"""
offline.py - the files and messages for playing without DSiRPC nearby
(offline play): achievements are kept on the console's SD card and handed to
DSiRPC the next time the launcher finds it. DSiRPC does all the work; the
console only stores what it's given and what it unlocked.

On the SD card, in the launcher's folder (the launcher writes them; see
launcher/source/sync.c):

    RPCUNLK.BIN           unlocks waiting for DSiRPC (written in game by
                          nds-bootstrap's rpcprobe/probe_ach.c; read and
                          cleared by the launcher)
    <launcher>/sets/CODE.DRS
                          each game's achievements, from DSiRPC (build_set())
    RPCSET.BIN            the set of the game being started (a copy, so the
                          in-game side only needs a fixed name);
                          nds-bootstrap's rpcprobe/probe_ach.c checks it

RPCUNLK.BIN (version 1): 4096 bytes, 256 slots of 16 bytes, little-endian.
Slot 0 is the header: "DRUL", u16 version, u16 slot size (16), u16 slot
count (256), 6 bytes reserved. Slots 1-255 are unlocks:

    u32 achievement ID (0: empty slot)
    4   game code
    u32 when: seconds since 2000-01-01 00:00 by the console's clock (local time)
    u16 sequence number
    u16 check: 0x5AA5 + the sum of the first 7 little-endian u16s, so a slot
        that was only partly written is ignored

Each unlock is one slot, written on its own, so there's never a half-written
list; the launcher zeroes the slots once DSiRPC has them. In game, unlocks go
after the last slot in use (sequence number = slot number, less that start's
shadow notes), dated by the
console's clock, read when the achievement unlocks (when it can't be read just
then: its last reading, or the launcher's time= in RPCHAND.TXT, plus the
VBlanks since, which stop while it sleeps); 0 if there was no clock.
Achievements already in the file
aren't checked again. Unlocks DSiRPC made itself (playing online) come back
this way too; engine.py leaves out the ones it knows about.

One slot isn't an unlock: each start of a game keeps its playtime in the
next free slot, rewritten each minute (achievement ID PLAYTIME_ID, the game's
code, its seconds in place of when). The launcher adds it to the game's
playtime as it starts and clears it before any sync, so DSiRPC never gets
one; if it does, it's left out.

Nor are the shadow check's notes (IDs from RESERVED_IDS up aren't unlocks).
The console checks its frame lane a second time from every 8th sample, the
way the pass lane sees memory (rpcprobe/probe_ach.c, "The shadow check"),
and notes each achievement it decides on: PROVEN_ID when the two came out
differently (it needs the frame lane), CLEAN_ID when its memory changed a
while with no difference. The note's slot has the achievement's ID in place
of when, and sequence number 0. read_shadow_notes() reads them; the launcher
counts and clears them with the unlocks (count_slots()), and engine.py keeps
them in ra/cache/frame_needs.json (core/frame_needs.py).

CODE.DRS (an offline set, version 5), little-endian:

    header (64 bytes): "DRSE", u16 version (5), u16 header size (64),
        4 game code, u32 RA game ID, u32 stamp (CRC-32 of everything after
        the header), u16 achievement count (in both programs), u16 flags
        (0), u32 pass lane program size, u32 its state size (the RAM the
        console needs to run it), u32 list size, u32 frame lane program
        size, u32 0 (reserved), u8 the frame lane's ring: 2 to the power
        of this many samples, 3 to 8 (8 to 256 samples; anything else: 16),
        19 bytes 0 (the
        console reads the header first, then keeps its notes for
        nds-bootstrap's in-game menu in its RAM copy of bytes 40-63)
    the pass lane's program, then the frame lane's: the achievements,
        already parsed by rcheevos on the PC (rcheevos.compile_offline();
        the format is described in nds-bootstrap's rpcprobe/probe_ach_vm.c,
        the console's interpreter). The frame lane's achievements are
        checked every frame (sampled at the start of every VBlank, checked
        in order); the pass lane's in passes over them, one after another,
        each reading the game's memory once. split_lanes() picks them.
    the list, for nds-bootstrap's in-game menu (build_list()):
        "DRMN", u16 version (1), u16 entries, u32 text size, u32 0
        an entry per achievement of the game (official, core and bonus
        sets, RetroAchievements' order), 16 bytes each:
            u32 achievement ID
            u32 when it was earned: seconds since 2000-01-01 by the
                console's clock (local time); 0 = not earned, or not known
            u16 title, u16 description: where their text starts
            u8 points
            u8 flags: bit 0 earned (RetroAchievements has it, as far as
                DSiRPC knows), bit 1 earned on the console (the console
                sets it in RAM), bit 2 the console checks it (it's in the
                program)
            u16 0 (the console numbers its own unlocks here in RAM, for
                the menu's "new" marks)
        the text: the titles and descriptions, NUL-terminated, in plain
            ASCII (accents dropped, other characters '?'), then 0s to a
            multiple of 4

Only the achievements left to unlock (as far as DSiRPC knows) that the
console can check are in the programs: official, from the core or a bonus
set, reading only main RAM, that rcheevos parses and that don't need
floating point. The whole set and its state (the pass lane's, the frame
lane's twice, its ring of samples and, when there's room, the console's
shadow copy of the frame lane) have to fit in ACH_MEMORY, the RAM
nds-bootstrap sets aside for them less the 4 KB the console reads
RPCUNLK.BIN into and the per-frame capture's 2 KB ring. build_set() fits
it with the smallest ring (RING_MIN), giving up the shadow copy first, then
frame lane places (those achievements move to the pass lane), then the
biggest pass lane achievements, and then gives the ring as many samples
(up to RING_MAX) as what's left holds. The launcher
never looks past the header; the stamp tells it whether its copy is
current. (Version 1 had the MemAddr text instead of a program; version 2
had no list; version 3 had no frame lane; version 4 had no ring byte, and
the console gives it 16 samples.)

Which achievements DSiRPC put in which lane of the sets it built is kept in
ra/cache/console_sets.json by stamp (remember_set(), known_set()): the
console's "DSiRPC ach" report says which set it runs (st=), so DSiRPC knows
what the console checks every frame.

The sync exchange (when the launcher starts and when it starts a game, while DSiRPC can be found):

    1. The launcher broadcasts UDP b"DSiRPC sync?" + u8 version (the newest
       it speaks) to port 4245; DSiRPC answers b"DSiRPC sync!" + u8 version +
       u16 TCP port, the version being the older of the launcher's and its
       own (SYNC_VERSION), and the exchange uses that one. (DSiRPC before
       version 2 always answered 1, and launchers before it asked for 1.)
    2. Over TCP, the launcher sends a request:
         "DRSQ", u16 version, u16 n cached sets, 4 game code being started,
         u32 unlock bytes, u32 console model; then n x (4 code, u32 stamp); then
         RPCUNLK.BIN as it is; then (version 2) the games' RetroAchievements
         hashes: u16 m, u16 games hashed since the last sync, u32 how long that
         took (ms); then m x (4 code, 16 MD5, u8 flags (1: the file being
         started), u8 name length (up to 63), 2 bytes 0, the file's name
         without its folder or ".nds")
       and DSiRPC answers (version 2: first, while it works, any number of
       "DRSP", u16 done, u16 of, u8 what (1 checking the games with
       RetroAchievements, 2 getting their sets), 3 bytes 0, so the launcher
       keeps waiting and shows how far it got):
         "DRSA", u16 version, u16 status (0 ok), u16 unlocks taken,
         u16 n sets, u32 reserved; then n x (4 code, u32 size, the .DRS);
         then (version 2) u16 k, k x (16 MD5, u8 RA_UNKNOWN / RA_SET /
         RA_NOT_THIS_ROM / RA_NO_GAME, 3 bytes 0): what RetroAchievements has
         for each hash
       DSiRPC sends every set it has that the console doesn't have (or has an
       older copy of), the game being started first, and none for a game
       whose hash RetroAchievements has no set for (core/rom_hashes.py).

While the launcher waits for a key, it sends UDP b"DSiRPC here" + u8 console
model to the port DSiRPC answered from, every 5 seconds, and b"DSiRPC bye"
when it exits (SELECT, or exiting connected), so DSiRPC knows when it's in
the launcher and when it's gone.
"""

