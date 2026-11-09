"""
mkds_reader.py - Mario Kart DS (AMCE): the racers' places on the course, the
lap and the player's place, read from the DSi's memory for the overlay's race
view (overlay/mkds.py).

Mario Kart DS has no parser of its own otherwise: it's an "other" game
(core/other_game.py) with its RetroAchievements set, and the hub adds this
reader's state to it as 'mkds' while a race (Grand Prix, VS or Time Trial)
is on. Outside one (the menus, Battle, Missions) it's None, and the game card
shows.

Where things are, in the US version (offsets into main RAM, 0x02000000):

    0x000B54    MAIN, a pointer to the game's main block (0x0216F320 on US;
                MKDasher's mkds-hud-lua, scripts/Memory.lua, and Chris-B33's
                mkds-lua-ml-model, src/emulator/mem.lua, both start there).
                The rest are MAIN + offset:
    +0xB9D8     pointer to racer 0, the player (0 outside a race). The racers
                are 0x5A8 bytes each, back to back: mkds-lua-ml-model reads
                0x5A8 bytes there, and libretro-database's "Mario Kart DS
                (USA).cht" ("No CPU's Characters in Karts v2.0") walks seven
                more with that stride. Each one's position is s32 20.12 fixed
                point at +0x80 (x), +0x84 (height) and +0x88 (z), the ground
                plane being x and z (mkds-hud-lua's Program.lua reads them so).
    +0x62DC     pointer to the race status, 0x8C bytes a racer in the same
                order (the cheat "Force 3rd Lap - Wi-Fi" writes the lap at
                +0x38, +0xC4, +0x150, +0x1DC). Each has timers (u16 ms, then
                a minutes byte and a seconds byte) at +0x00 (total), +0x08
                (this race) and +0x18 (this lap), the lap at +0x38, the last
                checkpoint passed at +0x46 (mkds-lua-ml-model heads for the
                one after it) and the last key checkpoint at +0x48.
    +0x62E0     pointer to the course's data: its checkpoints' count (u16) at
                +0x48 and a pointer to them at +0x44 (mkds-lua-ml-model,
                src/emulator/checkpoints.lua). A checkpoint is 0x24 bytes: a
                line across the road from (x1, z1) to (x2, z2), s32 20.12 at
                +0, +4, +8, +0xC, and its key checkpoint number (s16) at
                +0x20. Checkpoint 0 is the finish line. They're the course
                file's own (data/Course/<course>.carc, course_map.nkm's CPOI
                section has the same 0x24-byte entries), so tools/mkds_maps.py
                lines the course art up with them from the ROM.
    +0xC53C     the player's lap, +0xC544 the race's laps, +0xB96C set once
                the player has finished (mkds-hud-lua's Memory.lua)
    +0xC90C     pointer to the racers' items, 0x210 bytes a racer: the item
                held (ITEMS) at +0x4C, how many at +0x54 (mkds-hud-lua's
                Program.lua reads +0x54 there; the cheat "CPU's Can't Get
                Items v2.0" writes 0x13, none, at +0x25C for racers 1-7, and
                "Master Code - Offline v3.0" an item at +0x4C and 1 at +0x54)

And at fixed addresses (RetroAchievements' code notes and rich presence for
the game, RA game 12711):

    0x3CDCD8    the course (COURSES): the game's course table (arm9,
                0x02154288 on US, its name pointers in ID order) is this
                minus one; the code notes' list agrees but for 0x15, which is
                the table's unused test_circle, not Banshee Boardwalk (0x17)
    0x3CDCDC    the cup, 0x3CDCE0 the mode (MODES), 0x3CDCE8 the class
                (0 50cc, 1 100cc, 2 150cc), 0x3CDD2F 1 for mirror
    0x3CDD40    the player's character (CHARACTERS), 0x3CDD44 the kart
    0x368754    the player's place, 1 to 8 (the code notes). Not used: on a
                DSi under nds-bootstrap it reads the same whatever the place
                (08 all race at DK Pass in the log of 2026-11-08; 7C and FB
                in others), and taken as the player's place it put them
                last and everyone else a place up. probe() still logs it, and
                looks for where the game keeps the places.
    0x2AC39C    pointer to the Grand Prix standings: the player's points so
                far in the cup at +0x30 (the code notes, and the set's
                3-star cup achievements, which want 40 there: four wins)

The other drivers' characters follow the player's, 0x30 bytes apart
(DRIVERS): libretro-database's cheat "All Colored CPU Shy Guy's With
Matching Karts" writes Shy Guy (0x0C) at 0x3CDD70, 0x3CDDA0, ... 0x3CDE90 and
their karts 4 bytes on, and the cheat at 0x3CDD48 + 0x30 n (unnamed, cheat70
in the file) pairs each of those entries with racer n's block (+0x4C, then
+0x5F4 ...), so entry n is racer n.

Nothing known gives the other racers' places, so they come from how far
round each racer is: laps, the last checkpoint passed and how far it's got
toward the next (progress()), the player's too. 'place' is the player's
place in 'order', so the ranking and the place shown never disagree. (docs/mkds-console-guide.md
checks both on the console.)

read() returns None outside a race, else:

    {'course': 0x14, 'course_name': 'Figure-8 Circuit', 'mode': 'Grand Prix',
     'cup': 'Mushroom', 'cc': '150cc', 'mirror': False,
     'lap': 2, 'laps': 3, 'place': 3, 'finished': False, 'time_ms': 83456,
     'character': 'Mario' (the player's), 'kart': 0,
     'item': {'id': 0x0B, 'name': 'Triple Red Shells', 'count': 3} or None
     (nothing held, or not read yet), 'cup_points': 18 (Grand Prix only, else
     None),
     'racers': [{'slot': 0, 'player': True, 'character': 'Mario' (None: not one we know),
                 'x': 1234.5, 'z': -321.0, 'y': 850.0 (height), 'lap': 2, 'checkpoint': 7,
                 'progress': 59.4, 'place': 3}, ...]  (slot order),
     'order': [slot, ...] first place first,
     'checkpoints': ((x1, z1, x2, z2, key), ...) the course's, or ()}
"""

