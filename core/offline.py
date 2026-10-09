"""
offline.py - the files and messages for playing without DSiRPC nearby
(offline play): achievements are kept on the console's SD card and handed to
DSiRPC the next time the launcher finds it. DSiRPC does all the work; the
console only stores what it's given and what it unlocked.

On the SD card (the launcher writes them; see launcher/source/sync.c):

    sd:/RPCUNLK.BIN       unlocks waiting for DSiRPC (written in game by
                          nds-bootstrap's rpcprobe/probe_ach.c; read and
                          cleared by the launcher)
    <launcher>/sets/CODE.DRS
                          each game's achievements, from DSiRPC (build_set())
    sd:/RPCSET.BIN        the set of the game being started (a copy, so the
                          in-game side only needs a fixed name in the root);
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
after the last slot in use (sequence number = slot number), dated by the
console's clock, read when the achievement unlocks (when it can't be read just
then: its last reading, or the launcher's time= in RPCHAND.TXT, plus the
VBlanks since, which stop while it sleeps); 0 if there was no clock.
Achievements already in the file
aren't checked again. Unlocks DSiRPC made itself (playing online) come back
this way too; engine.py leaves out the ones it knows about.

CODE.DRS (an offline set, version 4), little-endian:

    header (64 bytes): "DRSE", u16 version (4), u16 header size (64),
        4 game code, u32 RA game ID, u32 stamp (CRC-32 of everything after
        the header), u16 achievement count (in both programs), u16 flags
        (0), u32 pass lane program size, u32 its state size (the RAM the
        console needs to run it), u32 list size, u32 frame lane program
        size, 24 bytes 0 (the console keeps its notes for nds-bootstrap's
        in-game menu in its RAM copy of bytes 40-63)
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
            ASCII (accents dropped, other characters '?')

Only the achievements left to unlock (as far as DSiRPC knows) that the
console can check are in the programs: official, from the core or a bonus
set, reading only main RAM, that rcheevos parses and that don't need
floating point. The whole set and its state (the pass lane's, the frame
lane's twice and its ring of FRAME_SLOTS samples) have to fit in
ACH_MEMORY, the RAM nds-bootstrap sets aside for them less the 4 KB the
console reads RPCUNLK.BIN into and the per-frame capture's 2 KB ring; the
biggest pass lane achievements are left out until it does. The launcher
never looks past the header; the stamp tells it whether its copy is
current. (Version 1 had the MemAddr text instead of a program; version 2
had no list; version 3 had no frame lane.)

Which achievements DSiRPC put in which lane of the sets it built is kept in
ra/cache/console_sets.json by stamp (remember_set(), known_set()): the
console's "DSiRPC ach" report says which set it runs (st=), so DSiRPC knows
what the console checks every frame.

The sync exchange (one per game started while DSiRPC can be found):

    1. The launcher broadcasts UDP b"DSiRPC sync?" + u8 version to port 4245;
       DSiRPC answers b"DSiRPC sync!" + u8 version + u16 TCP port.
    2. Over TCP, the launcher sends a request:
         "DRSQ", u16 version, u16 n cached sets, 4 game code being started,
         u32 unlock bytes, u32 reserved; then n x (4 code, u32 stamp); then
         RPCUNLK.BIN as it is
       and DSiRPC answers:
         "DRSA", u16 version, u16 status (0 ok), u16 unlocks taken,
         u16 n sets, u32 reserved; then n x (4 code, u32 size, the .DRS)
       DSiRPC sends every set it has that the console doesn't have (or has an
       older copy of), the game being started first.
"""

import datetime
import json
import os
import re
import struct
import time
import zlib

SYNC_PORT = 4245
VERSION = 1
DISCOVER = b"DSiRPC sync?"
ANSWER = b"DSiRPC sync!"

UNLOCK_MAGIC = b"DRUL"
UNLOCK_SLOT = 16
UNLOCK_SLOTS = 256
UNLOCK_FILE_SIZE = UNLOCK_SLOT * UNLOCK_SLOTS

SET_MAGIC = b"DRSE"
SET_VERSION = 4
SET_HEADER = struct.Struct("<4sHH4sIIHHIIII24s")
WATCH_RING_SIZE = 0x800                   # nds-bootstrap's DSIRPC_WATCH_RING_SIZE (locations.h)
ACH_MEMORY = 0x40000 - UNLOCK_FILE_SIZE - WATCH_RING_SIZE   # nds-bootstrap's DSIRPC_ACH_SIZE less
                                          # RPCUNLK.BIN's space and the capture's ring (probe_ach.c's
                                          # ACH_SET_SPACE)
FRAME_SLOTS = 8                           # probe_ach.c's ACH_FRAME_SLOTS
PROGRAM_VERSION = 2                       # probe_ach_vm.c's program format
PROGRAM_HEADER = struct.Struct("<IHHHHI")
LIST_MAGIC = b"DRMN"
LIST_VERSION = 1
LIST_HEADER = struct.Struct("<4sHHII")
LIST_ENTRY = struct.Struct("<IIHHBBH")
LIST_EARNED, LIST_ON_CONSOLE, LIST_CHECKED = 1, 2, 4
LIST_TEXT_MAX = 0xFFFF                    # u16 text offsets
TITLE_MAX, DESCRIPTION_MAX = 80, 255