import datetime
import json
import logging
import os
import re
import struct
import time
import zlib

SYNC_PORT = 4245
VERSION = 1                               # RPCUNLK.BIN's, and the sync's first
SYNC_VERSION = 2                          # the newest sync version: 2 adds the games' hashes
DISCOVER = b"DSiRPC sync?"
ANSWER = b"DSiRPC sync!"
HERE = b"DSiRPC here"
BYE = b"DSiRPC bye"

UNLOCK_MAGIC = b"DRUL"
UNLOCK_SLOT = 16
UNLOCK_SLOTS = 256
PLAYTIME_ID = 0xFFFFFFFF           # a start's playtime, not an unlock
UNLOCK_FILE_SIZE = UNLOCK_SLOT * UNLOCK_SLOTS

SET_MAGIC = b"DRSE"
SET_VERSION = 5
SET_HEADER = struct.Struct("<4sHH4sIIHHIIIIIB19s")
CLEAN_SESSIONS = 2                        # sessions a frame lane achievement came out clean before it gives
                                          # its place to an untested one
ACHVM_STRUCT = 160                        # an AchVm on the console (144 bytes), rounded up
SHADOW_NOTE_BYTES = 8                     # probe_ach.c's ShAch: what it keeps per frame lane achievement
RESERVED_IDS = 0xFFFFFF00                 # slot IDs from this up aren't unlocks
PROVEN_ID = 0xFFFFFFFE                    # a slot saying an achievement needs the frame lane
CLEAN_ID = 0xFFFFFFFD                     # a slot saying one was shadowed a while with no difference
WATCH_RING_SIZE = 0x800                   # nds-bootstrap's DSIRPC_WATCH_RING_SIZE (locations.h)
ACH_MEMORY = 0x80000 - UNLOCK_FILE_SIZE - WATCH_RING_SIZE   # nds-bootstrap's DSIRPC_ACH_SIZE less
                                          # RPCUNLK.BIN's space and the capture's ring (probe_ach.c's
                                          # ACH_SET_SPACE)
FRAME_SLOTS = 16                          # probe_ach.c's ACH_FRAME_SLOTS: a set's ring when its header doesn't say
RING_MIN, RING_MAX = 8, 256               # the frame lane's ring: as many samples (a power of 2) as the memory
                                          # left over holds, 4 seconds and a bit at most
PROGRAM_VERSION = 3                       # probe_ach_vm.c's program format
PROGRAM_HEADER = struct.Struct("<IHHHHI")
LIST_MAGIC = b"DRMN"
LIST_VERSION = 1
LIST_HEADER = struct.Struct("<4sHHII")
LIST_ENTRY = struct.Struct("<IIHHBBH")
LIST_EARNED, LIST_ON_CONSOLE, LIST_CHECKED = 1, 2, 4
LIST_TEXT_MAX = 0xFFFF                    # u16 text offsets
TITLE_MAX, DESCRIPTION_MAX = 80, 255

REQUEST = struct.Struct("<4sHH4sII")
ROMS_HEADER = struct.Struct("<HHI")       # (version 2) hashes, games hashed since the last sync, ms
ROM_RECORD = struct.Struct("<4s16sBB2x")  # code, md5, flags, name length; the name follows
STATUS_RECORD = struct.Struct("<16sB3x")
PROGRESS = struct.Struct("<4sHHB3x")      # (version 2) "DRSP", done, of, what, before the answer
PROGRESS_CHECKING, PROGRESS_SETS = 1, 2
ROM_STARTED = 1
ROM_NAME_MAX = 63
# (core/rom_hashes.py's UNKNOWN, HAS_SET, NOT_THIS_ROM, NO_GAME)
RA_UNKNOWN, RA_SET, RA_NOT_THIS_ROM, RA_NO_GAME = 0, 1, 2, 3
MAX_ROMS = 1024
ANSWER_HEADER = struct.Struct("<4sHHHHI")
MAX_CACHED = 1024
MAX_UNLOCK_BYTES = 64 * 1024

