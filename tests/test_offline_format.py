"""core/offline.py's files and messages for offline play: RPCUNLK.BIN's
unlock slots, the .DRS sets (lanes, list, stamp, the console's memory
limit), the launcher's sync request and answer, and which set the console
runs (console_sets.json)."""

import datetime
import json
import struct
import zlib

import pytest

from core import offline, ra_set
from helpers import gen_set

NOW = datetime.datetime(2026, 10, 19, 12, 0, 0).timestamp()


def _clock(dt):
    return offline.console_clock(dt.timestamp())


def _unlock_file(slots):
    data = bytearray(offline.empty_unlock_file())
    for i, slot in enumerate(slots, start=1):
        data[i * offline.UNLOCK_SLOT:(i + 1) * offline.UNLOCK_SLOT] = slot
    return bytes(data)


# -- RPCUNLK.BIN ---------------------------------------------------------------

def test_empty_unlock_file():
    data = offline.empty_unlock_file()
    assert len(data) == offline.UNLOCK_FILE_SIZE == 4096
    assert data[:10] == b"DRUL\x01\x00\x10\x00\x00\x01"   # what probe_ach.c and the launcher write
    assert offline.read_unlocks(data, now=NOW) == [] and offline.count_unlocks(data) == 0


def test_unlocks_read_oldest_first():
    t1 = _clock(datetime.datetime(2026, 10, 18, 9, 30))
    t2 = _clock(datetime.datetime(2026, 10, 18, 21, 5))
    data = _unlock_file([offline.unlock_slot(1002, "IRBO", t2, 1),
                         offline.unlock_slot(1001, "IRBO", t1, 2),
                         offline.unlock_slot(55, "CPUE", t1, 3)])
    got = offline.read_unlocks(data, now=NOW)
    assert [(u["id"], u["code"], u["seq"]) for u in got] == [(1001, "IRBO", 2), (55, "CPUE", 3), (1002, "IRBO", 1)]
    assert got[0]["when"] == int(datetime.datetime(2026, 10, 18, 9, 30).timestamp())
    assert offline.count_unlocks(data) == 3


def test_damaged_empty_and_repeated_slots():
    when = _clock(datetime.datetime(2026, 10, 18, 9, 30))
    torn = bytearray(offline.unlock_slot(7, "IRBO", when, 2))
    torn[8] ^= 1                                              # written halfway: the check fails
    data = _unlock_file([offline.unlock_slot(5, "IRBO", when, 1), bytes(torn),
                         offline.unlock_slot(0, "IRBO", when, 3),       # empty
                         offline.unlock_slot(9, "irbo", when, 4),       # not a game code
                         offline.unlock_slot(5, "IRBO", when + 60, 5),  # a repeat
                         offline.unlock_slot(5, "IRAO", when, 6)])      # the same ID, another game
    got = offline.read_unlocks(data, now=NOW)
    assert [(u["id"], u["code"]) for u in got] == [(5, "IRBO"), (5, "IRAO")]
    assert offline.count_unlocks(data) == 3                   # what the launcher counts: repeats too


def test_a_wrong_clock_becomes_now():
    future = _clock(datetime.datetime(2030, 1, 1))
    past = _clock(datetime.datetime(2015, 1, 1))
    data = _unlock_file([offline.unlock_slot(1, "IRBO", future, 1), offline.unlock_slot(2, "IRBO", past, 2),
                         offline.unlock_slot(3, "IRBO", 0, 3)])
    assert {u["when"] for u in offline.read_unlocks(data, now=NOW)} == {int(NOW)}


def test_not_an_unlock_file():
    with pytest.raises(offline.FormatError):
        offline.read_unlocks(b"NOPE" + bytes(4092), now=NOW)
    wrong = bytearray(offline.empty_unlock_file())
    wrong[4] = 2                                              # version 2
    with pytest.raises(offline.FormatError):
        offline.read_unlocks(bytes(wrong), now=NOW)
    assert offline.read_unlocks(b"", now=NOW) == [] and offline.count_unlocks(b"") == 0


