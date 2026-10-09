"""
hub.py - the state hub: one poller that owns the DSi connection and hands the
parsed game state to everything else (the overlay window, Discord, ...).

Only one process can use UDP port 4244, so anything that wants live data hangs
off a StateHub instead of talking to the DSi itself.

    hub = StateHub(DsiSource(charmap))
    hub.add_listener(lambda snap, events: ...)   # called from the hub thread
    hub.start()
    snap = hub.snapshot()                        # latest state, any thread
    ...
    hub.stop()

A source is anything with read() -> state dict or None, plus an optional
status text, forget_dsi(), next_delay() (seconds until the next read, to
override the hub's interval) and take_events() (events of its own, like an
achievement unlocking). Returning the very same state object as last time
means "nothing new, still there". A state is Platinum's parsed dict (see
core/parser.py; it has no 'kind'), Black or White's (core/bw_parser.py,
{'kind': 'bw', ...}, laid out like Platinum's plus the RetroAchievements
keys of core/other_game.py), or, for any other game, the dict from
core/other_game.py ({'kind': 'other', ...}); is_other() and is_bw() tell
them apart.
Sources here:

    DsiSource    the real DSi (waits for hellos, re-learns the IP after it
                 goes quiet, reads only the battlers a few times a second
                 during a battle, follows the DSi to other games)
    FileSource   a 4 MB RAM dump, for offline testing
    core/demo.py DemoSource, made-up scenes for working on the overlay

Events are worked out by comparing each new state with the previous one; see
diff_events().
"""

import logging
import struct
import threading
import time

from . import games
from .bw_parser import BWParser
from .other_game import OtherGame, ra_summary
from .parser import PlatinumParser, TrainerMemory
from .ra_game import RaGame, RaSettings


def is_other(state):
    """True for the state of a game without its own parser (core/other_game.py)."""
    return bool(state) and state.get('kind') == 'other'


def is_bw(state):
    """True for Pokemon Black or White's state (core/bw_parser.py)."""
    return bool(state) and state.get('kind') == 'bw'


class Snapshot:
    """What the hub knows right now. `state` is the last good parse (kept
    while offline, so a window can show the last known party), `online` says
    whether the game answered recently."""

    def __init__(self, state=None, online=False, updated=0.0, status="starting"):
        self.state = state
        self.online = online
        self.updated = updated      # time.time() of the last good parse
        self.status = status        # short human-readable source status


