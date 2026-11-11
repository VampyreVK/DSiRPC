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
from core.paths import DATA  # noqa: E402  (where DSiRPC writes; the macOS app's data folder)
LOG_DIR = os.path.join(DATA, "logs")
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


# How long the launcher's sync waits for RetroAchievements' list of the
# started game's unlocks before going on with what DSiRPC knows
RECONCILE_TIMEOUT = 5.0


class PortInUse(Exception):
    """UDP port 4244 is taken: DSiRPC (or one of its tools) is already running."""


HASH_LOOKUP_THREADS = 8  # RetroAchievements lookups of the launcher's hashes at a time
SET_FETCH_THREADS = 4    # sets downloaded at a time for the console
BUILD_TICK = 5.0         # seconds between "still working" frames while a set is built (the launcher waits 30)


def _game_name(code):
    """A game's name for the log: core/games.py's, its set's, or its code"""
    from core import games, ra_set
    if code in games.NAMES:
        return games.NAMES[code]
    try:
        s = ra_set.for_game(code, ra_set.RA_DIR)
    except (ra_set.SetFileError, OSError):
        s = None
    return s.title if s is not None and s.title else code


def _relearning(engine, code=None):
    """--clear-learning's first sync, for this game (code) or any."""
    cl = getattr(engine, "clear_learning", None)
    return bool(cl) and not getattr(engine, "_relearned", True) and (code is None or cl in ("all", code))