EPOCH_2000 = datetime.datetime(2000, 1, 1)
_CODE = re.compile(rb"^[A-Z0-9]{4}$")


class FormatError(ValueError):
    pass


def valid_code(code):
    return isinstance(code, (bytes, bytearray)) and bool(_CODE.match(bytes(code)))


# -- RPCUNLK.BIN --------------------------------------------------------------

def _check(slot14):
    words = struct.unpack("<7H", slot14)
    return (0x5AA5 + sum(words)) & 0xFFFF


def unlock_slot(achievement_id, code, when, seq=0):
    """One unlock as the console writes it (for tests and tools)."""
    body = struct.pack("<I4sIH", achievement_id, code.encode() if isinstance(code, str) else code, when, seq)
    return body + struct.pack("<H", _check(body))


def empty_unlock_file():
    header = struct.pack("<4sHHH6s", UNLOCK_MAGIC, VERSION, UNLOCK_SLOT, UNLOCK_SLOTS, b"")
    return header + bytes(UNLOCK_FILE_SIZE - len(header))


def console_time(when):
    """Seconds since 2000 by the console's (local time) clock -> a Unix time."""
    try:
        return (EPOCH_2000 + datetime.timedelta(seconds=int(when))).timestamp()
    except (OverflowError, OSError, ValueError):
        return None


def console_clock(unix_time):
    """A Unix time -> seconds since 2000 by the console's (local time)
    clock, console_time()'s other way round. 0 for no or a bad time."""
    try:
        if not unix_time:
            return 0
        s = int((datetime.datetime.fromtimestamp(int(unix_time)) - EPOCH_2000).total_seconds())
        return s if 0 < s < 0x100000000 else 0
    except (OverflowError, OSError, ValueError):
        return 0


