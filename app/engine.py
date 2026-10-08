"""
engine.py - what runs while DSiRPC runs, whichever way it's started
(dsirpc.py in a console, or the tray icon):

  the state hub (core/hub.py)        the one thing talking to the DSi
  the Discord Rich Presence          rpc/presence_connector.py, a hub listener
  the overlay window (optional)      overlay/app.py, drawn from the hub
  RetroAchievements                  core/ra_link.py (signed in) and
                                     core/ra_game.py, run by the hub's source

The hub reads every 5 s while only Discord needs the data (Discord takes an
update about every 5 s anyway), and every 2 s with the battlers a few times a
second during battles while the overlay window is open.

The engine also writes logs/state.json (what's running, refreshed at least
every 30 s), so 'dsirpc.py setup' can see the game while the tray holds the
DSi's UDP port.
"""

import json
import logging
import logging.handlers
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "dsirpc.log")
STATE_FILE = os.path.join(LOG_DIR, "state.json")
ACHIEVEMENTS_LOG = os.path.join(LOG_DIR, "achievements.log")


def setup_logging(console=True, verbose=False):
    """Logs to logs/dsirpc.log (kept to about 3 MB) and, with console, to
    the console as well."""
    os.makedirs(LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    root.addHandler(fh)
    if console and sys.stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        root.addHandler(sh)


class PortInUse(Exception):
    """UDP port 4244 is taken: DSiRPC (or one of its tools) is already running."""


class Engine:
    DISCORD_INTERVAL = 5.0
    OVERLAY_INTERVAL = 2.0
    STATE_EVERY = 30.0

    def __init__(self, cfg, file=None, game=None, demo=False, demo_name=None, dsi_ip=None, port=4244,
                 interval=None, client_id=None, dry_run=False, discord=True, check_images=True, ra=True,
                 blank_ra=False, clear_ra=False):
        from core.charmap import parse_charmap_txt
        from core.hub import DsiSource, FileSource, StateHub
        from core.ra_game import RaSettings
        from rpc.presence_connector import DiscordConnector

        self.cfg = cfg
        self.client_id = client_id
        self.fixed_interval = interval
        self.ra_enabled = ra
        self.dry_run = dry_run
        # Debugging (dsirpc.py --blank-ra / --clear-ra; README's "Debugging
        # options"): act as if nothing were unlocked (a dry run does too), and
        # wipe the console's offline state at the first sync.
        self.blank_ra = blank_ra or dry_run
        self.clear_ra = clear_ra
        self._cleared = False      # --clear-ra's sync has happened
        self._clearing = False     # this sync is it
        self.ra_settings = RaSettings()
        self._apply_ra_settings()
        self.ra_link = None
        charmap = parse_charmap_txt(os.path.join(ROOT, "PokeGen4Charmap.txt"))
        if demo:
            from core.demo import DemoSource
            base = FileSource(charmap, file).state if file else None
            source, self.fixed_interval = DemoSource(base, name=demo_name), 0.5
        elif file:
            source, self.fixed_interval = FileSource(charmap, file, game, self.ra_settings), interval or 1.0
        else:
            if ra and cfg.ra_signed_in:
                from core.ra_link import RALink
                self.ra_link = RALink(cfg.ra_username, cfg.ra_token, cfg.ra_roms or None, self.ra_settings,
                                      blank=self.blank_ra)
            try:
                source = DsiSource(charmap, port=port, dsi_ip=dsi_ip, ra_link=self.ra_link,
                                   ra_settings=self.ra_settings)
            except OSError as e:
                if self.ra_link:
                    self.ra_link.stop()
                raise PortInUse(f"UDP port {port} is already in use ({e})") from e
        self.source = source
        self.hub = StateHub(source, interval=self.fixed_interval or self.DISCORD_INTERVAL)
        self.discord = DiscordConnector(self._client_id_for, dry_run=dry_run, enabled=discord,
                                        check_images=check_images)
        self._apply_console_icon()
        self.hub.add_listener(self.discord.on_update)
        self.hub.add_closer(self.discord.close)
        self.hub.add_listener(self._on_update)

        self.on_change = None          # fn(events) when what the tray shows changes (hub thread)
        self.persist = False           # save setting changes (overlay size) to dsirpc.cfg
        self.overlay_window = None
        self.overlay_thread = None
        self._overlay_lock = threading.Lock()
        self._last_view = None
        self._state_written = 0.0
        self._cfg_mtime = self._mtime(cfg.path)
        self._started = False
        self._apply_overlay(False)

        # Offline play: the launcher hands over what was unlocked without
        # DSiRPC and takes the sets it doesn't have (core/console_sync.py).
        # Only when reading a real DSi.
        self.console_sync = None
        if not demo and not file:
            from core.console_sync import ConsoleSync
            self.console_sync = ConsoleSync(self._offline_sets, self._offline_unlocks)

    # -- settings ----------------------------------------------------------

    def _apply_ra_settings(self):
        """dsirpc.cfg's [ra] into the settings the RetroAchievements side
        reads (the same object, so a reload takes effect right away)."""
        c, s = self.cfg, self.ra_settings
        sending = self.ra_enabled and not self.dry_run  # a dry run sends nothing anywhere
        s.achievements = c.ra_achievements and self.ra_enabled
        s.submit = c.ra_submit and sending
        s.profile = c.ra_profile and sending
        s.racache = c.racache or None
        s.auto_import = c.ra_auto_import
        s.interval = c.ra_interval

    def _apply_console_icon(self):
        from rpc import generic_presence
        self.discord.console = generic_presence.console_icon(self.cfg.console_icon)

    def set_console_icon(self, key):
        """The picture from Assets/Consoles for Discord's small image ('' for none)."""
        self.cfg.console_icon = key or ""
        self._apply_console_icon()

    def _client_id_for(self, code, platinum):
        return self.client_id or self.cfg.client_id_for(code, platinum)

    @staticmethod
    def _mtime(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return None

    def _check_config(self):
        """Picks up dsirpc.cfg changes (e.g. from setup) while running."""
        m = self._mtime(self.cfg.path)
        if m == self._cfg_mtime:
            return
        self._cfg_mtime = m
        from utils.config import Config
        self.cfg = Config(self.cfg.path)
        self._apply_ra_settings()
        self._apply_console_icon()
        if self.ra_link:
            self.ra_link.update(self.cfg.ra_username, self.cfg.ra_token, self.cfg.ra_roms or None)
        elif self.cfg.ra_signed_in and self.ra_enabled and hasattr(self.source, 'ra_link'):
            # Just signed in (setup): connect, and start the game's RA side over with it.
            from core.ra_link import RALink
            self.ra_link = RALink(self.cfg.ra_username, self.cfg.ra_token, self.cfg.ra_roms or None,
                                  self.ra_settings, blank=self.blank_ra)
            self.source.ra_link = self.ra_link
            self.source.ra_code = None
        logging.info(f"Reloaded {self.cfg.path}")

    def save_config(self):
        try:
            self.cfg.save()
            self._cfg_mtime = self._mtime(self.cfg.path)  # not a change to reload
        except OSError as e:
            logging.warning(f"Couldn't save {self.cfg.path}: {e}")

    # -- status ------------------------------------------------------------

    def headline(self):
        """One line for the tray: what's running, or what DSiRPC waits for."""
        snap = self.hub.snapshot()
        if snap.online and snap.state:
            from core.hub import is_other
            title = snap.state.get('title') if is_other(snap.state) else "Pokemon Platinum"
            return f"Playing {title}"
        return snap.status or "Starting"

    @property
    def ra_game(self):
        return getattr(self.source, 'ra_game', None)

    def ra_status(self):
        """One line for the tray about RetroAchievements."""
        ra = self.ra_game
        who = f"{self.ra_link.username}" if self.ra_link and self.ra_link.signed_in else "not signed in"
        if not ra or not self.online:
            return f"RetroAchievements: {who}"
        if not ra.set:
            return f"RetroAchievements: {ra.note or 'looking for the set'}"
        p = ra.progress
        if p:
            return f"RetroAchievements: {p[0]} of {p[1]} unlocked ({who})"
        return f"RetroAchievements: {ra.total} achievements ({who})"

    @property
    def online(self):
        return self.hub.snapshot().online

    @property
    def overlay_on(self):
        return self.overlay_thread is not None and self.overlay_thread.is_alive()

    def _log_achievements(self, events):
        lines = []
        for e in events:
            if e.get('type') == 'achievement':
                p = e.get('progress')
                lines.append(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{e['game']}\t{e['id']}\t{e['title']}\t"
                             f"{e['points']} points\t{'sent' if e['sent'] else 'not sent'}"
                             + (f"\t{p[0]}/{p[1]}" if p else "") + "\n")
        if lines:
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                with open(ACHIEVEMENTS_LOG, "a", encoding="utf-8") as f:
                    f.writelines(lines)
            except OSError:
                pass

    # -- offline play (core/console_sync.py's thread) --------------------------

    def _offline_sets(self, game, stamps, unlocks=()):
        """[(code, .DRS bytes)] for the console: the game it's starting
        (downloaded now if needed), then every other set in ra/, each only
        if the console's copy is missing or older. What's known to be
        unlocked is left out, including the unlocks the console just sent
        (nothing with --blank-ra or --dry-run), and listed as earned, with
        when, for nds-bootstrap's in-game menu. --clear-ra's sync sends every
        set. rcheevos builds them (core/offline.py's build_set())."""
        from core import offline, ra_set
        from core.rcheevos import RcheevosError, RcheevosMissing
        # Each exchange calls this first, then _offline_unlocks()
        self._clearing = self.clear_ra and not self._cleared
        self._cleared = self._cleared or self._clearing
        link = self.ra_link if self.ra_enabled else None
        codes = ([game] if game else []) + [c for c in ra_set.codes() if c != game]
        out = []
        for code in codes:
            try:
                s = link.set_for_code(code) if (link and code == game) else ra_set.for_game(code)
            except ra_set.SetFileError as e:
                logging.info(f"Offline sync: {code}: {e}")
                continue
            if not s:
                continue
            earned = {}
            if not self.blank_ra:
                earned = link.known_unlock_times(s.id) if link else {}
                if not self._clearing:
                    for u in unlocks:
                        if u['code'] == code and not earned.get(u['id']):
                            earned[u['id']] = u['when']
            try:
                data = offline.build_set(s, code, set(earned), earned)
            except RcheevosMissing as e:
                logging.warning(f"Offline sync: no achievement sets for the console: {e}")
                return out
            except (RcheevosError, offline.FormatError) as e:
                logging.warning(f"Offline sync: {code}: couldn't build its set: {e}")
                continue
            if self._clearing or stamps.get(code) != offline.set_stamp(data):
                out.append((code, data))
        if self._clearing:
            logging.info(f"Offline sync: --clear-ra: sending all {len(out)} set(s) again")
        return out

    def _offline_unlocks(self, unlocks):
        """Unlocks from offline play: sent to RetroAchievements like any
        other (with when they happened), if that's on in setup. The console
        saves every unlock, so the ones DSiRPC already knows about (unlocked
        while it was watching) are left out. Returns False to leave them on
        the console (--dry-run); --clear-ra's sync takes them without
        sending them."""
        from core import ra_set
        from core.ra_link import queue_offline
        if self._clearing:
            logging.info(f"Offline sync: --clear-ra: cleared {len(unlocks)} unlock(s) off the console, "
                         "nothing sent")
            return True
        if self.dry_run:
            logging.info(f"Offline sync: --dry-run: {len(unlocks)} unlock(s) from the console, not sent "
                         f"and left on it: {', '.join(str(u['id']) for u in unlocks)}")
            return False
        sending = self.cfg.ra_submit and self.ra_enabled and not self.dry_run
        link = self.ra_link
        sets, rows, known = {}, [], 0
        for u in unlocks:
            if u['code'] not in sets:
                try:
                    sets[u['code']] = ra_set.for_game(u['code'])
                except ra_set.SetFileError:
                    sets[u['code']] = None
            s = sets[u['code']]
            if s and link and u['id'] in link.known_unlocks(s.id):
                known += 1
                continue
            a = next((a for a in s.achievements if a['id'] == u['id']), None) if s else None
            row = {'id': u['id'], 'when': u['when'], 'game': s.title if s else u['code'],
                   'game_id': s.id if s else 0, 'title': a['title'] if a else f"achievement {u['id']}",
                   'points': a['points'] if a else 0}
            rows.append(row)
            if sending and link:
                link.award_offline(row['id'], row['when'], row['game'], row['game_id'])
        if known:
            logging.info(f"Offline play: {known} unlock(s) from the console DSiRPC already had")
        if not rows:
            return
        if sending and not link:
            queue_offline(rows)
        lines = [f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r['when']))}\t{r['game']}\t{r['id']}\t"
                 f"{r['title']}\t{r['points']} points\t{'sent' if sending else 'not sent'} (offline play)\n"
                 for r in rows]
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(ACHIEVEMENTS_LOG, "a", encoding="utf-8") as f:
                f.writelines(lines)
        except OSError:
            pass
        logging.info(f"Offline play: {len(rows)} achievement(s) unlocked"
                     + ("" if sending else " (not sent: sending unlocks is off in setup)"))
        if self.on_change:
            try:
                self.on_change([{'type': 'offline_unlocks', 'count': len(rows), 'sent': sending,
                                 'titles': [r['title'] for r in rows]}])
            except Exception:
                logging.exception("on_change failed")
        return len(rows)

    def _on_update(self, snap, events):
        self._check_config()
        self._log_achievements(events)
        view = (self.headline(), self.discord.status, snap.online, self.overlay_on, self.ra_status())
        changed = view != self._last_view
        if changed:
            if self._last_view is None or view[0] != self._last_view[0]:
                logging.info(view[0])
            self._last_view = view
        if changed or time.time() - self._state_written > self.STATE_EVERY:
            self._write_state(snap)
        if (changed or events) and self.on_change:
            try:
                self.on_change(events)
            except Exception:
                logging.exception("on_change failed")

    def _write_state(self, snap):
        from core.hub import is_other
        state = snap.state if snap.online else None
        game = getattr(self.source, 'game', None)
        out = {
            'time': time.time(),
            'pid': os.getpid(),
            'online': bool(snap.online),
            'status': snap.status,
            'game': game,
            'title': (state.get('title') if is_other(state) else "Pokemon Platinum") if state else None,
            'header_title': state.get('header_title') if is_other(state) else None,
            'ra_game_id': self.ra_game.game_id if self.ra_game else 0,
            'discord': self.discord.status,
        }
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=1)
            os.replace(tmp, STATE_FILE)
            self._state_written = time.time()
        except OSError:
            pass

    # -- running -----------------------------------------------------------

    def start(self):
        self.hub.start()
        self._started = True
        if self.console_sync:
            try:
                self.console_sync.start()
            except OSError as e:
                logging.warning(f"No offline sync: UDP/TCP port {self.console_sync.port} is in use ({e})")
                self.console_sync = None

    def stop(self):
        self.set_overlay(False)
        if self.console_sync:
            self.console_sync.stop()
        if self._started:
            self.hub.stop()
            self._started = False
        if self.ra_link:
            self.ra_link.stop()
        try:
            os.remove(STATE_FILE)
        except OSError:
            pass

    def once(self):
        """One read and one presence update, on this thread (for --file --dry-run)."""
        from core.hub import Snapshot
        state = self.source.read()
        self.discord.on_update(Snapshot(state, bool(state), time.time(), getattr(self.source, 'status', '')), [])
        return state

    def set_discord(self, on):
        self.discord.set_enabled(on)

    def _apply_overlay(self, on):
        """Reads faster (and battles every 0.3 s) only while the overlay shows them."""
        if hasattr(self.source, 'fast_battles'):
            self.source.fast_battles = on
        if not self.fixed_interval:
            self.hub.interval = self.OVERLAY_INTERVAL if on else self.DISCORD_INTERVAL
        if hasattr(self.source, 'parse_interval'):
            self.source.parse_interval = self.hub.interval

    def _make_window(self):
        from overlay.app import OverlayWindow

        def save_scale(n):
            self.cfg.overlay_scale = n
            if self.persist:
                self.save_config()
        chroma = self.cfg.chroma or None
        try:
            window = OverlayWindow(self.hub, scale=self.cfg.overlay_scale, chroma=chroma, on_scale=save_scale)
        except ValueError as e:
            logging.warning(f"chroma in {os.path.basename(self.cfg.path)}: {e}; ignoring it")
            window = OverlayWindow(self.hub, scale=self.cfg.overlay_scale, on_scale=save_scale)
        return window

    def run_overlay_here(self):
        """The overlay window on this thread, until it's closed."""
        self.overlay_window = self._make_window()
        self._apply_overlay(True)
        try:
            self.overlay_window.run()
        finally:
            self._apply_overlay(False)
            self.overlay_window = None

    def set_overlay(self, on, on_closed=None):
        """Opens or closes the overlay window on its own thread (tray mode).
        on_closed() is called if the user closes the window."""
        with self._overlay_lock:
            if on and not self.overlay_on:
                window = self._make_window()

                def run():
                    closed = window.run()
                    self._apply_overlay(False)
                    if closed and on_closed:
                        on_closed()
                self.overlay_window = window
                self._apply_overlay(True)
                self.overlay_thread = threading.Thread(target=run, name="Overlay", daemon=True)
                self.overlay_thread.start()
            elif not on and self.overlay_on:
                self.overlay_window.stop()
                self.overlay_thread.join(timeout=5)
                self._apply_overlay(False)
            if not self.overlay_on:
                self.overlay_window = self.overlay_thread = None