class DsiSource:
    """Reads the real DSi through core/dsirpc_client.py.

    A full read is about 20 requests, and each one the DSi's wifi chip drops
    costs a second-long timeout, so during a battle only the battlers are
    read (one request: the fields decode_battle_mon() needs, the last moves,
    the music and the battle pointer), every FAST_INTERVAL seconds.
    Everything else is carried over from the last full read. A full read is
    done again straight away when a battler stops decoding, the music or the
    battle pointer changes (the battle is ending or another one started), or
    several quick reads in a row get no reply, and at least every
    BATTLE_FULL_EVERY seconds as a safety net. Set fast_battles = False to
    read battles like everything else (when nothing shows them live).

    Pokemon Black and White (US) get their own parser (core/bw_parser.py),
    read the same way (battlers only during a battle), with the game card's
    RetroAchievements keys added. While what it reads doesn't look like the
    game (another region, or memory laid out differently), they get the game
    card like any other game, and the parser is tried again every
    parse_interval.

    Any other game is followed with core/other_game.py: its name, and its
    RetroAchievements rich presence if there's a set for it.

    Every game, Platinum too, gets its RetroAchievements side
    (core/ra_game.py): its achievements are checked every
    ra_settings.interval seconds (about once a second), between the parses,
    which happen every parse_interval seconds, and the ones checked every
    frame on the PC (core/frame_capture.py) a few times a second, also in
    between the requests of a long read, so the DSi's record of frames
    never fills up. DSiRPC's own unlocks are passed on to the console's
    checker. `ra_link` is the connection to RetroAchievements
    (core/ra_link.py), if you're signed in."""

    FAST_INTERVAL = 0.3
    FAST_TIMEOUT = 0.6
    FAST_MISSES = 5
    BATTLE_FULL_EVERY = 60.0

    def __init__(self, charmap, port=4244, dsi_ip=None, timeout=1.0, racache=None, ra_link=None,
                 ra_settings=None):
        from .dsirpc_client import DSiClient
        from .dsi_memory import DsiRam, SparseRam
        self.charmap = charmap
        self.ra_settings = ra_settings or RaSettings()
        if racache is not None:
            self.ra_settings.racache = racache
        self.ra_link = ra_link
        self.fast_battles = True
        self.parse_interval = 5.0
        self.last_parse = 0.0
        self.port = port
        self.pinned_ip = dsi_ip
        self.client = DSiClient(port=port, dsi_ip=dsi_ip, timeout=timeout)
        self.client.ach.on_unlocks = self._console_unlocks
        self.client.ach.on_report = self._console_report
        self.client.idle_hook = self._capture_tick
        self.ram = DsiRam(self.client)
        self.sparse = SparseRam(self.client)
        self.ra_game = None     # RaGame for the running game
        self.ra_code = None
        self._events = []
        self.failed = False
        self.trainers = TrainerMemory()
        self.last = None        # the latest state returned
        self.last_full = 0.0    # time.time() of the last full read
        self.fast_misses = 0
        self.other = None       # OtherGame while the DSi runs something other than Platinum
        self.bw_started = None  # when Black/White started being read (for Discord's timer)
        self.bw_failed = False  # the last Black/White parse didn't look like the game

    @property
    def status(self):
        if self.client.dsi_ip is None:
            return f"Waiting for the DSi on UDP {self.port}"
        if self.failed:
            return f"DSi at {self.client.dsi_ip} isn't answering"
        if self.other:
            return f"DSi at {self.client.dsi_ip}: {self.other.title}"
        return f"DSi at {self.client.dsi_ip}"

    @property
    def game(self):
        """The game the DSi said it's running (None for old builds)."""
        return self.client.game

    @property
    def racache(self):
        return self.ra_settings.racache

    @racache.setter
    def racache(self, value):
        self.ra_settings.racache = value

    def _in_battle(self):
        return bool(self.last and not is_other(self.last) and self.last['battle']['active'])

    def next_delay(self):
        if self.client.dsi_ip is None:
            return None
        now = time.time()
        delays = []
        if self.fast_battles and self._in_battle():
            delays.append(self.FAST_INTERVAL)
        if self.ra_game and (self.ra_game.runtime or not self.ra_game.set):
            delays.append(self.ra_game.next_due - now)
        if self.ra_game and self.ra_game.capture_due is not None:
            delays.append(self.ra_game.capture_due - now)
        if games.is_platinum(self.client.game) or games.is_bw(self.client.game):
            delays.append(self.last_parse + self.parse_interval - now)
        return max(0.05, min(delays)) if delays else None

    def take_events(self):
        events, self._events = self._events, []
        return events

    def _switch_ra(self, game):
        """The RetroAchievements side follows the game the DSi runs (old
        builds that don't say count as Platinum)."""
        code = (game or {}).get('code') if game else games.PLATINUM_US
        if code == self.ra_code:
            return
        if self.ra_game:
            self.ra_game.close()
        self.ra_code = code
        self.ra_game = RaGame(game or {'code': code, 'version': 0, 'header_crc': 0}, self.sparse,
                              self.ra_link, self.ra_settings) if code else None

    def _console_unlocks(self, ids):
        """The console's own checker (offline play's, which runs while you
        play online too) unlocked these: they count right away."""
        if self.ra_game:
            self.ra_game.inbox.put(("console", list(ids)))

    def _console_report(self, report):
        """The console's checker reported (once a second): which set it runs."""
        if self.ra_game:
            self.ra_game.inbox.put(("report", dict(report)))

    def _capture_tick(self):
        """The achievements checked every frame on the PC (also called
        between the requests of a long read)."""
        ra = self.ra_game
        if ra is None or ra.capture_due is None or time.time() < ra.capture_due:
            return
        ra.capture_tick()
        self._events += ra.take_events()

    def _push_unlocks(self):
        """DSiRPC's own unlocks, to the console's checker and in-game menu."""
        ra = self.ra_game
        todo = ra.pending_pushes() if ra else []
        if not todo:
            return
        try:
            taken = self.client.push_unlocks(todo, retries=1, timeout=0.5)
        except (TimeoutError, RuntimeError):
            return
        ra.pushed_to_console(todo[:taken])
        if taken:
            logging.info(f"Console: told it about {taken} unlock(s) DSiRPC made, for its in-game menu")

    def _ra_tick(self):
        ra = self.ra_game
        if not ra or time.time() < ra.next_due:
            return
        ra.next_due = time.time() + self.ra_settings.interval
        try:
            ra.tick()
        except (TimeoutError, RuntimeError) as e:
            ra.read_ok = False
            logging.debug(f"RetroAchievements read failed: {e}")
        except Exception:
            ra.read_ok = False
            logging.exception("RetroAchievements check failed")
        self._events += ra.take_events()
        self._push_unlocks()

    def read(self):
        if self.client.dsi_ip is None:
            # Short wait so the hub thread can still be stopped quickly.
            if not self.client.wait_for_dsi(max_wait=1.0):
                return None
        game = self.client.game
        self._switch_ra(game)
        self._capture_tick()
        self._ra_tick()
        if games.is_bw(game):
            return self._read_bw(game)
        self.bw_started = None
        # The Platinum parser only makes sense on Platinum.
        if not games.is_platinum(game):
            return self._read_other(game)
        if self.other:
            self.other.close()
            self.other = None
        if self.fast_battles and self._in_battle() and time.time() - self.last_full < self.BATTLE_FULL_EVERY:
            try:
                data = self._read_battlers(self.last)
                self.fast_misses = 0
            except (TimeoutError, RuntimeError):
                self.fast_misses += 1
                if self.fast_misses < self.FAST_MISSES:
                    return None  # dropped; the next try is only FAST_INTERVAL away
                data = None
            if data is not None:
                self.failed = False
                self.last = data
                return data
        elif not is_other(self.last) and time.time() - self.last_parse < self.parse_interval:
            return self.last  # nothing new yet (this call was for the achievements)
        return self._read_full()

    def _read_other(self, game):
        if self.other is None or self.other.game != game:
            if self.other:
                self.other.close()
            self.last = None
            self.other = OtherGame(game, self.ra_game, self.client)
            logging.info(f"The DSi is running {games.name(game)}")
        if not self.other.reading:
            self.client.listen(1.0)  # keep up with the hellos, to notice a switch
        data = self.other.read()
        self.failed = data is None and self.ra_game is not None and bool(self.ra_game.runtime)
        self.last = data
        return data

    def _read_bw(self, game):
        """Pokemon Black or White: like Platinum (battlers only during a
        battle), or the game card while the parser doesn't recognise what
        it reads."""
        now = time.time()
        last = self.last if is_bw(self.last) else None
        if last and self.fast_battles and last['battle']['active'] and now - self.last_full < self.BATTLE_FULL_EVERY:
            try:
                ranges = BWParser.quick_ranges(last, games.bw_version(game))
                data = BWParser.apply_quick(last, self.client.read_ranges(ranges, timeout=self.FAST_TIMEOUT, retries=1))
                self.fast_misses = 0
            except (TimeoutError, RuntimeError):
                self.fast_misses += 1
                if self.fast_misses < self.FAST_MISSES:
                    return None  # dropped; the next try is only FAST_INTERVAL away
                data = None
            if data is not None:
                self.failed = False
                self.last = self._with_ra(data, game)
                return self.last
        elif now - self.last_parse < self.parse_interval:
            if last:
                fresh = self._with_ra(last, game)
                if any(fresh[k] != last.get(k) for k in ('progress', 'unlocked', 'latest', 'rich_presence', 'ra_set')):
                    self.last = fresh  # an unlock, or the set arrived: show it now
                return self.last
            return self._read_other(game)  # the game card until the next try
        self.fast_misses = 0
        self.last_parse = now
        try:
            self.ram.clear()
            data = BWParser(self.ram, version=games.bw_version(game)).parse()
        except (TimeoutError, RuntimeError) as e:
            if not self.failed:
                logging.warning(f"Read failed: {e}")
            self.failed = True
            self.last = None
            return None
        if data is None:
            if not self.bw_failed:
                logging.warning(f"{games.name(game)}: its memory doesn't look the way DSiRPC expects"
                                " (another region?), so it gets the game card")
            self.bw_failed = True
            return self._read_other(game)
        if self.bw_failed or not last:
            logging.info(f"Reading {games.name(game)} with its own parser")
        self.bw_failed = False
        if self.other:
            self.other.close()
            self.other = None
        self.failed = False
        self.last = self._with_ra(data, game)
        self.last_full = time.time()
        return self.last

    def _with_ra(self, data, game):
        """A Black/White state with the game card's RetroAchievements keys."""
        if self.bw_started is None:
            self.bw_started = time.time()
        if not self.ra_game:
            return data
        return dict(data, **ra_summary(game, self.ra_game, self.bw_started))

    def _read_full(self):
        self.fast_misses = 0
        self.last_parse = time.time()
        try:
            self.ram.clear()
            data = self.trainers.apply(PlatinumParser(self.ram, self.charmap).parse())
        except (TimeoutError, RuntimeError) as e:
            if not self.failed:
                logging.warning(f"Read failed: {e}")
            self.failed = True
            self.last = None
            return None
        self.failed = data is None
        self.last = data
        self.last_full = time.time()
        return data

    def _read_battlers(self, last):
        """The last state with its battlers read again. None if a full read
        is needed instead."""
        P = PlatinumParser
        ptr = int(last['battle']['pointer'], 16)
        slots = [P.BATTLE_SIDES.index(m['side']) for m in last['battle']['mons']]
        ranges = []
        for i in slots:
            base = ptr + P.BATTLE_OFFSET_MONS + i * P.SIZE_BATTLE_MON
            ranges += [(base + off, n) for off, n in P.BATTLE_MON_FIELDS]
        ranges += [(ptr + P.BATTLE_OFFSET_LAST_MOVES, 8), (P.MUSIC_ID, 2), (P.BATTLE_POINTER, 4)]
        got = self.client.read_ranges(ranges, timeout=self.FAST_TIMEOUT, retries=1)
        last_moves, music, ptr_now = got[-3], got[-2], got[-1]
        if struct.unpack('<I', ptr_now)[0] != ptr or struct.unpack('<H', music)[0] != last['misc']['music_id']:
            return None

        parser = P(b"", self.charmap)
        mons, k = [], 0
        for i in slots:
            raw = bytearray(P.SIZE_BATTLE_MON)
            for off, n in P.BATTLE_MON_FIELDS:
                raw[off:off + n] = got[k]
                k += 1
            mon = parser.battle_mon(bytes(raw), i, last_moves)
            if mon is None:
                return None
            mons.append(mon)
        data = dict(last)
        data['battle'] = dict(last['battle'], mons=mons)
        return data

    def forget_dsi(self):
        """The DSi went quiet: learn its IP again from the next hello (its
        DHCP lease can change), unless it was given with --dsi-ip. The game
        may have been restarted meanwhile, so achievements start over."""
        if not self.pinned_ip:
            self.client.dsi_ip = None
        if self.ra_game:
            self.ra_game.reset()

    def close(self):
        if self.other:
            self.other.close()
        if self.ra_game:
            self.ra_game.close()
        self.client.sock.close()