import logging
import struct

RAM = 0x02000000
RAM_END = 0x02400000
MAIN_PTR = 0x02000B54
MAIN_US = 0x0216F320

RACERS_AT = 0xB9D8          # MAIN + this: pointer to racer 0
RACER_SIZE = 0x5A8
RACER_POS = 0x80            # x, height, z (s32 20.12)
STATUS_AT = 0x62DC          # MAIN + this: pointer to the race status (and the course data's after it)
STATUS_SIZE = 0x8C
STATUS_TIMER = 0x08         # this race's timer
STATUS_LAP = 0x38           # the status bytes read: +0x38 (lap) to +0x4A
STATUS_READ = 0x12
STATUS_CHECKPOINT = 0x46 - STATUS_LAP    # (offsets into what's read)
STATUS_KEY = 0x48 - STATUS_LAP
COURSE_DATA_AT = 0x62E0
CP_POINTER, CP_COUNT = 0x44, 0x48
CP_SIZE = 0x24
CP_KEY = 0x20
PLAYER_LAP_AT = 0xC53C      # lap, then the race's laps at +8
FINISHED_AT = 0xB96C

SETUP = 0x023CDCD8          # course (+0), cup (+4), mode (+8), class (+0x10)
SETUP_LEN = 0x11
PLAYER = 0x023CDD2F         # mirror (+0), character (+0x11), kart (+0x15)
PLAYER_LEN = 0x19
PLACE = 0x02368754
DRIVERS = 0x023CDD40        # driver n's character: DRIVERS + n * DRIVER_SIZE (the player's is n = 0)
DRIVER_SIZE = 0x30
ITEMS_AT = 0xC90C           # MAIN + this: pointer to the racers' items
ITEM_READ = (0x4C, 9)       # the player's: the item (+0x4C) to the count (+0x54)
ITEM_COUNT = 0x54 - 0x4C
STANDINGS_PTR = 0x022AC39C  # pointer to the Grand Prix standings
CUP_POINTS = 0x30           # ... the player's points in the cup there

MAX_RACERS = 8
FIXED = 4096.0              # 20.12

MODES = {0: "Grand Prix", 1: "Time Trial", 3: "VS"}          # (2 Battle, 4 Mission: not read)
RACERS_IN = {"Grand Prix": 8, "VS": 8, "Time Trial": 1}
CUPS = ["Mushroom", "Flower", "Star", "Special", "Shell", "Banana", "Leaf", "Lightning"]
CLASSES = ["50cc", "100cc", "150cc"]
# The code notes' order (0x3CDD40), Shy Guy after them (Download Play)
CHARACTERS = ["Mario", "Donkey Kong", "Toad", "Bowser", "Peach", "Wario", "Yoshi", "Luigi",
              "Dry Bones", "Daisy", "Waluigi", "R.O.B.", "Shy Guy"]