def test_console_clock_round_trip():
    for dt in (datetime.datetime(2000, 1, 1, 0, 0, 1), datetime.datetime(2026, 10, 19, 23, 59, 59),
               datetime.datetime(2099, 12, 31, 12, 0)):
        when = offline.console_clock(dt.timestamp())
        assert offline.console_time(when) == dt.timestamp()
    assert offline.console_clock(0) == offline.console_clock(None) == 0
    assert offline.console_clock(datetime.datetime(1999, 1, 1).timestamp()) == 0


# -- the menu's list -------------------------------------------------------------

def test_plain_text():
    assert offline.plain_text("Pokémon Café", 80) == "Pokemon Cafe"
    assert offline.plain_text("“Hi”—there… ★", 80) == '"Hi"-there... *'
    assert offline.plain_text("ポケモン  and\nmore", 80) == "???? and more"
    assert offline.plain_text("x" * 100, 20) == "x" * 17 + "..."
    assert offline.plain_text(None, 10) == ""


def test_list_round_trip():
    s = ra_set.RaSet(gen_set.make_set(30, seed=3))
    a0, a1 = s.playable_achievements[:2]
    earned_at = datetime.datetime(2026, 10, 1, 8, 0).timestamp()
    data = offline.build_list(s, earned={a0["id"]: earned_at, a1["id"]: 0}, checked=[a1["id"]])
    got = offline.read_list(data)
    assert [e["id"] for e in got] == [a["id"] for a in s.playable_achievements]
    assert got[0]["flags"] == offline.LIST_EARNED and got[0]["when"] == offline.console_clock(earned_at)
    assert got[1]["flags"] == offline.LIST_EARNED | offline.LIST_CHECKED and got[1]["when"] == 0
    assert all(e["flags"] == 0 and e["seq"] == 0 for e in got[2:])
    assert got[0]["title"] == a0["title"] and got[0]["points"] == a0["points"]
    # Repeated text is stored once
    magic, version, count, text_size, _ = offline.LIST_HEADER.unpack_from(data)
    assert text_size < sum(len(e["title"]) + len(e["description"]) + 2 for e in got)
    with pytest.raises(offline.FormatError):
        offline.read_list(data[:offline.LIST_HEADER.size + 4])


# -- .DRS sets ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def puzzle_set(rcheevos):
    s = ra_set.RaSet(gen_set.make_set(150, seed=2))
    return s, offline.build_set(s, "TEST")


def test_set_round_trip(puzzle_set):
    s, data = puzzle_set
    info = offline.read_set(data)
    assert info["code"] == "TEST" and info["game_id"] == s.id
    hsize = offline.SET_HEADER.size
    assert info["stamp"] == zlib.crc32(data[hsize:]) & 0xFFFFFFFF == offline.set_stamp(data)
    frame, passes = set(info["frame"]), set(info["pass"])
    assert frame and passes and not frame & passes
    assert frame | passes == {a["id"] for a in s.playable_achievements}
    # The two that can only be judged frame by frame (a one-frame flag, a
    # ResetIf on every rotation) are in the frame lane
    assert {gen_set.T_SPIN_SINGLE, gen_set.ONE_HAND} <= frame
    listed = {e["id"]: e["flags"] for e in info["list"]}
    assert all(listed[aid] & offline.LIST_CHECKED for aid in frame | passes)
    assert len(data) % 4 == 0


def test_set_leaves_out_unlocked(puzzle_set, rcheevos):
    s, _ = puzzle_set
    skip = {a["id"] for a in s.playable_achievements[:20]}
    info = offline.read_set(offline.build_set(s, "TEST", skip_ids=skip, earned={i: 0 for i in skip}))
    assert not skip & (set(info["frame"]) | set(info["pass"]))
    listed = {e["id"]: e["flags"] for e in info["list"]}
    assert all(listed[aid] == offline.LIST_EARNED for aid in skip)


def test_set_fits_the_consoles_memory(rcheevos):
    s = ra_set.RaSet(gen_set.make_set(900, seed=6))
    info = offline.read_set(offline.build_set(s, "BIGG"))
    need = offline.set_memory(info["program"], info["frame_program"], len(offline.build_list(s)))
    assert need <= offline.ACH_MEMORY
    assert 0 < len(info["frame"]) + len(info["pass"]) <= 900
    sample, check = offline.frame_costs(*offline.program_counts(info["frame_program"]))
    assert sample <= offline.FRAME_SAMPLE_CYCLES and check <= offline.FRAME_CHECK_CYCLES


