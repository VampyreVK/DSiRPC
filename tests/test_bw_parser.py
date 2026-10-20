"""core/bw_parser.py on helpers/bw_fake.py's made-up Black and White RAM:
the trainer, the party (encrypted Gen V Pokemon), the field, a battle, the
Continue menu, the wrong game, and the gait from the player's movement."""

import struct

import pytest

from core.bw_parser import BWParser, WHITE_SHIFT
from helpers import bw_fake


@pytest.fixture(autouse=True)
def fresh_parser():
    BWParser._player_slot.clear()   # (a cache shared by every parser: each test starts without it)
    yield
    BWParser._player_slot.clear()


def parse(version="Black", **kw):
    return BWParser(bw_fake.make(version, **kw), None, version).parse()


@pytest.mark.parametrize("version", ["Black", "White"])
def test_trainer_and_field(version):
    d = parse(version)
    assert d["kind"] == "bw" and d["version"] == version
    assert (d["trainer_name"], d["character"], d["trainer_id"], d["secret_id"]) == ("Hilda", "Hilda", 12345, 54321)
    assert d["money"] == 23456 and d["badges"] == ["Trio", "Basic", "Insect"]
    assert d["playtime"] == {"hours": 15, "minutes": 42, "seconds": 7}
    loc = d["location"]
    assert (d["zone"], loc["name"], loc["x"], loc["z"]) == (0x1C, "Castelia City", 300, 512)
    assert loc["facing"] == "right" and loc["gait"] == "stand"
    assert loc["weather_kind"] == "rain" and d["season"] == "autumn"
    assert d["pokedex"] == {"obtained": True, "national": True, "seen": 8, "caught": 5}
    assert d["misc"]["clock"] == "2026-10-09 21:05" and d["misc"]["clock_source"] == "game"
    assert d["misc"]["music_id"] == 0x400 and not d["battle"]["active"]


def test_party():
    party = parse("White")["party"]
    assert [(m["slot"], m["species"], m["nickname"], m["level"], m["curr_hp"], m["max_hp"]) for m in party] == [
        (1, "Oshawott", "Oshawott", 18, 44, 52), (2, "Pidove", "Pidove", 12, 30, 33),
        (3, "Zorua", "Zorua", 20, 0, 50), (4, "Volcarona", "Egg", 1, 10, 10)]
    assert all(m["checksum_ok"] for m in party)
    assert party[1]["gender"] == "F" and party[1]["item"] == "Oran Berry"
    assert party[2]["shiny"] and not party[0]["shiny"]          # PID high half = TID ^ SID
    assert party[3]["egg"] and not party[2]["egg"]
    assert [mv for mv in party[0]["moves"] if mv] and party[0]["ot_name"] == "VIV"


def test_clock_from_the_second_place():
    d = parse(rtc_at=1)
    assert d["misc"]["clock"] == "2026-10-09 21:05"
    d = parse(rtc=None)
    assert d["misc"]["clock_source"] == "pc"


def test_trainer_battle():
    b = parse("White", battle=True, wild=False)["battle"]
    assert b["active"] and not b["wild"] and b["style"] == "single" and b["trainer_id"] == 77
    assert [(m["side"], m["species_id"], m["level"], m["curr_hp"], m["max_hp"], m["pp"]) for m in b["mons"]] == [
        ("yours", 501, 18, 40, 52, [23, 30]), ("foe", 506, 9, 20, 28, [35, 30])]
    assert b["pointer"] == hex(0x0226D6A4 + WHITE_SHIFT)


def test_wild_battle():
    b = parse("Black", battle=True, wild=True)["battle"]
    assert b["active"] and b["wild"] and b["trainer_id"] == 0


def test_continue_menu_and_other_games():
    p = BWParser(bw_fake.make("White", zone=0, field=False), None, "White")
    assert p.parse() is None and p.on_menu                     # the save loaded, no field yet
    # In Black City (zone 0 too), the player is there
    d = parse("White", zone=0, player_slot=0, facing=1)
    assert d and d["location"]["facing"] == "down"
    assert BWParser(bytes(0x400000), None, "Black").parse() is None      # not Black/White
    assert BWParser(bw_fake.make("White"), None, "Black").parse() is None  # White read as Black


def test_damaged_party_is_not_black_white():
    ram = bytearray(bw_fake.make("Black"))
    for i in range(4):   # every party slot's encrypted data scrambled
        o = BWParser.PARTY + i * 0xDC - 0x02000000 + 8
        ram[o:o + 128] = bytes((b ^ 0x5A) for b in ram[o:o + 128])
    assert BWParser(bytes(ram), None, "Black").parse() is None