REQUEST = struct.Struct("<4sHH4sII")
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


def _slots(data):
    """The valid unlock slots in RPCUNLK.BIN's bytes: (id, code, when, seq)."""
    if len(data) < UNLOCK_SLOT or data[:4] != UNLOCK_MAGIC:
        raise FormatError("not an unlock file")
    version, slot_size, slots = struct.unpack_from("<HHH", data, 4)
    if version != VERSION or slot_size != UNLOCK_SLOT:
        raise FormatError(f"unlock file version {version}, slot size {slot_size}")
    out = []
    for i in range(1, min(slots, len(data) // UNLOCK_SLOT)):
        slot = data[i * UNLOCK_SLOT:(i + 1) * UNLOCK_SLOT]
        aid, code, when, seq, check = struct.unpack("<I4sIHH", slot)
        if aid != 0 and check == _check(slot[:14]) and valid_code(code):
            out.append((aid, code, when, seq))
    return out


def count_unlocks(data):
    """How many valid unlock slots there are (what the launcher counts too)."""
    return len(_slots(data)) if data else 0


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
        aid, n_sets, _, conds = struct.unpack_from("<IBBH", program, pos)
        size = 8 + n_sets * 12 + conds * 16
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
    """The RAM the console needs to run a program (probe_ach_vm.c's checkProgram())."""
    n_mem, n_ach, n_conds, _ = program_info(program)
    return n_mem * 8 + n_conds * 4 + n_ach * 4 + _align4(n_mem) + _align4(n_ach)


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
# and FRAME_CHECK_CYCLES (the checking, in the game's idle time). The costs
# are fitted to nds-bootstrap's checker on tools/arm7_model's ARM7 model
# (an achievement whose values didn't change is skipped, which the check
# cost assumes for most of them on most frames).

FRAME_SAMPLE_CYCLES = 40000               # about 19 scanlines (a frame has 263, 2,130 cycles each)
FRAME_CHECK_CYCLES = 110000               # about 52 scanlines
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
    return (221 * n_plain + 566 * n_mod + 150,
            112 * (n_plain + n_mod) + 500 * n_ach + 90 * n_conds)


def _fits_frame(n_plain, n_mod, n_ach, n_conds):
    sample, check = frame_costs(n_plain, n_mod, n_ach, n_conds)
    return sample <= FRAME_SAMPLE_CYCLES and check <= FRAME_CHECK_CYCLES


def split_lanes(todo):
    """[(id, memaddr)] (all parsing and supported) -> (frame lane, pass
    lane), the same shape. The frame lane takes the ones that need it
    (timing() 2 or 3) first, the cheapest first so as many as possible fit,
    then the rest the same way, while it fits; each one is costed on its own
    (memory values it shares with ones already in count once if they're
    plain), then the lane as a whole is checked."""
    from .rcheevos import compile_offline
    alone = {}
    for aid, memaddr in todo:
        program, left = compile_offline([(aid, memaddr)])
        if left:
            continue
        n_plain, n_mod, n_ach, n_conds = program_counts(program)
        alone[aid] = (plain_memrefs(program), n_mod, n_conds)
    order = sorted((t for t in todo if t[0] in alone),
                   key=lambda t: (timing(t[1]) < 2, alone[t[0]][2] + 2 * alone[t[0]][1], t[0]))
    frame, plain, n_mod, n_conds = [], set(), 0, 0
    for t in order:
        p, m, c = alone[t[0]]
        if _fits_frame(len(plain | p), n_mod + m, len(frame) + 1, n_conds + c):
            frame.append(t)
            plain |= p
            n_mod += m
            n_conds += c
    while frame:  # (the estimate counts shared modified values more than once, so this is a check)
        program, _ = compile_offline(frame)
        if _fits_frame(*program_counts(program)):
            break
        frame.pop()
    chosen = {t[0] for t in frame}
    return frame, [t for t in todo if t[0] not in chosen]


def set_memory(pass_program, frame_program, list_size):
    """The console RAM a set needs: the file (header, programs, list), the
    pass lane's state, the frame lane's twice and its ring of samples."""
    need = _align4(SET_HEADER.size + len(pass_program) + len(frame_program) + list_size) + state_size(pass_program)
    if frame_program:
        n_plain, n_mod, _, _ = program_counts(frame_program)
        need += 2 * state_size(frame_program) + FRAME_SLOTS * 4 * (n_plain + n_mod)
    return need


def build_set(raset, code, skip_ids=(), earned=None):
    """The offline set for a game (bytes), from its RaSet. skip_ids: the
    achievements already unlocked (left out of the programs); earned: {id:
    Unix time it was earned, or 0} for the in-game menu's list. Needs
    rcheevos with DSiRPC's compiler (rcheevos.RcheevosMissing otherwise)."""
    from .ra_game import _unreachable
    from .rcheevos import compile_offline
    todo = [(a["id"], a["memaddr"]) for a in raset.playable_achievements
            if a["id"] not in skip_ids and a["memaddr"] and not _unreachable(a["memaddr"])]
    _, left_out = compile_offline(todo)
    todo = [t for t in todo if t[0] not in left_out]
    frame, rest = split_lanes(todo)
    frame_program = b""
    if frame:
        frame_program, _ = compile_offline(frame)
    # The list's size doesn't depend on which achievements are checked
    list_size = len(build_list(raset, earned))
    while True:
        program, _ = compile_offline(rest)
        _, _, _, achievements = program_info(program)
        if not achievements or set_memory(program, frame_program, list_size) <= ACH_MEMORY:
            break
        # too big for the console: leave out the biggest achievement
        biggest = max(achievements, key=lambda a: a[1] + a[2] * 4)[0]
        rest = [t for t in rest if t[0] != biggest]
    if len(program) % 4 or len(frame_program) % 4:
        raise FormatError("program size isn't a multiple of 4")
    n_ach = program_info(program)[1] + (program_info(frame_program)[1] if frame_program else 0)
    checked = [a[0] for a in achievements] + [t[0] for t in frame]
    body = program + frame_program + build_list(raset, earned, checked)
    header = SET_HEADER.pack(SET_MAGIC, SET_VERSION, SET_HEADER.size, code.encode(), raset.id,
                             zlib.crc32(body) & 0xFFFFFFFF, n_ach, 0, len(program), state_size(program),
                             len(body) - len(program) - len(frame_program), len(frame_program), b"")
    return header + body


def read_set(data):
    """{'code', 'game_id', 'stamp', 'achievements': [{'id'}], 'program',
    'state_size', 'frame_program', 'frame': [ids], 'pass': [ids], 'list':
    read_list()'s}. Version 3 sets (no frame lane) too."""
    if len(data) < SET_HEADER.size or data[:4] != SET_MAGIC:
        raise FormatError("not an offline set")
    (_, version, hsize, code, game_id, stamp, count, _flags,
     program_size, state, list_size, frame_size, _) = SET_HEADER.unpack_from(data)
    if version not in (3, 4):
        raise FormatError(f"offline set version {version}")
    if version == 3:
        frame_size = 0
    body = data[hsize:hsize + program_size + frame_size + list_size]
    if len(body) != program_size + frame_size + list_size or zlib.crc32(body) & 0xFFFFFFFF != stamp:
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
            'frame': frame, 'pass': passes, 'list': read_list(body[program_size + frame_size:])}


# -- which set the console runs ------------------------------------------------------

KNOWN_SETS_KEEP = 64


def _known_path(ra_dir):
    if ra_dir is None:
        from . import ra_set
        ra_dir = ra_set.RA_DIR
    return os.path.join(ra_dir, "cache", "console_sets.json")


def remember_set(data, ra_dir=None):
    """Notes which achievements a set DSiRPC built checks in which lane, by
    its stamp (ra/cache/console_sets.json; the last KNOWN_SETS_KEEP)."""
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
    """{'code', 'game_id', 'frame': set of ids, 'pass': set of ids} of a set
    DSiRPC built, by its stamp (an int), or None."""
    try:
        with open(_known_path(ra_dir), encoding="utf-8") as f:
            entry = json.load(f).get(f"{stamp:08X}")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(entry, dict):
        return None
    return {'code': entry.get('code'), 'game_id': entry.get('game_id', 0),
            'frame': set(entry.get('frame') or ()), 'pass': set(entry.get('pass') or ())}


def set_stamp(data):
    return struct.unpack_from("<I", data, 16)[0]


# -- the exchange ---------------------------------------------------------------

def parse_request(header, rest_reader):
    """Reads a request: header is its first REQUEST.size bytes, rest_reader(n)
    returns the next n bytes. -> (game code or None, {code: stamp}, unlock bytes)."""
    magic, version, cached, game, unlock_bytes, _ = REQUEST.unpack(header)
    if magic != b"DRSQ" or version != VERSION:
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
    return (game.decode() if valid_code(game) else None), stamps, unlocks


def build_request(game, stamps, unlocks):
    """A request as the launcher sends it (for tests)."""
    head = REQUEST.pack(b"DRSQ", VERSION, len(stamps), (game or "").encode().ljust(4, b"\0")[:4],
                        len(unlocks), 0)
    return head + b"".join(struct.pack("<4sI", c.encode(), s) for c, s in stamps.items()) + unlocks


def build_answer(status, taken, sets):
    """sets: [(code, .DRS bytes)]."""
    out = [ANSWER_HEADER.pack(b"DRSA", VERSION, status, taken, len(sets), 0)]
    for code, data in sets:
        out.append(struct.pack("<4sI", code.encode(), len(data)))
        out.append(data)
    return b"".join(out)