def test_damaged_sets_refused(puzzle_set):
    _, data = puzzle_set
    damaged = bytearray(data)
    damaged[-5] ^= 0x10
    for bad in (bytes(damaged), b"XXXX" + data[4:], data[:40], data[:-4],
                data[:4] + struct.pack("<H", 2) + data[6:]):
        with pytest.raises(offline.FormatError):
            offline.read_set(bad)


def test_timing():
    assert offline.timing("0xH0100=1") == 1
    assert offline.timing("0xH0100=1_d0xH0100=0") == 2
    assert offline.timing("0xH0100=1_p0xH0100=0") == 2
    assert offline.timing("0xH0118>=5.30.") == 3
    assert offline.timing("0xH0100=1_R:0xH0111!=1") == 3
    assert offline.timing("0xH0100=1SP:0xH0111=1") == 3


# -- the launcher's sync ---------------------------------------------------------

def test_request_round_trip():
    unlocks = _unlock_file([offline.unlock_slot(1, "IRBO", 100, 1)])
    raw = offline.build_request("IRBO", {"IRBO": 0x1234, "CPUE": 0xABCD}, unlocks)
    pos = [offline.REQUEST.size]

    def reader(n):
        chunk = raw[pos[0]:pos[0] + n]
        pos[0] += n
        return chunk

    game, stamps, got = offline.parse_request(raw[:offline.REQUEST.size], reader)
    assert game == "IRBO" and stamps == {"IRBO": 0x1234, "CPUE": 0xABCD} and got == unlocks
    assert pos[0] == len(raw)
    # Connected, no game started yet
    raw2 = offline.build_request(None, {}, b"")
    assert offline.parse_request(raw2[:offline.REQUEST.size], lambda n: b"") == (None, {}, b"")


def test_bad_requests():
    good = offline.build_request("IRBO", {}, b"")
    for header in (b"XXXX" + good[4:offline.REQUEST.size],
                   good[:4] + struct.pack("<H", 9) + good[6:offline.REQUEST.size],
                   offline.REQUEST.pack(b"DRSQ", offline.VERSION, offline.MAX_CACHED + 1, b"IRBO", 0, 0),
                   offline.REQUEST.pack(b"DRSQ", offline.VERSION, 0, b"IRBO", offline.MAX_UNLOCK_BYTES + 1, 0)):
        with pytest.raises(offline.FormatError):
            offline.parse_request(header, lambda n: bytes(n))


def test_answer_layout():
    data = offline.build_answer(0, 3, [("IRBO", b"abcd"), ("CPUE", b"xy")])
    magic, version, status, taken, n, _ = offline.ANSWER_HEADER.unpack_from(data)
    assert (magic, version, status, taken, n) == (b"DRSA", offline.VERSION, 0, 3, 2)
    rest = data[offline.ANSWER_HEADER.size:]
    assert rest == b"IRBO" + struct.pack("<I", 4) + b"abcd" + b"CPUE" + struct.pack("<I", 2) + b"xy"


# -- which set the console runs ---------------------------------------------------

def test_known_sets(puzzle_set, tmp_path):
    _, data = puzzle_set
    info = offline.read_set(data)
    assert offline.known_set(info["stamp"], str(tmp_path)) is None
    offline.remember_set(data, str(tmp_path))
    known = offline.known_set(info["stamp"], str(tmp_path))
    assert known == {"code": "TEST", "game_id": info["game_id"], "frame": set(info["frame"]),
                     "pass": set(info["pass"])}
    offline.remember_set(b"not a set", str(tmp_path))         # ignored


def test_known_sets_keep_the_newest(puzzle_set, tmp_path):
    _, data = puzzle_set
    path = tmp_path / "cache" / "console_sets.json"
    path.parent.mkdir()
    old = {f"{i:08X}": {"code": "OLDS", "frame": [], "pass": [], "time": 1000 + i} for i in range(80)}
    path.write_text(json.dumps(old))
    offline.remember_set(data, str(tmp_path))
    kept = json.loads(path.read_text())
    assert len(kept) == offline.KNOWN_SETS_KEEP
    assert f"{offline.read_set(data)['stamp']:08X}" in kept and "00000000" not in kept