@pytest.mark.parametrize("dx,secs,form,gait", [
    (0.0, 1.0, None, "stand"),
    (3.75, 1.0, None, "walk"),
    (7.5, 1.0, None, "run"),
    (7.5, 1.0, "bike", "bike"),
    (0.0, 1.0, "bike", "bike_stop"),
    (3.0, 1.0, "surf", "surf"),
    (300.0, 1.0, None, "stand"),        # a warp, not a sprint
])
def test_gait(dx, secs, form, gait):
    before = {"fx": (10.0, 20.0), "at": 100.0, "moved": ("walk", 90.0)}
    loc = {"fx": (10.0 + dx, 20.0), "form": form}
    BWParser.motion(before, loc, 100.0 + secs)
    assert loc["gait"] == gait and loc["at"] == 100.0 + secs
    # The last way you moved carries on through a stop (for Discord)
    assert loc["moved"] == ((gait, 100.0 + secs) if gait in ("walk", "run", "bike") else ("walk", 90.0))


def test_gait_needs_a_time_between():
    loc = {"fx": (15.0, 20.0), "form": None}
    BWParser.motion({"fx": (10.0, 20.0), "at": 100.0}, loc, 100.01)   # too soon to tell
    assert loc["gait"] == "stand"
    loc = {"fx": (15.0, 20.0), "form": None}
    BWParser.motion({}, loc, 5.0)                                      # nothing to compare with
    assert loc["gait"] == "stand"


def _read(ram, ranges):
    return [bytes(ram[a - 0x02000000:a - 0x02000000 + n]) for a, n in ranges]


def test_quick_reads_follow_the_battle():
    ram = bytearray(bw_fake.make("White", battle=True, wild=False))
    last = BWParser(bytes(ram), None, "White").parse()
    foe = int(last["battle"]["mons"][1]["battler"], 16) - 0x02000000
    struct.pack_into("<H", ram, foe + BWParser.B_SPECIES + 4, 3)                  # the foe's HP: 3
    ram[foe + BWParser.B_MOVES + 2] = 29                                         # its first move's PP: 29
    got = BWParser.apply_quick(last, _read(ram, BWParser.quick_ranges(last, "White")))
    assert got["battle"]["mons"][1]["curr_hp"] == 3 and got["battle"]["mons"][1]["pp"] == [29, 30]
    assert got["battle"]["mons"][0] == last["battle"]["mons"][0] and last["battle"]["mons"][1]["curr_hp"] == 20
    # Anything else needs a full read: someone switched in, the battle ended
    switched = bytearray(ram)
    struct.pack_into("<I", switched, BWParser.BATTLERS + WHITE_SHIFT + 4 * 7 - 0x02000000, 0x02280000)
    assert BWParser.apply_quick(last, _read(switched, BWParser.quick_ranges(last, "White"))) is None
    ended = bytearray(ram)
    ended[BWParser.IN_BATTLE + WHITE_SHIFT - 0x02000000] = 0
    assert BWParser.apply_quick(last, _read(ended, BWParser.quick_ranges(last, "White"))) is None


def test_field_reads_follow_the_player():
    ram = bytearray(bw_fake.make("White", player_slot=2, facing=3))
    obj = BWParser.MAP_OBJECTS + WHITE_SHIFT + 2 * 0x100 - 0x02000000
    struct.pack_into("<iii", ram, obj + BWParser.O_POSITION, int(300.5 * 65536), 0, int(512.5 * 65536))
    last = BWParser(bytes(ram), None, "White").parse()
    last["location"]["at"] = 100.0
    assert last["location"]["fx"] == (300.5, 512.5)
    # A second later: 3.75 tiles on, facing up
    struct.pack_into("<iii", ram, obj + BWParser.O_POSITION, int(304.25 * 65536), 0, int(512.5 * 65536))
    ram[obj + BWParser.O_FACING] = 0
    got = BWParser.apply_field(last, _read(ram, BWParser.field_ranges(last, "White")), 101.0)
    assert (got["location"]["gait"], got["location"]["facing"], got["location"]["x"]) == ("walk", "up", 304)
    # Another map, a battle, or the object gone: a full read instead
    for o, v in ((BWParser.ZONE + WHITE_SHIFT - 0x02000000, 0x1D), (BWParser.IN_BATTLE + WHITE_SHIFT - 0x02000000, 0x41),
                 (obj, 0x01)):
        changed = bytearray(ram)
        changed[o] = v
        assert BWParser.apply_field(last, _read(changed, BWParser.field_ranges(last, "White")), 101.0) is None