class FileSource:
    """A RAM dump (e.g. ram_dump.bin). Parsed once, then returned every time.
    `game`: the dump's game code, if it isn't Platinum (e.g. 'AMCE', or
    'IRBO' for Pokemon Black)."""

    def __init__(self, charmap, path, game=None, ra_settings=None):
        with open(path, "rb") as f:
            ram = f.read()
        self.game = {'code': game.upper(), 'version': 0, 'header_crc': 0} if game else None
        if games.is_platinum(self.game):
            self.state = PlatinumParser(ram, charmap).parse()
        elif games.is_bw(self.game):
            ra = RaGame(self.game, ram, None, ra_settings)
            ra.tick()
            self.state = BWParser(ram, version=games.bw_version(self.game)).parse()
            if self.state:
                self.state.update(ra_summary(self.game, ra, time.time()))
            ra.close()
        else:
            ra = RaGame(self.game, ram, None, ra_settings)
            ra.tick()
            self.state = OtherGame(self.game, ra).read()
            ra.close()
        self.status = f"RAM dump {path}"

    def read(self):
        return self.state


def _party_key(mon):
    return (mon.get('species_id'), mon.get('nickname'))


def diff_events(old, new):
    """Events between two states (either may be None). Each event is a dict
    with a 'type' and whatever details fit it."""
    events = []
    if new is None:
        return events
    if old is None:
        return events
    if is_other(old) or is_other(new):
        if is_other(old) != is_other(new) or old.get('game') != new.get('game'):
            events.append({'type': 'game_changed', 'title': new.get('title') or 'Pokemon Platinum'})
        return events
    if old.get('kind') != new.get('kind') or old.get('version') != new.get('version'):
        events.append({'type': 'game_changed', 'title': new.get('title') or 'Pokemon Platinum'})
        return events

    ob, nb = old['battle'], new['battle']
    if nb['active'] and not ob['active']:
        foes = [m for m in nb['mons'] if m['side'].startswith('foe')]
        events.append({'type': 'battle_start', 'music': new['misc']['music_id'],
                       'trainer': nb.get('trainer'), 'foes': foes})
        for m in foes:
            if m['shiny']:
                events.append({'type': 'shiny_encounter', 'mon': m, 'wild': bool(nb.get('wild'))})
    elif ob['active'] and not nb['active']:
        events.append({'type': 'battle_end'})

    if new['location']['map_id'] != old['location']['map_id']:
        events.append({'type': 'map_changed', 'location': new['location']})

    if len(new['badges']) > len(old['badges']):
        events.append({'type': 'badge_earned', 'badges': new['badges']})

    if new['pokedex']['caught'] > old['pokedex']['caught']:
        events.append({'type': 'dex_caught', 'caught': new['pokedex']['caught']})

    # Party members are matched by slot, and only when the same Pokemon is
    # still in that slot (species and nickname).
    for o, n in zip(old['party'], new['party']):
        if _party_key(o) != _party_key(n) or n['egg']:
            continue
        if n['level'] > o['level']:
            events.append({'type': 'level_up', 'mon': n, 'from': o['level']})
        if o['curr_hp'] > 0 and n['curr_hp'] == 0:
            events.append({'type': 'fainted', 'mon': n})
    if [_party_key(m) for m in old['party']] != [_party_key(m) for m in new['party']]:
        events.append({'type': 'party_changed', 'party': new['party']})
    return events


