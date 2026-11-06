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

And at fixed addresses (RetroAchievements' code notes and rich presence for
the game, RA game 12711):

    0x3CDCD8    the course (COURSES): the game's course table (arm9,
                0x02154288 on US, its name pointers in ID order) is this
                minus one; the code notes' list agrees but for 0x15, which is
                the table's unused test_circle, not Banshee Boardwalk (0x17)
    0x3CDCDC    the cup, 0x3CDCE0 the mode (MODES), 0x3CDCE8 the class
                (0 50cc, 1 100cc, 2 150cc), 0x3CDD2F 1 for mirror
    0x3CDD40    the player's character (CHARACTERS), 0x3CDD44 the kart
    0x368754    the player's place, 1 to 8

The other drivers' characters follow the player's, 0x30 bytes apart
(DRIVERS): libretro-database's cheat "All Colored CPU Shy Guy's With
Matching Karts" writes Shy Guy (0x0C) at 0x3CDD70, 0x3CDDA0, ... 0x3CDE90 and
their karts 4 bytes on, and the cheat at 0x3CDD48 + 0x30 n (unnamed, cheat70
in the file) pairs each of those entries with racer n's block (+0x4C, then
+0x5F4 ...), so entry n is racer n.

Nothing known gives the other racers' places, so they come from how far
round each racer is: laps, the last checkpoint passed and how far it's got
toward the next (progress()). The player's own place, which the game keeps,
wins: the player goes in at that place and the others keep their order around
them. (docs/mkds-console-guide.md checks both on the console.)

read() returns None outside a race, else:

    {'course': 0x14, 'course_name': 'Figure-8 Circuit', 'mode': 'Grand Prix',
     'cup': 'Mushroom', 'cc': '150cc', 'mirror': False,
     'lap': 2, 'laps': 3, 'place': 3, 'finished': False, 'time_ms': 83456,
     'character': 'Mario' (the player's), 'kart': 0,
     'racers': [{'slot': 0, 'player': True, 'character': 'Mario' (None: not one we know),
                 'x': 1234.5, 'z': -321.0, 'lap': 2, 'checkpoint': 7,
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


class MkdsReader:
    """Reads a race a few times a second in two requests: the pointers, the
    setup and every racer's position in one, their laps and checkpoints in
    the other. The pointers each read gets are the ones the read after uses
    (a race's stay put), and the checkpoints are read once a course, so a
    pointer that's moved costs one read with nothing in it."""

    def __init__(self):
        self.main = None
        self.racers_at = 0     # pointers as the last read had them
        self.status_at = 0
        self.course_at = 0
        self.checkpoints = ()
        self.cp_key = None     # (course data pointer, course) the checkpoints are for

    def ranges(self, n=MAX_RACERS):
        """What a read reads, in parse()'s order."""
        main = self.main
        out = [(MAIN_PTR, 4), (main + STATUS_AT, 8), (main + RACERS_AT, 4), (SETUP, SETUP_LEN),
               (PLAYER, PLAYER_LEN), (PLACE, 1), (main + PLAYER_LAP_AT, 12), (main + FINISHED_AT, 1)]
        if self.racers_at and self.status_at:
            out += [(self.racers_at + i * RACER_SIZE + RACER_POS, 12) for i in range(n)]
            out += [(self.status_at + i * STATUS_SIZE + STATUS_LAP, STATUS_READ) for i in range(n)]
            out.append((self.status_at + STATUS_TIMER, 4))
            out += [(DRIVERS + i * DRIVER_SIZE, 1) for i in range(1, n)]
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
        state = self.parse(chunks)
        if state is not None and self.cp_key != (self.course_at, state['course']):
            self.checkpoints = self._checkpoints(client, timeout)
            self.cp_key = (self.course_at, state['course'])
            state['checkpoints'] = self.checkpoints
            mids = midpoints(self.checkpoints)
            if mids:       # (docs/mkds-console-guide.md: how the map's lined up with the console's course)
                logging.info(f"Mario Kart DS: {state['course_name']}{' (mirror)' if state['mirror'] else ''}, "
                             f"{len(mids)} checkpoints, the finish line's middle at ({mids[0][0]:.0f}, {mids[0][1]:.0f})")
            for r in state['racers']:
                r['progress'] = progress(r['lap'], r['checkpoint'], r['x'], r['z'], mids)
            state['order'] = rank(state['racers'], state['place'])
        return state

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
        main_raw, status, racers, setup, player, place, laps, finished = chunks[:8]
        rest = list(chunks[8:])
        had = (self.racers_at, self.status_at)
        main = _ptr(main_raw)
        if main != self.main:
            self.main = main or None
            self.racers_at = self.status_at = self.course_at = 0
            return None
        self.status_at, self.course_at = _ptr(status[:4]), _ptr(status[4:8])
        self.racers_at = _ptr(racers)
        mode = MODES.get(setup[8])
        course = setup[0]
        if not (self.racers_at and self.status_at and mode and course in COURSES):
            return None
        if had != (self.racers_at, self.status_at) or len(rest) < 3 * MAX_RACERS:
            return None
        positions, statuses = rest[:MAX_RACERS], rest[MAX_RACERS:2 * MAX_RACERS]
        timer, drivers = rest[2 * MAX_RACERS], rest[2 * MAX_RACERS + 1:]
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
            char = me if i == 0 else character_name(drivers[i - 1][0])
            racers.append({'slot': i, 'player': i == 0, 'character': char, 'x': x, 'z': z,
                           'lap': lap, 'checkpoint': cp, 'progress': progress(lap, cp, x, z, mids),
                           'place': None})
        player_place = place[0] if 1 <= place[0] <= len(racers) else None
        order = rank(racers, player_place)
        lap, total = struct.unpack_from("<b", laps, 0)[0], laps[8]
        return {
            'course': course, 'course_name': COURSES[course][0], 'mode': mode,
            'cup': CUPS[setup[4]] if setup[4] < len(CUPS) else None,
            'cc': CLASSES[setup[0x10]] if setup[0x10] < len(CLASSES) else None,
            'mirror': player[0] == 1, 'lap': lap, 'laps': total if 0 < total < 10 else 3,
            'place': player_place, 'finished': finished[0] != 0, 'time_ms': _timer(timer),
            'character': me, 'kart': player[0x15], 'racers': racers, 'order': order,
            'checkpoints': self.checkpoints if self.cp_key and self.cp_key[1] == course else (),
        }