SHORT_NAMES = {"Donkey Kong": "DK", "Dry Bones": "DRYBNS", "Waluigi": "WALUIGI", "Shy Guy": "SHYGUY"}
# The item byte. From libretro-database's per-item cheats (the byte each has
# the master code store): 0x00, 0x02, 0x06-0x08, 0x0B, 0x0C, 0x0E-0x10 and
# 0x13 (none). The rest fill the gaps in the game's usual order and are
# unverified (docs/mkds-console-guide.md): 0x01, 0x03-0x05, 0x09, 0x0A, 0x0D.
ITEMS = {
    0x00: "Green Shell", 0x01: "Red Shell", 0x02: "Banana", 0x03: "Fake Item Box", 0x04: "Mushroom",
    0x05: "Triple Mushrooms", 0x06: "Bob-omb", 0x07: "Spiny Shell", 0x08: "Lightning",
    0x09: "Triple Green Shells", 0x0A: "Triple Bananas", 0x0B: "Triple Red Shells", 0x0C: "Star",
    0x0D: "Golden Mushroom", 0x0E: "Bullet Bill", 0x0F: "Blooper", 0x10: "Boo",
}
NO_ITEM = 0x13

# The course byte -> (name, the course file in data/Course/). The race courses
# are 0x01-0x28 (0x02-0x08 and 0x15 are unused or test courses), the battle
# courses 0x2A-0x2F.
COURSES = {
    0x01: ("GCN Yoshi Circuit", "old_yoshi_gc"),
    0x09: ("GCN Baby Park", "old_baby_gc"),
    0x0A: ("SNES Mario Circuit 1", "old_mario_sfc"),
    0x0B: ("N64 Moo Moo Farm", "old_momo_64"),
    0x0C: ("GBA Bowser Castle 2", "old_koopa_agb"),
    0x0D: ("GBA Peach Circuit", "old_peach_agb"),
    0x0E: ("GCN Luigi Circuit", "old_luigi_gc"),
    0x0F: ("SNES Koopa Beach 2", "old_noko_sfc"),
    0x10: ("N64 Frappe Snowland", "old_frappe_64"),
    0x11: ("Tick-Tock Clock", "clock_course"),
    0x12: ("Luigi's Mansion", "mansion_course"),
    0x13: ("Airship Fortress", "airship_course"),
    0x14: ("Figure-8 Circuit", "cross_course"),
    0x16: ("Yoshi Falls", "bank_course"),
    0x17: ("N64 Banshee Boardwalk", "old_hyudoro_64"),
    0x18: ("Shroom Ridge", "ridge_course"),
    0x19: ("Mario Circuit", "mario_course"),
    0x1A: ("Peach Gardens", "garden_course"),
    0x1B: ("Desert Hills", "desert_course"),
    0x1C: ("Delfino Square", "town_course"),
    0x1D: ("Rainbow Road", "rainbow_course"),
    0x1E: ("DK Pass", "snow_course"),
    0x1F: ("Cheep Cheep Beach", "beach_course"),
    0x20: ("Bowser's Castle", "koopa_course"),
    0x21: ("Waluigi Pinball", "pinball_course"),
    0x22: ("Wario Stadium", "stadium_course"),
    0x23: ("SNES Donut Plains 1", "old_donut_sfc"),
    0x24: ("N64 Choco Mountain", "old_choco_64"),
    0x25: ("GBA Luigi Circuit", "old_luigi_agb"),
    0x26: ("GCN Mushroom Bridge", "old_kinoko_gc"),
    0x27: ("SNES Choco Island 2", "old_choco_sfc"),
    0x28: ("GBA Sky Garden", "old_sky_agb"),
}


def _ptr(raw):
    """A pointer into main RAM, or 0 (anything else: not one)."""
    v = struct.unpack("<I", raw[:4])[0]
    return v if RAM <= v < RAM_END else 0


def _fixed(raw, at):
    return struct.unpack_from("<i", raw, at)[0] / FIXED


def _timer(raw):
    """A race timer (u16 ms, minutes, seconds) -> milliseconds."""
    ms, minutes, seconds = struct.unpack("<HBB", raw[:4])
    return (minutes * 60 + seconds) * 1000 + ms


