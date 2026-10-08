"""
offline.py - the files and messages for playing without DSiRPC nearby
(offline play): achievements are kept on the console's SD card and handed to
DSiRPC the next time the launcher finds it. DSiRPC does all the work; the
console only stores what it's given and what it unlocked.

On the SD card (the launcher writes them; see launcher/source/sync.c):

    sd:/RPCUNLK.BIN       unlocks waiting for DSiRPC (the in-game side will
                          write them; read and cleared by the launcher)
    <launcher>/sets/CODE.DRS
                          each game's achievements, from DSiRPC (build_set())
    sd:/RPCSET.BIN        the set of the game being started (a copy, so the
                          in-game side only needs a fixed name in the root)

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
list; the launcher zeroes the slots once DSiRPC has them.

CODE.DRS (an offline set, version 1), little-endian:

    header (32 bytes): "DRSE", u16 version, u16 header size, 4 game code,
        u32 RA game ID, u32 stamp (CRC-32 of everything after the header),
        u16 achievement count, u16 flags, u32 table offset, u32 strings offset
    table: per achievement u32 ID, u16 points, u16 flags (1: reads through a
        pointer, 2: from a bonus set), u32 offset of its condition string
        (from the strings offset)
    strings: the conditions, in RetroAchievements' MemAddr text, NUL-terminated

Only the achievements left to unlock (as far as DSiRPC knows) that the
console can check are in it: official, from the core or a bonus set, reading
only main RAM, and that rcheevos parses. The launcher never looks past the
header; the stamp tells it whether its copy is current.

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
SET_HEADER = struct.Struct("<4sHH4sIIHHII")
SET_ENTRY = struct.Struct("<IHHI")
SET_INDIRECT = 1
SET_BONUS = 2

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

def build_set(raset, code, skip_ids=(), check=None):
    """The offline set for a game (bytes), from its RaSet. skip_ids: the
    achievements already unlocked. check: fn(memaddr) -> True if the console
    can check it (by default, anything reading only main RAM)."""
    from .ra_game import _unreachable
    entries, strings = [], bytearray()
    for a in raset.playable_achievements:
        if a["id"] in skip_ids or not a["memaddr"] or _unreachable(a["memaddr"]):
            continue
        if check is not None and not check(a["memaddr"]):
            continue
        flags = (SET_INDIRECT if "I:" in a["memaddr"] else 0) | (SET_BONUS if a["set_type"] == "bonus" else 0)
        entries.append((a["id"], min(a["points"], 0xFFFF), flags, len(strings)))
        strings += a["memaddr"].encode("ascii", "replace") + b"\0"
    table = b"".join(SET_ENTRY.pack(*e) for e in entries)
    body = table + bytes(strings)
    table_offset = SET_HEADER.size
    header = SET_HEADER.pack(SET_MAGIC, VERSION, SET_HEADER.size, code.encode(), raset.id,
                             zlib.crc32(body) & 0xFFFFFFFF, len(entries), 0,
                             table_offset, table_offset + len(table))
    return header + body


def read_set(data):
    """{'code', 'game_id', 'stamp', 'achievements': [{'id', 'points', 'flags', 'memaddr'}]}."""
    if len(data) < SET_HEADER.size or data[:4] != SET_MAGIC:
        raise FormatError("not an offline set")
    (_, version, hsize, code, game_id, stamp, count, _flags,
     table_offset, strings_offset) = SET_HEADER.unpack_from(data)
    if version != VERSION:
        raise FormatError(f"offline set version {version}")
    if zlib.crc32(data[hsize:]) & 0xFFFFFFFF != stamp:
        raise FormatError("offline set damaged (stamp doesn't match)")
    achievements = []
    for i in range(count):
        aid, points, flags, offset = SET_ENTRY.unpack_from(data, table_offset + i * SET_ENTRY.size)
        start = strings_offset + offset
        end = data.index(b"\0", start)
        achievements.append({'id': aid, 'points': points, 'flags': flags,
                             'memaddr': data[start:end].decode("ascii")})
    return {'code': code.decode(), 'game_id': game_id, 'stamp': stamp, 'achievements': achievements}


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