def _slots(data, notes=False):
    """The valid unlock slots in RPCUNLK.BIN's bytes: (id, code, when, seq);
    notes: the shadow check's notes too (what the launcher counts)."""
    if len(data) < UNLOCK_SLOT or data[:4] != UNLOCK_MAGIC:
        raise FormatError("not an unlock file")
    version, slot_size, slots = struct.unpack_from("<HHH", data, 4)
    if version != VERSION or slot_size != UNLOCK_SLOT:
        raise FormatError(f"unlock file version {version}, slot size {slot_size}")
    out = []
    for i in range(1, min(slots, len(data) // UNLOCK_SLOT)):
        slot = data[i * UNLOCK_SLOT:(i + 1) * UNLOCK_SLOT]
        aid, code, when, seq, check = struct.unpack("<I4sIHH", slot)
        if aid and (aid < RESERVED_IDS or (notes and aid != PLAYTIME_ID)) and check == _check(slot[:14]) and valid_code(code):
            out.append((aid, code, when, seq))
    return out


def read_shadow_notes(data):
    """The console's shadow check's notes in RPCUNLK.BIN's bytes: [{'code',
    'id', 'proven': True (it needs the frame lane) or False (shadowed a while,
    no difference)}], each (code, id) once, proven winning."""
    if not data or len(data) < UNLOCK_SLOT or data[:4] != UNLOCK_MAGIC:
        return []
    version, slot_size, slots = struct.unpack_from("<HHH", data, 4)
    if version != VERSION or slot_size != UNLOCK_SLOT:
        return []
    out = {}
    for i in range(1, min(slots, len(data) // UNLOCK_SLOT)):
        slot = data[i * UNLOCK_SLOT:(i + 1) * UNLOCK_SLOT]
        kind, code, aid, _, check = struct.unpack("<I4sIHH", slot)
        if kind in (PROVEN_ID, CLEAN_ID) and check == _check(slot[:14]) and valid_code(code) and aid:
            k = (code.decode(), aid)
            out[k] = out.get(k, False) or kind == PROVEN_ID
    return [{'code': c, 'id': a, 'proven': v} for (c, a), v in sorted(out.items())]


def shadow_slot(kind, achievement_id, code, seq=0):
    """One of the console's shadow notes as it writes them (for tests)."""
    return unlock_slot(kind, code, achievement_id, seq)


def count_unlocks(data):
    """How many valid unlock slots there are."""
    return len(_slots(data)) if data else 0


def count_slots(data):
    """How many valid slots there are, the shadow check's notes included:
    what the launcher counts, and clears the file when DSiRPC took that many."""
    return len(_slots(data, notes=True)) if data else 0


def read_unlocks(data, now=None):
    """[{'id', 'code', 'when', 'seq'}] from RPCUNLK.BIN's bytes, oldest
    first. Slots that are empty or only partly written are skipped, and so are
    repeats. A time in the future (a wrong clock) becomes now."""
    now = time.time() if now is None else now
    if not data:
        return []
    out, seen = [], set()
    for aid, code, when, seq in _slots(data):
        key = (code, aid)
        if key in seen:
            continue
        seen.add(key)
        t = console_time(when)
        if t is None or t > now + 86400 or t < now - 2 * 365 * 86400:
            t = now  # the console's clock is off
        out.append({'id': aid, 'code': code.decode(), 'when': int(min(t, now)), 'seq': seq})
    out.sort(key=lambda u: (u['when'], u['seq']))
    return out


# -- CODE.DRS -----------------------------------------------------------------

def _align4(n):
    return (n + 3) & ~3


def program_info(program):
    """(memrefs, achievements, conditions, [(id, bytes)]) of a compiled program."""
    version, n_plain, n_mod, n_ach, _, n_conds = PROGRAM_HEADER.unpack_from(program)
    if version != PROGRAM_VERSION:
        raise FormatError(f"program version {version}")
    pos = PROGRAM_HEADER.size + n_plain * 8 + n_mod * 20
    achievements = []
    for _ in range(n_ach):
        aid, sets, conds = struct.unpack_from("<IHH", program, pos)
        size = 8 + (sets & 0x7FFF) * 12 + conds * 16   # (bit 15 of sets: "has core")
        achievements.append((aid, size, conds))
        pos += size
    if pos != len(program):
        raise FormatError("program size doesn't add up")
    return n_plain + n_mod, n_ach, n_conds, achievements


def program_counts(program):
    """(plain memory values, modified ones, achievements, conditions)"""
    _, n_plain, n_mod, n_ach, _, n_conds = PROGRAM_HEADER.unpack_from(program)
    return n_plain, n_mod, n_ach, n_conds


def plain_memrefs(program):
    """The plain memory values a program reads: {(address, size, type)}"""
    n_plain = PROGRAM_HEADER.unpack_from(program)[1]
    out = set()
    for i in range(n_plain):
        address, size, vtype = struct.unpack_from("<IBB", program, PROGRAM_HEADER.size + i * 8)
        out.add((address, size, vtype))
    return out


def state_size(program):
    """The RAM the console needs to run a program (probe_ach_vm.c's checkProgram()),
    the map of which achievements each memory value matters to included."""
    n_mem, n_ach, n_conds, achievements = program_info(program)
    size = n_mem * 8 + n_conds * 4 + n_ach * 4 + _align4(n_mem) + _align4(n_ach)
    if not n_ach:
        return size
    # the map: a u32 per achievement, n_mem + 1 u16 and, at most, a u16 for
    # each memory value a condition names (each operand that isn't a constant)
    refs = 0
    _, n_plain, n_mod, _, _, _ = PROGRAM_HEADER.unpack_from(program)
    pos = PROGRAM_HEADER.size + n_plain * 8 + n_mod * 20
    for _, ach_size, _ in achievements:
        p, end = pos + 8, pos + ach_size
        while p < end:
            n = sum(struct.unpack_from("<5H", program, p))
            p += 12
            for _ in range(n):
                w = struct.unpack_from("<I", program, p)[0]
                refs += (((w >> 8) & 0x0F) != 2) + (((w >> 12) & 0x0F) != 2)
                p += 16
        pos = end
    return size + n_ach * 4 + _align4(2 * (n_mem + 1)) + _align4(2 * refs)


_PUNCTUATION = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "′": "'", "´": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "…": "...", "×": "x", " ": " ", "　": " ", "ß": "ss",
    "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe", "Ø": "O", "ø": "o",
    "★": "*", "☆": "*", "♥": "<3", "→": "->", "←": "<-",
    "\t": " ", "\r": " ", "\n": " ",
})


def plain_text(text, limit):
    """`text` in what nds-bootstrap's in-game menu font surely has: printable
    ASCII. Accents are dropped ("Pokemon"), typographic punctuation becomes
    its plain version, anything else '?'. At most `limit` characters."""
    import unicodedata
    text = unicodedata.normalize("NFKD", (text or "").translate(_PUNCTUATION))
    out = "".join(c if " " <= c <= "~" else "" if unicodedata.combining(c) else "?" for c in text)
    out = " ".join(out.split())
    return out if len(out) <= limit else out[:limit - 3].rstrip() + "..."


def build_list(raset, earned=None, checked=()):
    """The list section of a set (bytes): every achievement of the game for
    nds-bootstrap's in-game menu. earned: {id: Unix time it was earned (0 or
    None if not known)}; checked: the IDs in the program."""
    earned = earned or {}
    checked = set(checked)
    text = bytearray()
    where = {}

    def put(s):
        if s not in where:
            where[s] = len(text)
            text.extend(s.encode("ascii") + b"\0")
        return where[s]

    entries = []
    for a in raset.playable_achievements:
        aid = a["id"]
        flags = (LIST_EARNED if aid in earned else 0) | (LIST_CHECKED if aid in checked else 0)
        when = console_clock(earned.get(aid)) if aid in earned else 0
        title = put(plain_text(a["title"], TITLE_MAX))
        description = put(plain_text(a["description"], DESCRIPTION_MAX))
        if len(text) > LIST_TEXT_MAX:
            raise FormatError("too much text for the achievement list")
        entries.append(LIST_ENTRY.pack(aid, when, title, description, min(a["points"], 255), flags, 0))
    text.extend(bytes(_align4(len(text)) - len(text)))
    return LIST_HEADER.pack(LIST_MAGIC, LIST_VERSION, len(entries), len(text), 0) + b"".join(entries) + bytes(text)


def read_list(data):
    """[{'id', 'when', 'title', 'description', 'points', 'flags', 'seq'}] from a list section."""
    if len(data) < LIST_HEADER.size:
        raise FormatError("achievement list too short")
    magic, version, count, text_size, _ = LIST_HEADER.unpack_from(data)
    text_at = LIST_HEADER.size + count * LIST_ENTRY.size
    if magic != LIST_MAGIC or version != LIST_VERSION or text_at + text_size > len(data):
        raise FormatError("not an achievement list")
    text = data[text_at:text_at + text_size]

    def string(at):
        end = text.find(b"\0", at)
        if at >= len(text) or end < 0:
            raise FormatError("achievement list text out of range")
        return text[at:end].decode("ascii")

    out = []
    for i in range(count):
        aid, when, title, description, points, flags, seq = LIST_ENTRY.unpack_from(data, LIST_HEADER.size + i * LIST_ENTRY.size)
        out.append({'id': aid, 'when': when, 'title': string(title), 'description': string(description),
                    'points': points, 'flags': flags, 'seq': seq})
    return out


# -- the two lanes ---------------------------------------------------------------
#
# RetroAchievements' rules are checked once a frame on an emulator, and some
# achievements can only be judged that way: a flag that's set for one frame
# (Tetris DS's T-spin), a ResetIf that must catch every rotation, a hit
# count of frames. The console samples the frame lane's memory values at the
# start of every VBlank and checks them frame by frame; the rest go in the
# pass lane, checked in passes that each read the memory once. The frame
# lane costs ARM7 time every frame, so it's picked by need first and then by
# cost, within FRAME_SAMPLE_CYCLES (the sampling, in the VBlank interrupt)
# and FRAME_CHECK_CYCLES (the checking, in the game's idle time, on a frame
# where most achievements' values didn't change: those are skipped). A frame
# where every value changes has to be checked whole; the console checks a
# sample a part at a time in its idle turns, so that only has to fit
# FRAME_BUSY_CYCLES, what the ring of samples can catch up on without
# dropping one (7 frames' checking; the ring, RING_MIN to RING_MAX samples
# as the set's memory allows, holds more than that, for the longer busy
# stretches of a game whose values change on most frames, as Tetris DS's
# line clears and higher levels do). The costs are fitted to nds-bootstrap's checker on
# tools/arm7_model's ARM7 model (the busy one so it never comes out under
# what the model measured).

FRAME_SAMPLE_CYCLES = 42000               # about 20 scanlines (a frame has 263, 2,130 cycles each)
FRAME_CHECK_CYCLES = 110000               # about 52 scanlines
FRAME_BUSY_CYCLES = 7 * FRAME_CHECK_CYCLES   # (fixed, whatever the ring: the rest of the ring is for
                                             # longer busy stretches)
_FLAG = re.compile(r"(?:^|[_S])([RPZCD]):")
_HITS = re.compile(r"\.\d+\.")
_DELTA = re.compile(r"(?<![0-9A-Za-z])[dp](?:0x|f[A-Za-z])")


def timing(memaddr):
    """How much an achievement needs checking every frame: 3 if it counts
    frames or must not miss one (a hit target, ResetIf, PauseIf,
    ResetNextIf, AddHits, SubHits), 2 if it compares values with earlier
    ones (delta, prior), 1 otherwise."""
    if _FLAG.search(memaddr) or _HITS.search(memaddr):
        return 3
    return 2 if _DELTA.search(memaddr) else 1


def frame_costs(n_plain, n_mod, n_ach, n_conds):
    """(sampling, checking) ARM7 cycles a frame for a frame lane this big."""
    return (192 * n_plain + 500 * n_mod + 150,
            119 * (n_plain + n_mod) + 350 * n_ach + 1 * n_conds)


def frame_busy_cost(n_plain, n_mod, n_ach, n_conds):
    """ARM7 cycles to check a frame lane this big on a frame where every
    value changed (none skipped)."""
    return 545 * (n_plain + n_mod) + 2659 * n_ach + 436 * n_conds


def _fits_frame(n_plain, n_mod, n_ach, n_conds):
    sample, check = frame_costs(n_plain, n_mod, n_ach, n_conds)
    return (sample <= FRAME_SAMPLE_CYCLES and check <= FRAME_CHECK_CYCLES and
            frame_busy_cost(n_plain, n_mod, n_ach, n_conds) <= FRAME_BUSY_CYCLES)


def split_lanes(todo, proven=(), clean=None):
    """[(id, memaddr)] (all parsing and supported) -> (frame lane, pass
    lane), the same shape. The frame lane takes the ones proven to need it
    first (proven: ids, from core/frame_needs.py), then the ones timing()
    guesses need it (2 or 3), but those the console's shadow check found no
    difference for in CLEAN_SESSIONS sessions or more (clean: {id:
    sessions}) after the others, then the rest; the cheapest first each
    time so as many as possible fit, while it fits. Each one is tried by
    compiling the lane with it: the memory values achievements share
    (rcheevos shares them, AddAddress chains included, and a chain's root
    often feeds hundreds) count once, as they do on the console. That's a
    compile per achievement, a tenth of a second for a big set."""
    from .rcheevos import compile_offline
    alone = {}
    for aid, memaddr in todo:
        program, left = compile_offline([(aid, memaddr)])
        if left:
            continue
        n_plain, n_mod, n_ach, n_conds = program_counts(program)
        alone[aid] = n_conds + 2 * n_mod
    proven, clean = set(proven), clean or {}

    def group(t):
        if t[0] in proven:
            return 0
        if timing(t[1]) < 2:
            return 3
        return 2 if clean.get(t[0], 0) >= CLEAN_SESSIONS else 1
    order = sorted((t for t in todo if t[0] in alone), key=lambda t: (group(t), alone[t[0]], t[0]))
    frame = []
    for t in order:
        program, _ = compile_offline(frame + [t])
        if _fits_frame(*program_counts(program)):
            frame.append(t)
    chosen = {t[0] for t in frame}
    return frame, [t for t in todo if t[0] not in chosen]


def set_memory(pass_program, frame_program, list_size, shadow=True, slots=FRAME_SLOTS):
    """The console RAM a set needs: the file (header, programs, list), the
    pass lane's state, the frame lane's twice and its ring of slots samples,
    and the frame lane's shadow copy (shadow: the console leaves it out when
    there's no room for it)."""
    need = (_align4(SET_HEADER.size + len(pass_program) + len(frame_program) + _align4(list_size)) +
            state_size(pass_program))
    if frame_program:
        n_plain, n_mod, n_ach, _ = program_counts(frame_program)
        need += 2 * state_size(frame_program) + slots * 4 * (n_plain + n_mod)
    if frame_program and shadow:
        n_plain, n_mod, n_ach, _ = program_counts(frame_program)
        # its shadow copy (probe_ach.c: checked from every 8th sample; its VM, state, notes, and its
        # own copy of the sample, so the frame lane never waits for it)
        need += ACHVM_STRUCT + state_size(frame_program) + SHADOW_NOTE_BYTES * n_ach + 4 * (n_plain + n_mod)
    return need


_NO_SHADOW_SAID = set()   # the games build_set() has said so for in this run


def _fit_slow(rest, frame, frame_program, list_size, code, tick=None):
    """The fit as it first was (kept as the reference for _fit_fast()): one
    step at a time, the pass lane compiled again at each. Returns (pass
    program, its achievements, frame lane, frame program, shadow, moved)."""
    from .rcheevos import compile_offline
    rest, frame = list(rest), list(frame)
    shadow, moved = True, 0
    while True:
        if tick:
            tick()
        program, _ = compile_offline(rest)
        _, _, _, achievements = program_info(program)
        if not achievements or set_memory(program, frame_program, _align4(list_size), shadow=shadow,
                                          slots=RING_MIN) <= ACH_MEMORY:
            break
        if shadow:
            shadow = False
            _say_no_shadow(code)
            continue
        if frame:
            rest.append(frame.pop())
            moved += 1
            frame_program = compile_offline(frame)[0] if frame else b""
            continue
        biggest = max(achievements, key=lambda a: a[1] + a[2] * 4)[0]
        rest = [t for t in rest if t[0] != biggest]
    return program, achievements, frame, frame_program, shadow, moved


def _fit_fast(rest, frame, frame_program, list_size, code, tick=None):
    """The same fit as _fit_slow(), the same set byte for byte, by halving
    instead of one step at a time: what fits only grows as achievements move
    from the frame lane to the pass lane (one state there, not two and the
    ring) or are left out, so the step the slow way stops at is found in a
    few compiles. The ones left out go biggest first, as there (their sizes
    taken from one compile)."""
    from .rcheevos import compile_offline
    rest, frame = list(rest), list(frame)
    whole_frame = list(frame)       # (its program given)
    compiled = {}

    def build(pass_lane, kept):
        if tick:
            tick()
        program, _ = compile_offline(pass_lane)
        fprog = frame_program if kept == whole_frame else compile_offline(kept)[0] if kept else b""
        return program, program_info(program)[3], fprog

    def fits(state, shadow):
        program, achievements, fprog = state
        return not achievements or set_memory(program, fprog, _align4(list_size), shadow=shadow,
                                              slots=RING_MIN) <= ACH_MEMORY

    whole = build(rest, frame)
    if fits(whole, True):
        return whole[0], whole[1], frame, whole[2], True, 0
    _say_no_shadow(code)
    if fits(whole, False):
        return whole[0], whole[1], frame, whole[2], False, 0

    # Frame lane achievements to the pass lane, the last first: the most kept that fits
    def keeping(k):
        if k not in compiled:
            compiled[k] = build(rest + frame[k:][::-1], frame[:k])
        return compiled[k]
    if frame:
        if fits(keeping(0), False):
            lo, hi = 0, len(frame)      # (keeping lo fits, keeping hi doesn't)
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if fits(keeping(mid), False):
                    lo = mid
                else:
                    hi = mid
            program, achievements, fprog = keeping(lo)
            return program, achievements, frame[:lo], fprog, False, len(frame) - lo
        rest = rest + frame[::-1]
        moved, frame = len(frame), []
        base = keeping(0)
    else:
        moved, base = 0, whole

    # Still too big: the biggest achievements left out, as few as fit
    order = [a[0] for _, a in sorted(enumerate(base[1]), key=lambda p: (-(p[1][1] + p[1][2] * 4), p[0]))]
    dropped = {}

    def dropping(m):
        if m not in dropped:
            gone = set(order[:m])
            dropped[m] = build([t for t in rest if t[0] not in gone], [])
        return dropped[m]
    lo, hi = 0, len(order)              # (dropping lo doesn't fit, dropping hi does)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fits(dropping(mid), False):
            hi = mid
        else:
            lo = mid
    program, achievements, fprog = dropping(hi)
    return program, achievements, frame, fprog, False, moved


def _say_no_shadow(code):
    # (every sync builds the sets again: said once a run, then only in the debug log)
    logging.log(logging.DEBUG if code in _NO_SHADOW_SAID else logging.INFO,
                f"Offline sets: {code}: no room for the shadow check's copy of the frame lane; "
                "the console won't shadow this game")
    _NO_SHADOW_SAID.add(code)


BUILT_KEEP = 2   # built sets kept a game in ra/cache/built/ (the newest)


def _builder_files():
    """The Python files a built set's bytes depend on: this one, ra_game.py
    (_unreachable(), which achievements go in) and rcheevos.py (the
    compiler's wrapper)"""
    here = os.path.dirname(os.path.abspath(__file__))
    return [os.path.abspath(__file__), os.path.join(here, "ra_game.py"), os.path.join(here, "rcheevos.py")]


def _build_key(raset, code, skip_ids, earned, proven, clean):
    """A digest of everything a built set depends on: the set's
    achievements, title and ID, what's skipped and listed as earned, what
    frame_needs has learned, and the builder (_builder_files() and the
    rcheevos library)."""
    import hashlib
    from . import rcheevos
    h = hashlib.sha256()
    for path in _builder_files():
        try:
            with open(path, "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(b"?")
    lib = getattr(rcheevos, "library_path", lambda: None)()
    if lib:
        try:
            st = os.stat(lib)
            h.update(f"{lib}|{st.st_size}|{int(st.st_mtime)}".encode())
        except OSError:
            pass
    parts = [code, raset.id, raset.title, raset.achievements, sorted(skip_ids),
             sorted((int(k), int(v or 0)) for k, v in (earned or {}).items()), sorted(proven),
             sorted((int(k), int(v)) for k, v in (clean or {}).items()), ACH_MEMORY, SET_VERSION]
    h.update(json.dumps(parts, sort_keys=True, default=str).encode())
    return h.hexdigest()[:32]


def build_set(raset, code, skip_ids=(), earned=None, proven=(), clean=None, cache_dir=None, tick=None, fit=None):
    """The offline set for a game (bytes), from its RaSet. skip_ids: the
    achievements already unlocked (left out of the programs); earned: {id:
    Unix time it was earned, or 0} for the in-game menu's list; proven: the
    ids known to need the frame lane (core/frame_needs.py's proven()); clean:
    {id: sessions the console's shadow check found no difference}, for
    split_lanes()'s order. Needs
    rcheevos with DSiRPC's compiler (rcheevos.RcheevosMissing otherwise).
    cache_dir: built sets kept there by a digest of all of that
    (_build_key()), so an unchanged set isn't built again, after a restart
    too; tick(): called as it goes, to keep the launcher waiting."""
    key = path = None
    if cache_dir:
        key = _build_key(raset, code, skip_ids, earned, proven, clean)
        path = os.path.join(cache_dir, f"{code}-{key}.drs")
        try:
            with open(path, "rb") as f:
                data = f.read()
            read_set(data)      # (a damaged one is built again)
            return data
        except (OSError, FormatError, struct.error):
            pass
    data = _build_set(raset, code, skip_ids, earned, proven, clean, tick, fit or _fit_fast)
    if path:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path)
            old = sorted((os.path.getmtime(os.path.join(cache_dir, n)), n) for n in os.listdir(cache_dir)
                         if n.startswith(code + "-") and n.endswith(".drs"))
            for _, n in old[:-BUILT_KEEP]:
                os.remove(os.path.join(cache_dir, n))
        except OSError:
            pass
    return data


def _build_set(raset, code, skip_ids, earned, proven, clean, tick, fit):
    from .ra_game import _unreachable
    from .rcheevos import compile_offline
    todo = [(a["id"], a["memaddr"]) for a in raset.playable_achievements
            if a["id"] not in skip_ids and a["memaddr"] and not _unreachable(a["memaddr"])]
    _, left_out = compile_offline(todo)
    todo = [t for t in todo if t[0] not in left_out]
    frame, rest = split_lanes(todo, proven, clean)
    frame_program = b""
    if frame:
        frame_program, _ = compile_offline(frame)
    # The list's size doesn't depend on which achievements are checked
    list_size = len(build_list(raset, earned))
    # Too big for the console: the shadow check's copy goes first (the console
    # leaves it out when there's no room), never an achievement; then frame
    # lane achievements move to the pass lane, the least needed first (still
    # checked; there they take one state, not two and the ring); then the
    # biggest achievements are left out
    slots = RING_MIN
    program, achievements, frame, frame_program, shadow, moved = fit(rest, frame, frame_program, list_size,
                                                                     code, tick)
    if moved:
        logging.info(f"Offline sets: {code}: {moved} frame lane achievement(s) moved to the pass lane to fit the console")
    # The ring of the frame lane's samples (fitted at RING_MIN): as big as what's
    # left holds, so the checking can fall that far behind in a busy stretch and
    # catch up without losing a sample
    while slots < RING_MAX and frame_program and set_memory(program, frame_program, _align4(list_size), shadow=shadow,
                                                          slots=slots * 2) <= ACH_MEMORY:
        slots *= 2
    if len(program) % 4 or len(frame_program) % 4:
        raise FormatError("program size isn't a multiple of 4")
    n_ach = program_info(program)[1] + (program_info(frame_program)[1] if frame_program else 0)
    checked = [a[0] for a in achievements] + [t[0] for t in frame]
    the_list = build_list(raset, earned, checked)
    the_list += bytes(_align4(len(the_list)) - len(the_list))
    body = program + frame_program + the_list
    header = SET_HEADER.pack(SET_MAGIC, SET_VERSION, SET_HEADER.size, code.encode(), raset.id,
                             zlib.crc32(body) & 0xFFFFFFFF, n_ach, 0, len(program), state_size(program),
                             len(the_list), len(frame_program), 0, slots.bit_length() - 1, b"")
    return header + body


def read_set(data):
    """{'code', 'game_id', 'stamp', 'achievements': [{'id'}], 'program',
    'state_size', 'frame_program', 'frame': [ids], 'pass': [ids], 'list':
    read_list()'s}. Version 3 sets (no frame lane) too."""
    if len(data) < SET_HEADER.size or data[:4] != SET_MAGIC:
        raise FormatError("not an offline set")
    (_, version, hsize, code, game_id, stamp, count, _flags,
     program_size, state, list_size, frame_size, _reserved, ring, _) = SET_HEADER.unpack_from(data)
    if version not in (3, 4, 5):
        raise FormatError(f"offline set version {version}")
    if version == 3:
        frame_size = 0
    if version < 5:
        ring = 0   # (no ring byte: the console gives it FRAME_SLOTS)
    ring = (1 << ring) if 3 <= ring <= 8 else FRAME_SLOTS
    total = program_size + frame_size + list_size
    body = data[hsize:hsize + total]
    if len(body) != total or zlib.crc32(body) & 0xFFFFFFFF != stamp:
        raise FormatError("offline set damaged (stamp doesn't match)")
    program = body[:program_size]
    frame_program = body[program_size:program_size + frame_size]
    _, n_ach, _, achievements = program_info(program)
    frame = [aid for aid, _, _ in program_info(frame_program)[3]] if frame_program else []
    if n_ach + len(frame) != count or state != state_size(program):
        raise FormatError("offline set header doesn't match its programs")
    passes = [aid for aid, _, _ in achievements]
    return {'code': code.decode(), 'game_id': game_id, 'stamp': stamp,
            'achievements': [{'id': aid} for aid in passes + frame],
            'program': program, 'state_size': state, 'frame_program': frame_program,
            'frame': frame, 'pass': passes, 'list': read_list(body[program_size + frame_size:program_size + frame_size + list_size]),
            'ring': ring}


# -- which set the console runs ------------------------------------------------------

KNOWN_SETS_KEEP = 64


def _known_path(ra_dir):
    if ra_dir is None:
        from . import ra_set
        ra_dir = ra_set.RA_DIR
    return os.path.join(ra_dir, "cache", "console_sets.json")


def remember_set(data, ra_dir=None, memaddr=None):
    """Notes which achievements a set DSiRPC built checks in which lane, by
    its stamp (ra/cache/console_sets.json; the last KNOWN_SETS_KEEP), and
    with memaddr ({id: MemAddr}) the logic of its frame lane's, so the
    console's shadow notes can be told apart from a later version's."""
    try:
        s = read_set(data)
    except FormatError:
        return
    path = _known_path(ra_dir)
    try:
        with open(path, encoding="utf-8") as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = {}
    if not isinstance(known, dict):
        known = {}
    known[f"{s['stamp']:08X}"] = {'code': s['code'], 'game_id': s['game_id'], 'frame': s['frame'],
                                  'pass': s['pass'], 'time': int(time.time())}
    if memaddr:
        from . import frame_needs
        known[f"{s['stamp']:08X}"]['mem'] = {str(aid): frame_needs.memaddr_hash(memaddr[aid])
                                             for aid in s['frame'] if memaddr.get(aid)}
    if len(known) > KNOWN_SETS_KEEP:
        for stamp in sorted(known, key=lambda k: known[k].get('time', 0))[:len(known) - KNOWN_SETS_KEEP]:
            del known[stamp]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(known, f)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def known_set(stamp, ra_dir=None):
    """{'code', 'game_id', 'frame': set of ids, 'pass': set of ids, 'mem':
    {id: its MemAddr's hash} (frame lane; None for a set remembered before
    that)} of a set DSiRPC built, by its stamp (an int), or None."""
    try:
        with open(_known_path(ra_dir), encoding="utf-8") as f:
            entry = json.load(f).get(f"{stamp:08X}")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(entry, dict):
        return None
    mem = entry.get('mem')
    return {'code': entry.get('code'), 'game_id': entry.get('game_id', 0),
            'frame': set(entry.get('frame') or ()), 'pass': set(entry.get('pass') or ()),
            'mem': {int(k): v for k, v in mem.items()} if isinstance(mem, dict) else None}


def set_stamp(data):
    return struct.unpack_from("<I", data, 16)[0]


# -- the exchange ---------------------------------------------------------------

def sync_version(asked):
    """The version DSiRPC answers a launcher's "DSiRPC sync?" with: the
    older of the launcher's and its own."""
    return max(1, min(asked or 1, SYNC_VERSION))


def parse_request(header, rest_reader):
    """Reads a request: header is its first REQUEST.size bytes, rest_reader(n)
    returns the next n bytes. -> (game code or None, {code: stamp}, unlock bytes)."""
    r = parse_sync(header, rest_reader)
    return r["game"], r["stamps"], r["unlocks"]


def parse_sync(header, rest_reader):
    """parse_request()'s, all of it: {'version', 'game', 'stamps', 'unlocks',
    'roms': [(code, md5 hex, started, file name)], 'hashed', 'hash_ms'} (the
    last three empty for version 1)."""
    magic, version, cached, game, unlock_bytes, _ = REQUEST.unpack(header)
    if magic != b"DRSQ" or not 1 <= version <= SYNC_VERSION:
        raise FormatError("not a sync request")
    if cached > MAX_CACHED or unlock_bytes > MAX_UNLOCK_BYTES:
        raise FormatError("sync request too big")
    stamps = {}
    raw = rest_reader(cached * 8)
    for i in range(cached):
        code, stamp = struct.unpack_from("<4sI", raw, i * 8)
        if valid_code(code):
            stamps[code.decode()] = stamp
    unlocks = rest_reader(unlock_bytes) if unlock_bytes else b""
    roms, hashed, hash_ms = [], 0, 0
    if version >= 2:
        n, hashed, hash_ms = ROMS_HEADER.unpack(rest_reader(ROMS_HEADER.size))
        if n > MAX_ROMS:
            raise FormatError("sync request too big")
        for _ in range(n):
            code, md5, flags, name_len = ROM_RECORD.unpack(rest_reader(ROM_RECORD.size))
            if name_len > ROM_NAME_MAX:
                raise FormatError("sync request garbled")
            name = rest_reader(name_len).decode("ascii", "replace") if name_len else ""
            # (a file without a game code, homebrew often: "" for its code)
            roms.append((code.decode() if valid_code(code) else "", md5.hex(), bool(flags & ROM_STARTED), name))
    return {'version': version, 'game': game.decode() if valid_code(game) else None, 'stamps': stamps,
            'unlocks': unlocks, 'roms': roms, 'hashed': hashed, 'hash_ms': hash_ms}


def console_name(model):
    """TWiLight Menu++'s CONSOLE_MODEL (0 DSi, 1 DSi devkit, 2 3DS, 3 New
    3DS) as "3DS" or "DSi"."""
    return "3DS" if model in (2, 3) else "DSi"


def request_console(header):
    """The console a request came from: "3DS" or "DSi". Its last word is
    TWiLight Menu++'s CONSOLE_MODEL; launchers from before it was sent leave
    0 there."""
    return console_name(REQUEST.unpack(header)[5] & 0xFF)


def build_request(game, stamps, unlocks, console_model=0, version=VERSION, roms=(), hashed=0, hash_ms=0):
    """A request as the launcher sends it (for tests). roms: [(code, md5
    hex, started, file name)], for version 2."""
    head = REQUEST.pack(b"DRSQ", version, len(stamps), (game or "").encode().ljust(4, b"\0")[:4],
                        len(unlocks), console_model)
    out = head + b"".join(struct.pack("<4sI", c.encode(), s) for c, s in stamps.items()) + unlocks
    if version >= 2:
        out += ROMS_HEADER.pack(len(roms), hashed, hash_ms)
        for c, m, started, *name in roms:
            n = (name[0] if name else "").encode("ascii", "replace")[:ROM_NAME_MAX]
            out += ROM_RECORD.pack(c.encode(), bytes.fromhex(m), ROM_STARTED if started else 0, len(n)) + n
    return out


def build_progress(done, total, what):
    """(version 2) a "still working" frame before the answer"""
    return PROGRESS.pack(b"DRSP", min(done, 0xFFFF), min(total, 0xFFFF), what)


def build_answer(status, taken, sets, version=VERSION, statuses=None):
    """sets: [(code, .DRS bytes)]; statuses (version 2): {md5 hex: RA_*}."""
    out = [ANSWER_HEADER.pack(b"DRSA", version, status, taken, len(sets), 0)]
    for code, data in sets:
        out.append(struct.pack("<4sI", code.encode(), len(data)))
        out.append(data)
    if version >= 2:
        statuses = statuses or {}
        out.append(struct.pack("<H", len(statuses)))
        out += [STATUS_RECORD.pack(bytes.fromhex(m), st) for m, st in statuses.items()]
    return b"".join(out)