def item_of(raw):
    """The item bytes (+0x4C to +0x54) -> {'id', 'name', 'count'}, or None
    when nothing's held (0x13, or an item we don't know)."""
    n = raw[0]
    if n not in ITEMS:
        return None
    count = raw[ITEM_COUNT]
    return {'id': n, 'name': ITEMS[n], 'count': count if 1 <= count <= 3 else 1}


def character_name(n):
    return CHARACTERS[n] if 0 <= n < len(CHARACTERS) else None


def short_name(name):
    """A racer's name for the ranking: 'MARIO', 'DK', 'R.O.B.'."""
    return SHORT_NAMES.get(name, name).upper() if name else None


def checkpoints_of(raw, count):
    """The checkpoint array's bytes -> ((x1, z1, x2, z2, key), ...)."""
    out = []
    for i in range(count):
        e = raw[i * CP_SIZE:(i + 1) * CP_SIZE]
        if len(e) < CP_SIZE:
            break
        x1, z1, x2, z2 = (v / FIXED for v in struct.unpack_from("<4i", e))
        out.append((x1, z1, x2, z2, struct.unpack_from("<h", e, CP_KEY)[0]))
    return tuple(out)


def midpoints(checkpoints):
    """The middle of each checkpoint's line: the course's shape, in order."""
    return [((x1 + x2) / 2, (z1 + z2) / 2) for x1, z1, x2, z2, _ in checkpoints]


def progress(lap, checkpoint, x, z, mids):
    """How far round a racer is, in checkpoints: laps x the checkpoints, plus
    the last one passed, plus how far along the way to the next one it is
    (-1 to 1: from the line between the two middles; before the first
    checkpoint the game has it at -1 or the last). Bigger is further ahead."""
    n = len(mids)
    if not n:
        return float(lap)
    cp = checkpoint % n
    (ax, az), (bx, bz) = mids[cp], mids[(cp + 1) % n]
    dx, dz = bx - ax, bz - az
    seg = dx * dx + dz * dz
    t = ((x - ax) * dx + (z - az) * dz) / seg if seg else 0.0
    return lap * n + checkpoint + max(-1.0, min(1.0, t))


def rank_player(racers, game_place=None):
    """(the order, the player's place in it): with the game's own place for
    the player when it's given (placings()), else as worked out, so the
    place shown is always the player's place in the ranking."""
    order = rank(racers, game_place)
    return order, next((r['place'] for r in racers if r['player']), None)


def rank(racers, player_place=None):
    """Sets each racer's 'place' (placings()) and returns the order."""
    order = placings(racers, player_place)
    by_slot = {r['slot']: r for r in racers}
    for i, slot in enumerate(order):
        by_slot[slot]['place'] = i + 1
    return order


def placings(racers, player_place=None):
    """The racers' slots, first place first: by progress, with the player
    (slot 0) put at `player_place` (the game's own, 1-based) when it's given
    and makes sense."""
    order = [r['slot'] for r in sorted(racers, key=lambda r: (-r['progress'], r['slot']))]
    if player_place and 0 in order and 1 <= player_place <= len(order):
        order.remove(0)
        order.insert(player_place - 1, 0)
    return order


PROBE_AT_MS = (20000, 60000)   # probe() a race this far in (its timer), once each


