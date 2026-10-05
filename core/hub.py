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
status text, forget_dsi() and next_delay() (seconds until the next read, to
override the hub's interval). A state is either Platinum's parsed dict (see
core/parser.py; it has no 'kind') or, for any other game, the dict from
core/other_game.py ({'kind': 'other', ...}); is_other() tells them apart.
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
from .other_game import OtherGame
from .parser import PlatinumParser, TrainerMemory


def is_other(state):
    """True for the state of a game without its own parser (core/other_game.py)."""
    return bool(state) and state.get('kind') == 'other'


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

    Any other game is followed with core/other_game.py: its name, and its
    RetroAchievements rich presence if there's a set for it. `racache` is an
    RA emulator's folder to look for sets in (see core/ra_cache.py)."""

    FAST_INTERVAL = 0.3
    FAST_TIMEOUT = 0.6
    FAST_MISSES = 5
    BATTLE_FULL_EVERY = 60.0

    def __init__(self, charmap, port=4244, dsi_ip=None, timeout=1.0, racache=None):
        from .dsirpc_client import DSiClient
        from .dsi_memory import DsiRam
        self.charmap = charmap
        self.racache = racache
        self.fast_battles = True
        self.port = port
        self.pinned_ip = dsi_ip
        self.client = DSiClient(port=port, dsi_ip=dsi_ip, timeout=timeout)
        self.ram = DsiRam(self.client)
        self.failed = False
        self.trainers = TrainerMemory()
        self.last = None        # the latest state returned
        self.last_full = 0.0    # time.time() of the last full read
        self.fast_misses = 0
        self.other = None       # OtherGame while the DSi runs something other than Platinum

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

    def _in_battle(self):
        return bool(self.last and not is_other(self.last) and self.last['battle']['active'])

    def next_delay(self):
        return self.FAST_INTERVAL if self.fast_battles and self._in_battle() else None

    def read(self):
        if self.client.dsi_ip is None:
            # Short wait so the hub thread can still be stopped quickly.
            if not self.client.wait_for_dsi(max_wait=1.0):
                return None
        # The Platinum parser only makes sense on Platinum.
        game = self.client.game
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
        return self._read_full()

    def _read_other(self, game):
        if self.other is None or self.other.game != game:
            if self.other:
                self.other.close()
            self.last = None
            self.other = OtherGame(game, self.ram, self.client, racache=self.racache)
            logging.info(f"The DSi is running {self.other.describe()}")
        if not self.other.reader:
            self.client.listen(1.0)  # keep up with the hellos, to notice a switch
        try:
            self.ram.clear()
            data = self.other.read()
        except (TimeoutError, RuntimeError) as e:
            if not self.failed:
                logging.warning(f"Read failed: {e}")
            self.failed = True
            return None
        self.failed = False
        self.last = data
        return data

    def _read_full(self):
        self.fast_misses = 0
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
        DHCP lease can change), unless it was given with --dsi-ip."""
        if not self.pinned_ip:
            self.client.dsi_ip = None

    def close(self):
        if self.other:
            self.other.close()
        self.client.sock.close()


class FileSource:
    """A RAM dump (e.g. ram_dump.bin). Parsed once, then returned every time.
    `game`: the dump's game code, if it isn't Platinum (e.g. 'AMCE')."""

    def __init__(self, charmap, path, game=None):
        with open(path, "rb") as f:
            ram = f.read()
        self.game = {'code': game.upper(), 'version': 0, 'header_crc': 0} if game else None
        if games.is_platinum(self.game):
            self.state = PlatinumParser(ram, charmap).parse()
        else:
            other = OtherGame(self.game, ram)
            self.state = other.read()
            other.close()
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
            with self._lock:
                snap = self._snap
                if data:
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