class StateHub:
    """Polls a source on its own thread and keeps the latest Snapshot."""

    def __init__(self, source, interval=2.0, offline_after=30.0):
        self.source = source
        self.interval = interval
        self.offline_after = offline_after
        self._snap = Snapshot(status=getattr(source, 'status', ''))
        self._lock = threading.Lock()
        self._listeners = []
        self._closers = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="StateHub", daemon=True)

    def add_listener(self, fn):
        """fn(snapshot, events) is called from the hub thread after every poll."""
        self._listeners.append(fn)

    def remove_listener(self, fn):
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    def add_closer(self, fn):
        """fn() is called once on the hub thread when the hub stops (for
        connectors whose resources belong to that thread)."""
        self._closers.append(fn)

    def snapshot(self):
        with self._lock:
            s = self._snap
            return Snapshot(s.state, s.online, s.updated, s.status)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)
        close = getattr(self.source, 'close', None)
        if close:
            close()

    def _run(self):
        last_ok = 0.0
        prev = None
        while not self._stop.is_set():
            t0 = time.time()
            try:
                data = self.source.read()
            except Exception as e:  # a bad parse must never kill the hub
                logging.exception(f"Source read crashed: {e}")
                data = None

            events = []
            take = getattr(self.source, 'take_events', None)
            if take:
                events += take()
            with self._lock:
                snap = self._snap
                if data is not None and data is prev and snap.online:
                    # Nothing new: the source was only checking achievements.
                    snap = Snapshot(snap.state, True, snap.updated, getattr(self.source, 'status', ''))
                elif data:
                    if not snap.online:
                        events.append({'type': 'online'})
                    events += diff_events(prev, data)
                    prev = data
                    last_ok = time.time()
                    snap = Snapshot(data, True, last_ok, getattr(self.source, 'status', ''))
                else:
                    online = snap.online and (time.time() - last_ok) < self.offline_after
                    if snap.online and not online:
                        events.append({'type': 'offline'})
                        prev = None
                        forget = getattr(self.source, 'forget_dsi', None)
                        if forget:
                            forget()
                    snap = Snapshot(snap.state, online, snap.updated, getattr(self.source, 'status', ''))
                self._snap = snap

            for fn in list(self._listeners):
                try:
                    fn(snap, events)
                except Exception as e:
                    logging.exception(f"Hub listener failed: {e}")

            delay = self.interval
            next_delay = getattr(self.source, 'next_delay', None)
            if next_delay and next_delay() is not None:
                delay = next_delay()
            self._stop.wait(max(0.0, delay - (time.time() - t0)))

        for fn in self._closers:
            try:
                fn()
            except Exception as e:
                logging.exception(f"Hub closer failed: {e}")