class MkdsReader:
    """Reads a race a few times a second in two requests: the pointers, the
    setup and every racer's position in one, their laps and checkpoints in
    the other. The pointers each read gets are the ones the read after uses
    (a race's stay put), and the checkpoints are read once a course, so a
    pointer that's moved costs one read with nothing in it. The game does
    move them as a race starts (the course's intro, then the countdown: the
    first console test had the checkpoints read twice, 10 s apart), which the
    hub rides out (core/hub.py's MKDS_HOLD_S). `why` says why the last read
    had no race; a change of reason is logged."""

    def __init__(self):
        self.main = None
        self.racers_at = 0     # pointers as the last read had them
        self.status_at = 0
        self.course_at = 0
        self.checkpoints = ()
        self.cp_key = None     # (course data pointer, course) the checkpoints are for
        self.why = None        # why the last read had no race (None: it had one)
        self.probed = set()    # PROBE_AT_MS done this race
        self.items_at = 0      # the items' and standings' pointers, as the last read had them
        self.standings_at = 0
        self.characters = ()   # the other drivers' character numbers (1-7), read with the checkpoints

    def ranges(self, n=MAX_RACERS):
        """What a read reads, in parse()'s order."""
        main = self.main
        out = [(MAIN_PTR, 4), (main + STATUS_AT, 8), (main + RACERS_AT, 4), (SETUP, SETUP_LEN),
               (PLAYER, PLAYER_LEN), (PLACE, 1), (main + PLAYER_LAP_AT, 12), (main + FINISHED_AT, 1)]
        if self.racers_at and self.status_at:
            out += [(self.racers_at + i * RACER_SIZE + RACER_POS, 12) for i in range(n)]
            out += [(self.status_at + i * STATUS_SIZE + STATUS_LAP, STATUS_READ) for i in range(n)]
            out.append((self.status_at + STATUS_TIMER, 4))
            # (a pointer read here is used by the next read; until then, a stand-in)
            out += [(main + ITEMS_AT, 4), ((self.items_at or MAIN_PTR) + ITEM_READ[0], ITEM_READ[1]),
                    (STANDINGS_PTR, 4), ((self.standings_at or MAIN_PTR) + CUP_POINTS, 1)]
        return out

    def read(self, client, timeout=None):
        """The race now, or None outside one. Raises TimeoutError or
        RuntimeError if the DSi doesn't answer."""
        if self.main is None:
            main = _ptr(client.read_ranges([(MAIN_PTR, 4)], timeout=timeout, retries=1)[0])
            if not main:
                return None
            self.main = main
        chunks = client.read_ranges(self.ranges(), timeout=timeout, retries=1)
        was = self.why
        state = self.parse(chunks)
        if self.why != was and self.why:
            logging.info(f"Mario Kart DS: no race in this read ({self.why})")
        if state is not None and self.cp_key != (self.course_at, state['course']):
            self.probed = set()
            drivers = client.read_ranges([(DRIVERS + i * DRIVER_SIZE, 1) for i in range(1, MAX_RACERS)],
                                         timeout=timeout, retries=1)
            self.characters = tuple(d[0] for d in drivers)
            for r in state['racers'][1:]:
                r['character'] = character_name(self.characters[r['slot'] - 1])
            self.checkpoints = self._checkpoints(client, timeout)
            self.cp_key = (self.course_at, state['course'])
            state['checkpoints'] = self.checkpoints
            mids = midpoints(self.checkpoints)
            if mids:       # (docs/mkds-console-guide.md: how the map's lined up with the console's course)
                logging.info(f"Mario Kart DS: {state['course_name']}{' (mirror)' if state['mirror'] else ''}, "
                             f"{len(mids)} checkpoints, the finish line's middle at ({mids[0][0]:.0f}, {mids[0][1]:.0f})")
            for r in state['racers']:
                r['progress'] = progress(r['lap'], r['checkpoint'], r['x'], r['z'], mids)
            state['order'], state['place'] = rank_player(state['racers'])
        due = [ms for ms in PROBE_AT_MS if ms not in self.probed and state and state['time_ms'] >= ms]
        if due:
            self.probed.update(due)
            try:
                self.probe(client, state, timeout)
            except (TimeoutError, RuntimeError) as e:
                logging.debug(f"Mario Kart DS: place probe failed ({e})")
        return state

    def probe(self, client, state, timeout=None):
        """Logs where the game might keep the racers' places, to find one
        that works on the console (docs/mkds-console-guide.md): the bytes
        around the code notes' place address, and every offset in the race
        status entries whose bytes across the racers are a ranking (1 to n
        or 0 to n-1), with how many agree with the order worked out here.
        Twice a race (PROBE_AT_MS), a few requests each."""
        slots = [r['slot'] for r in state['racers']]
        n = len(slots)
        if n < 2 or not self.status_at:
            return
        ranges = [(PLACE - 4, 12)] + [(self.status_at + i * STATUS_SIZE, STATUS_SIZE) for i in slots]
        got = client.read_ranges(ranges, timeout=timeout, retries=1)
        around, entries = got[0], got[1:]
        places = {r['slot']: r['place'] for r in state['racers']}
        found = []
        for off in range(STATUS_SIZE):
            vals = [e[off] for e in entries]
            for base in (1, 0):
                if sorted(vals) == list(range(base, base + n)):
                    agree = sum(1 for slot, v in zip(slots, vals) if v - base + 1 == places[slot])
                    found.append(f"+0x{off:02X} ({'1' if base else '0'}-based, {agree} of {n} agree)")
        logging.info(f"Mario Kart DS: place probe at {state['time_ms'] / 1000:.1f} s: the place byte "
                     f"0x{PLACE:08X} reads {around[4]:02X} (0x{PLACE - 4:08X}: {around.hex(' ')}); "
                     f"worked-out order {[s for s in state['order']]}; race status bytes that rank the "
                     f"racers: {', '.join(found) or 'none'}")

    def _checkpoints(self, client, timeout):
        if not self.course_at:
            return ()
        head = client.read_ranges([(self.course_at + CP_POINTER, 8)], timeout=timeout, retries=1)[0]
        at, count = _ptr(head[:4]), struct.unpack_from("<H", head, 4)[0]
        if not at or not 0 < count < 256:
            return ()
        return checkpoints_of(client.read_ranges([(at, count * CP_SIZE)], timeout=timeout, retries=1)[0], count)

    def parse(self, chunks):
        """ranges()' bytes -> the state above, or None outside a race (or
        when a pointer's moved since the ranges were made: the next read has
        it)."""
        main_raw, status, racers, setup, player, _place, laps, finished = chunks[:8]   # (_place: see PLACE)
        rest = list(chunks[8:])
        had = (self.racers_at, self.status_at)
        main = _ptr(main_raw)
        if main != self.main:
            self.main = main or None
            self.racers_at = self.status_at = self.course_at = 0
            self.why = "the main pointer changed"
            return None
        self.status_at, self.course_at = _ptr(status[:4]), _ptr(status[4:8])
        self.racers_at = _ptr(racers)
        mode = MODES.get(setup[8])
        course = setup[0]
        for bad, why in ((not self.racers_at, "no racers"), (not self.status_at, "no race status"),
                         (not mode, f"mode {setup[8]}"), (course not in COURSES, f"course 0x{course:02X}")):
            if bad:
                self.why = why
                return None
        if had != (self.racers_at, self.status_at) or len(rest) < 2 * MAX_RACERS + 5:
            self.why = "the racers moved"
            return None
        self.why = None
        positions, statuses = rest[:MAX_RACERS], rest[MAX_RACERS:2 * MAX_RACERS]
        timer, items_ptr, item, standings_ptr, points = rest[2 * MAX_RACERS:2 * MAX_RACERS + 5]
        item_ok = self.items_at and _ptr(items_ptr) == self.items_at
        points_ok = self.standings_at and _ptr(standings_ptr) == self.standings_at
        self.items_at, self.standings_at = _ptr(items_ptr), _ptr(standings_ptr)
        n = RACERS_IN[mode]
        me = character_name(player[0x11])
        mids = midpoints(self.checkpoints)
        racers = []
        for i in range(n):
            pos, st = positions[i], statuses[i]
            x, z = _fixed(pos, 0), _fixed(pos, 8)
            if i and x == 0 and z == 0:
                continue                                    # (no one in that slot)
            lap = struct.unpack_from("<b", st, 0)[0]
            cp = struct.unpack_from("<b", st, STATUS_CHECKPOINT)[0]
            char = me if i == 0 else character_name(self.characters[i - 1]) if self.characters else None
            racers.append({'slot': i, 'player': i == 0, 'character': char, 'x': x, 'z': z, 'y': _fixed(pos, 4),
                           'lap': lap, 'checkpoint': cp, 'progress': progress(lap, cp, x, z, mids),
                           'place': None})
        order, player_place = rank_player(racers)
        lap, total = struct.unpack_from("<b", laps, 0)[0], laps[8]
        return {
            'course': course, 'course_name': COURSES[course][0], 'mode': mode,
            'cup': CUPS[setup[4]] if setup[4] < len(CUPS) else None,
            'cc': CLASSES[setup[0x10]] if setup[0x10] < len(CLASSES) else None,
            'mirror': player[0] == 1, 'lap': lap, 'laps': total if 0 < total < 10 else 3,
            'place': player_place,
            'finished': finished[0] != 0, 'time_ms': _timer(timer),
            'character': me, 'kart': player[0x15], 'racers': racers, 'order': order,
            'item': item_of(item) if item_ok else None,
            'cup_points': points[0] if points_ok and mode == "Grand Prix" and points[0] <= 40 else None,
            'checkpoints': self.checkpoints if self.cp_key and self.cp_key[1] == course else (),
        }