class Engine:
    DISCORD_INTERVAL = 5.0
    OVERLAY_INTERVAL = 2.0
    STATE_EVERY = 30.0

    def __init__(self, cfg, file=None, game=None, demo=False, demo_name=None, dsi_ip=None, port=4244,
                 interval=None, client_id=None, dry_run=False, discord=True, check_images=True, ra=True,
                 blank_ra=False, clear_ra=False, clear_learning=None):
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
        # --clear-learning ("all" or a game code): what the shadow check learned
        # is wiped here, and at the console's first sync its notes are thrown
        # away and those sets sent again
        self.clear_learning = clear_learning
        self._relearned = False    # that sync has happened
        self._ignored_notes = 0
        if clear_learning:
            self._wipe_learning()
        # Every unlock DSiRPC has seen, on the console or here, sent to
        # RetroAchievements or not (core/unlocks.py)
        from core.unlocks import UnlockLedger
        self.unlocks = UnlockLedger()
        # How long each game runs while DSiRPC watches, for the launcher's
        # game picker (core/playtime.py). Only when reading a real DSi.
        self.playtime = None
        if not demo and not file:
            from core.playtime import Playtime
            self.playtime = Playtime()
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
        self.discord = DiscordConnector(self._client_id, dry_run=dry_run, enabled=discord,
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
            self.console_sync = ConsoleSync(self._offline_sets, self._offline_unlocks, self._console_seen,
                                            saves=self._save_store, on_saves=self._on_saves,
                                            on_here=self._launcher_here, updates=self._console_files,
                                            stats=self._console_stats, on_notes=self._shadow_notes,
                                            on_roms=self._console_roms)
        self._saves = None             # the launcher's save sync (core/saves.py), made when first asked
        self._console_update = None    # the console's files for its updates (core/console_update.py)

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

    def _client_id(self):
        return self.client_id or self.cfg.discord_client_id

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
            from core.hub import is_bw, is_other
            title = snap.state.get('title') if is_other(snap.state) or is_bw(snap.state) else "Pokemon Platinum"
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
        if not self.blank_ra:
            got = {e['id']: int(time.time()) for e in events if e.get('type') == 'achievement' and e.get('id')}
            if got:
                self.unlocks.add(got)
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

    def _console_seen(self, ip, game, console="DSi"):
        """The launcher synced: the DSi is connected, in the launcher (game
        None) or starting a game, before the game says hello (the overlay's
        waiting screen and the tray show it)."""
        if not hasattr(self.source, 'launcher'):
            return
        from core import games, ra_set
        title = games.NAMES.get(game or '')
        if game and not title:
            try:
                s = ra_set.for_game(game)
                title = s.title if s else None
            except (ra_set.SetFileError, OSError, ValueError):
                title = None
        title = (title or game or '').replace("Pokemon", "Pokémon")
        seen = self.source.launcher or {}
        self.source.launcher = {'ip': ip, 'game': game, 'title': title, 'console': console, 'at': time.time(),
                                'here': seen.get('here', False) and seen.get('ip') == ip}

    def _launcher_here(self, ip, here, console="DSi"):
        """The launcher's "still here" (every 5 s while it waits for a key:
        it's in the launcher) or its "bye" (it's exiting), so the waiting
        screen and the tray stop saying the DSi's connected once it's gone
        (core/hub.py's launcher_state times the rest out)."""
        if not hasattr(self.source, 'launcher'):
            return
        seen = self.source.launcher or {}
        if not here:
            if seen.get('ip') == ip:
                self.source.launcher = None
            return
        same = seen.get('ip') == ip
        self.source.launcher = {'ip': ip, 'game': None, 'title': '', 'at': time.time(), 'here': True,
                                'console': seen.get('console', console) if same else console}

    def _offline_sets(self, game, stamps, unlocks=(), progress=None):
        """[(code, .DRS bytes)] for the console: the game it's starting
        (downloaded now if needed), then every other set in ra/, each only
        if the console's copy is missing or older. What's known to be
        unlocked is left out (what RetroAchievements has, what DSiRPC has
        seen unlocked on the console or here, and the unlocks the console
        just sent; nothing with --blank-ra or --dry-run), and listed as
        earned, with when, for nds-bootstrap's in-game menu. The game being
        started is checked with RetroAchievements first (_reconcile()).
        --clear-ra's sync sends every set. rcheevos builds them
        (core/offline.py's build_set())."""
        from core import frame_needs, offline, ra_set
        from core.rcheevos import RcheevosError, RcheevosMissing
        # Each exchange calls this first, then _offline_unlocks()
        self._clearing = self.clear_ra and not self._cleared
        self._cleared = self._cleared or self._clearing
        link = self.ra_link if self.ra_enabled else None
        from core import rom_hashes
        hashes = rom_hashes.load()
        by_hash = rom_hashes.set_codes(hashes)   # every game on the SD card RetroAchievements has a set for
        codes = ([game] if game else []) + sorted((set(ra_set.codes()) | set(by_hash)) - {game})
        # Their sets fetched now if they aren't here yet (or are another game's): once, then kept in ra/
        fetch = []
        if link is not None:
            for code in by_hash:
                if code == game:
                    continue
                try:
                    local = ra_set.for_game(code)
                except ra_set.SetFileError:
                    local = None
                if local is None or local.id != by_hash[code]:
                    fetch.append(code)
        fetched = {}
        if fetch:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            if progress:
                progress(0, len(fetch), offline.PROGRESS_SETS)
            with ThreadPoolExecutor(SET_FETCH_THREADS) as pool:
                jobs = {pool.submit(link.set_for_code, code): code for code in fetch}
                for n, job in enumerate(as_completed(jobs), 1):
                    try:
                        fetched[jobs[job]] = job.result()
                    except Exception:
                        logging.exception(f"Offline sync: {jobs[job]}: couldn't get its set")
                    if progress:
                        progress(n, len(fetch), offline.PROGRESS_SETS)
        out = []
        built = os.path.join(ra_set.RA_DIR, "cache", "built")   # (an unchanged set isn't built again)
        said = [time.monotonic()]
        for i, code in enumerate(codes):
            if progress:
                progress(i, len(codes), offline.PROGRESS_SETS)   # (building them takes a while too)
                said[0] = time.monotonic()

            def tick(i=i):
                # a long build: said again now and then, so the launcher keeps waiting
                if progress and time.monotonic() - said[0] >= BUILD_TICK:
                    progress(i, len(codes), offline.PROGRESS_SETS)
                    said[0] = time.monotonic()
            if not rom_hashes.may_send(hashes, code):
                continue    # no set for the versions on the console, or not answered yet (_console_roms())
            try:
                if code in fetched:
                    s = fetched[code]
                elif link and code == game:
                    s = link.set_for_code(code)
                else:
                    s = ra_set.for_game(code)
            except ra_set.SetFileError as e:
                logging.info(f"Offline sync: {code}: {e}")
                continue
            if not s:
                continue
            earned = {}
            if not self.blank_ra:
                if link and code == game and not self._clearing:
                    self._reconcile(link, s)
                earned = link.known_unlock_times(s.id) if link else {}
                if not self._clearing:
                    ids = {a['id'] for a in s.achievements}
                    for aid, when in self.unlocks.times(ids).items():
                        if not earned.get(aid):
                            earned[aid] = when
                    for u in unlocks:
                        if u['code'] == code and not earned.get(u['id']):
                            earned[u['id']] = u['when']
            # the achievements found to need checking every frame go in the frame lane first
            needs = frame_needs.load()
            if frame_needs.prune(needs, code, s.achievements):  # (RetroAchievements changed some since)
                try:
                    frame_needs.save(needs)
                except OSError:
                    pass
            proven = frame_needs.proven(needs, code, s.playable_achievements)
            clean = frame_needs.clean_counts(needs, code, s.playable_achievements)
            try:
                data = offline.build_set(s, code, set(earned), earned, proven, clean, cache_dir=built, tick=tick)
            except RcheevosMissing as e:
                logging.warning(f"Offline sync: no achievement sets for the console: {e}")
                return out
            except (RcheevosError, offline.FormatError) as e:
                logging.warning(f"Offline sync: {code}: couldn't build its set: {e}")
                continue
            # which achievements the console checks every frame, and their logic
            offline.remember_set(data, memaddr={a['id']: a['memaddr'] for a in s.achievements})
            if self._clearing or _relearning(self, code) or stamps.get(code) != offline.set_stamp(data):
                out.append((code, data))
        if self._clearing:
            logging.info(f"Offline sync: --clear-ra: sending all {len(out)} set(s) again")
        if _relearning(self):
            resent = [c for c, _ in out if _relearning(self, c)]
            logging.info(f"Offline sync: --clear-learning: ignored {self._ignored_notes} shadow note(s) from the "
                         f"console, re-sent {len(resent)} set(s)" + (f" ({', '.join(resent)})" if resent else ""))
            self._relearned = True
        return out

    def _console_roms(self, roms, hashed, hash_ms, progress=None):
        """The launcher's games by their RetroAchievements hash (sync version
        2, core/rom_hashes.py): kept, every hash not asked yet asked of
        RetroAchievements (HASH_LOOKUP_THREADS at a time, the game being
        started first; progress(done, of, what) keeps the launcher waiting),
        a hash it doesn't know told apart by the game's title (it has the
        game, or not: the title never links a set), and a set linked to a game
        by its title dropped where the hashes say RetroAchievements has none
        for the versions on the console. Returns {md5: offline.RA_*}."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from core import offline, rom_hashes
        if hashed:
            logging.info(f"Offline sync: the launcher hashed {hashed} game(s) in {hash_ms / 1000:.1f} s")
        store = rom_hashes.load()
        rom_hashes.record(store, roms)
        link = self.ra_link if self.ra_enabled else None
        names = {r[1]: (r[3] if len(r) > 3 and r[3] else r[0] or r[1]) for r in roms}
        codes = {r[1]: r[0] for r in roms}
        todo = list(dict.fromkeys(r[1] for r in sorted(roms, key=lambda r: not r[2])
                                  if rom_hashes.due(store, r[1])))
        new = []
        if link is not None and todo:
            if progress:
                progress(0, len(todo), offline.PROGRESS_CHECKING)
            with ThreadPoolExecutor(HASH_LOOKUP_THREADS) as pool:
                jobs = {pool.submit(link.lookup_hash, md5): md5 for md5 in todo}
                done, reachable = 0, True
                for job in as_completed(jobs):
                    if job.cancelled() or not reachable:
                        continue
                    try:
                        gid = job.result()
                    except Exception:
                        logging.exception(f"Offline sync: couldn't look {jobs[job]} up")
                        gid = None
                    done += 1
                    if gid is None:     # out of reach: the rest stay unknown ("new") till the next sync
                        reachable = False
                        for other in jobs:
                            other.cancel()
                    else:
                        rom_hashes.remember(store, jobs[job], gid)
                        new.append(jobs[job])
                    if progress:
                        progress(done, len(todo), offline.PROGRESS_CHECKING)
        # A hash RetroAchievements doesn't know: does it have the game at all?
        # (a file without a game code, homebrew often, has no title to look up: no)
        titled = {"": False}
        for md5 in [m for m in codes if rom_hashes.answer(store, m) == 0 and "game" not in store["games"][m]]:
            code = codes[md5]
            if code not in titled:
                titled[code] = link.title_has_game(code) if link is not None else None
            if titled[code] is not None:
                rom_hashes.remember(store, md5, 0, titled[code])
        for md5 in new:
            st = rom_hashes.status(store, md5)
            which = f"{names[md5]} ({codes[md5] or 'no game code'}, hash {md5})"
            if st in (rom_hashes.NOT_THIS_ROM, rom_hashes.NO_GAME):
                logging.info(f"RetroAchievements has no set for {which}: "
                             + ("it has the game, but not this ROM" if st == rom_hashes.NOT_THIS_ROM
                                else "it doesn't have the game"))
            elif st == rom_hashes.HAS_SET and not codes[md5]:
                logging.info(f"RetroAchievements has a set for {which}, but without a game code the console "
                             "can't be given it")
        try:
            rom_hashes.save(store)
        except OSError as e:
            logging.warning(f"Offline sync: couldn't save {rom_hashes.path()}: {e}")
        for code in sorted(set(codes.values()) - {""}):
            if rom_hashes.unsupported(store, code):
                s = rom_hashes.drop_title_link(code)
                if s is not None:
                    logging.warning(f"RetroAchievements: {code}: the set it was linked to by its title ({s.title}, "
                                    f"game {s.id}) isn't for the version on the console, so it won't be used or sent "
                                    "to the console any more (kept in ra/cache/unsupported/; unlocks already earned "
                                    "stay)")
        return {md5: rom_hashes.status(store, md5) for md5 in codes}

    def _reconcile(self, link, s):
        """Before the console gets the game it's starting: RetroAchievements'
        unlocks for it come here (unlocked.json and the ledger), and the ones
        known here that it doesn't have go there, if sending is on. Without
        its answer (signed out, out of reach within RECONCILE_TIMEOUT, or
        profile and sending both off in setup, which keep DSiRPC from
        starting sessions), what's known here stands in."""
        if not (self.ra_settings.profile or self.ra_settings.submit):
            return
        upstream = link.refresh_unlocks(s.id, timeout=RECONCILE_TIMEOUT)
        if upstream is None:
            return
        ids = {a['id'] for a in s.achievements}
        self.unlocks.add({aid: when for aid, when in upstream.items() if aid in ids})
        if not self.ra_settings.submit:
            return
        missing = {aid: when for aid, when in self.unlocks.times(ids).items()
                   if aid not in upstream and not link.pending(aid)}
        for aid, when in sorted(missing.items()):
            link.award_offline(aid, when or int(time.time()), s.title, s.id)
        if missing:
            logging.info(f"RetroAchievements: sending {len(missing)} unlock(s) of {s.title} it didn't have yet")

    def _wipe_learning(self):
        """--clear-learning: ra/cache/frame_needs.json forgets the game's (or
        every game's) proofs and clean counts, after a backup."""
        import shutil
        from core import frame_needs
        which = "every game's" if self.clear_learning == "all" else f"{self.clear_learning}'s"
        path = frame_needs.path()
        if not os.path.exists(path):
            logging.info(f"--clear-learning: no learned frame needs to wipe ({path} isn't there)")
            return
        try:
            shutil.copyfile(path, path + ".bak")
            needs = frame_needs.load()
            gone = frame_needs.wipe(needs, None if self.clear_learning == "all" else self.clear_learning)
            frame_needs.save(needs)
            logging.info(f"--clear-learning: wiped {which} learned frame needs ({gone} entr{'y' if gone == 1 else 'ies'}; "
                         f"backup {path}.bak)")
        except OSError as e:
            logging.warning(f"--clear-learning: couldn't wipe {path}: {e}")

    def _shadow_notes(self, notes, stamps=None):
        """The console's shadow check's notes ([{'code', 'id', 'proven'}],
        core/offline.py's read_shadow_notes()): which frame lane achievements
        came out differently checked every frame and every few frames (they
        need the frame lane), and which didn't in a while of their memory
        changing. Kept in ra/cache/frame_needs.json for the next sets. A
        note about logic RetroAchievements has changed since the console's
        set was built (stamps: the console's sets, {code: stamp}) is left
        out, and so is a game whose set file can't be read: the rest are
        still kept. (Either way they count as taken, so the launcher clears
        RPCUNLK.BIN: kept there, they'd come back at every sync, and the
        file would fill up.)"""
        from core import frame_needs, offline, ra_set
        if _relearning(self):  # --clear-learning: not these
            drop = [n for n in notes if _relearning(self, n['code'])]
            self._ignored_notes += len(drop)
            notes = [n for n in notes if n not in drop]
        needs = frame_needs.load()
        changed = False
        for code in sorted({n['code'] for n in notes}):
            mine = [n for n in notes if n['code'] == code]
            try:
                s = ra_set.for_game(code)
            except ra_set.SetFileError as e:
                logging.warning(f"Offline sync: {code}: {len(mine)} shadow note(s) left out: its set file ({e})")
                continue
            memaddr = {a['id']: a['memaddr'] for a in s.achievements} if s else {}
            # The logic the console checked: the set it has (by its stamp), as built
            known = offline.known_set(stamps[code]) if stamps and code in stamps else None
            ran = known['mem'] if known and known['code'] == code else None
            if ran is not None:
                stale = [n for n in mine if n['id'] in memaddr and ran.get(n['id']) is not None
                         and ran[n['id']] != frame_needs.memaddr_hash(memaddr[n['id']])]
                if stale:
                    logging.info(f"Offline sync: {code}: {len(stale)} shadow note(s) left out: RetroAchievements "
                                 "changed those achievements since the console's set was made")
                    mine = [n for n in mine if n not in stale]
            for n in mine:
                if n['id'] not in memaddr:
                    continue
                if n['proven']:
                    if frame_needs.add(needs, code, n['id'], memaddr[n['id']], "console"):
                        logging.info(f"Offline sync: {code}: achievement {n['id']} needs checking every frame (the console found)")
                else:
                    frame_needs.add_clean(needs, code, n['id'], memaddr[n['id']])
                changed = True
        if changed:
            try:
                frame_needs.save(needs)
            except OSError as e:
                logging.warning(f"Offline sync: couldn't save frame_needs.json: {e}")

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
        # Noted here at once, so the next sync's sets have them whatever
        # RetroAchievements does (sending off, out of reach, or no answer
        # yet); the ones DSiRPC had already seen (unlocked here, or the
        # console's while connected) are left out below
        new = self.unlocks.add({u['id']: u['when'] for u in unlocks})
        sets, rows, known = {}, [], 0
        for u in unlocks:
            if u['code'] not in sets:
                try:
                    sets[u['code']] = ra_set.for_game(u['code'])
                except ra_set.SetFileError:
                    sets[u['code']] = None
            s = sets[u['code']]
            if u['id'] not in new or (s and link and u['id'] in link.known_unlocks(s.id)):
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

    def _save_store(self):
        """The SaveStore for the launcher's save sync, in dsirpc.cfg's [saves]
        folder (made again when the folder or the number of versions changes)."""
        from core.saves import SaveStore
        path, keep = self.cfg.saves_path, self.cfg.save_versions
        if self._saves is None or self._saves.root != path or self._saves.keep != keep:
            self._saves = SaveStore(path, keep)
        return self._saves

    def _console_files(self):
        """The console's files as they came with this DSiRPC, for the
        launcher's update check, or None while the tray's "Console updates"
        is off."""
        if not self.cfg.console_updates:
            return None
        if self._console_update is None:
            from core.console_update import ConsoleFiles
            self._console_update = ConsoleFiles()
        return self._console_update

    def _console_stats(self):
        """The playtimes and how DSiRPC is doing, for the launcher's modern
        look (core/playtime.py): (Playtime, {'pc', 'ra', 'discord'})."""
        from core.playtime import pc_name
        ra = self.ra_link.username if self.ra_link and self.ra_link.signed_in else ""
        discord = self.discord.status not in ("off",) and not self.discord.status.startswith(("no ", "can't"))
        return self.playtime, {'pc': pc_name(), 'ra': ra, 'discord': discord}

    def _on_saves(self, event):
        """The save sync's events: the tray hears the summary at the end."""
        if event['type'] != 'saves_synced' or not self.on_change:
            return
        try:
            self.on_change([event])
        except Exception:
            logging.exception("on_change failed")

    def _on_update(self, snap, events):
        self._check_config()
        self._log_achievements(events)
        if self.playtime and snap.online:
            self.playtime.tick((getattr(self.source, 'game', None) or {}).get('code'))
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
        from core.hub import is_bw, is_other
        state = snap.state if snap.online else None
        card = is_other(state) or is_bw(state)
        game = getattr(self.source, 'game', None)
        out = {
            'time': time.time(),
            'pid': os.getpid(),
            'online': bool(snap.online),
            'status': snap.status,
            'game': game,
            'title': (state.get('title') if card else "Pokemon Platinum") if state else None,
            'header_title': state.get('header_title') if card else None,
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

    def restart_console_sync(self):
        """Closes the launcher's sync ports and opens them again with a new
        listener (from the tray's thread, once macOS lets DSiRPC on the
        local network: the listener opened before that never hears the
        launcher)."""
        old = self.console_sync
        if not old or not self._started:
            return
        old.stop()
        from core.console_sync import ConsoleSync
        new = ConsoleSync(old.sets_for, old.on_unlocks, old.on_console, port=old.port, host=old.host,
                          saves=old.saves, on_saves=old.on_saves, on_here=old.on_here, updates=old.updates,
                          stats=old.stats, on_notes=old.on_notes, on_roms=old.on_roms)
        try:
            new.start()
        except OSError as e:
            logging.warning(f"No offline sync: UDP/TCP port {new.port} is in use ({e})")
            new = None
        self.console_sync = new

    def stop(self):
        self.set_overlay(False)
        if self.console_sync:
            self.console_sync.stop()
        if self.playtime:
            self.playtime.flush()
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

    def set_music(self, name):
        """The overlay window's ambient music (utils.config.MUSIC_CHOICES),
        straight away if the window's open."""
        self.cfg.ambient_music = name
        window = self.overlay_window
        if window is not None:
            window.set_music(name)

    def _apply_overlay(self, on):
        """Reads faster (and battles every 0.3 s) only while the overlay shows them."""
        if hasattr(self.source, 'fast_battles'):
            self.source.fast_battles = on
        if not self.fixed_interval:
            self.hub.interval = self.OVERLAY_INTERVAL if on else self.DISCORD_INTERVAL
        if hasattr(self.source, 'parse_interval'):
            self.source.parse_interval = self.hub.interval

    def _make_window(self, remote=False):
        """The overlay window; `remote`: in a process of its own (macOS's
        menu bar, see overlay/remote.py), else on the calling thread."""
        from overlay.app import OverlayWindow

        def save_scale(n):
            self.cfg.overlay_scale = n
            if self.persist:
                self.save_config()
        chroma = self.cfg.chroma or None
        if remote:
            from overlay.remote import RemoteOverlay
            os.makedirs(LOG_DIR, exist_ok=True)
            return RemoteOverlay(self.hub, scale=self.cfg.overlay_scale, chroma=chroma, on_scale=save_scale,
                                 log_file=os.path.join(LOG_DIR, "overlay.log"), music=self.cfg.ambient_music)
        try:
            window = OverlayWindow(self.hub, scale=self.cfg.overlay_scale, chroma=chroma, on_scale=save_scale,
                                   music=self.cfg.ambient_music)
        except ValueError as e:
            logging.warning(f"chroma in {os.path.basename(self.cfg.path)}: {e}; ignoring it")
            window = OverlayWindow(self.hub, scale=self.cfg.overlay_scale, on_scale=save_scale,
                                   music=self.cfg.ambient_music)
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
        """Opens or closes the overlay window on its own thread (tray mode;
        on macOS the window is in a process of its own, as the menu bar has
        the main thread). on_closed() is called if the user closes the window."""
        with self._overlay_lock:
            if on and not self.overlay_on:
                window = self._make_window(remote=sys.platform == "darwin")

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
