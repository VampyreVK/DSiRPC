"""The launcher's RetroAchievements hash (launcher/source/md5.c and
romhash.c) against DSiRPC's own (core/ra_hash.py, rcheevos' recipe) on
made-up ROMs and, when it's there, a real one; and the first-time setup that
hashes each game once and keeps it in games.idx (picker.c's picker_setup()),
the hashes it sends DSiRPC, and what it keeps of DSiRPC's answer
(picker_store_status()). Built for the PC with tests/c/ui's host."""

import hashlib
import os
import struct

import pytest

from core import ra_hash
from helpers import REPO, launcher_ui as lui

ADME = os.path.join(REPO, "__pycache__", "Animal Crossing - Wild World (USA) (Rev 1).nds")
ADME_HASH = "2936fbd18b66f56ac472231c4becbcd1"


@pytest.fixture(scope="module")
def host(cc, tmp_path_factory):
    return lui.build(str(tmp_path_factory.mktemp("ui") / "ui_host"))


def made_rom(path, arm9=0x1234, arm7=0x777, icon_at=None, unit=0, supercard=False, size=None, seed=1):
    """A ROM with its ARM9 and ARM7 code (pseudo-random bytes) where its
    header says, and an icon block at icon_at (default: after the code)"""
    import random
    rnd = random.Random(seed)
    arm9_at, arm7_at = 0x4000, 0x4000 + arm9 + 0x100
    icon = arm7_at + arm7 + 0x40 if icon_at is None else icon_at
    total = size if size is not None else icon + 0xA00 + 0x200
    body = bytearray(rnd.getrandbits(8) for _ in range(total))
    head = bytearray(body[:512])
    head[0x0C:0x10] = b"TEST"
    head[0x12] = unit
    struct.pack_into("<I", head, 0x20, arm9_at)
    struct.pack_into("<I", head, 0x2C, arm9)
    struct.pack_into("<I", head, 0x30, arm7_at)
    struct.pack_into("<I", head, 0x3C, arm7)
    struct.pack_into("<I", head, 0x68, icon)
    body[:512] = head
    if supercard:
        sc = bytearray(512)
        sc[0:4] = b"\x2E\x00\x00\xEA"
        sc[0xB0:0xB4] = b"\x44\x46\x96\x00"
        body = sc + body
    with open(path, "wb") as f:
        f.write(bytes(body))
    return path


def host_hash(host, path):
    [line] = [ln for ln in lui.run(host, f"hash {path}") if ln.startswith("hash ")]
    _, result, md5 = line.split()
    return int(result), md5


def test_md5_matches_hashlib(host, tmp_path):
    # through the whole recipe, a ROM whose parts are sizes MD5 has to pad
    for n, (a9, a7) in enumerate([(0x40, 0x40), (0x3F, 0x41), (0x12345, 0x6789), (1, 0), (0, 0)]):
        path = made_rom(str(tmp_path / f"r{n}.nds"), a9, a7, seed=n)
        assert host_hash(host, path) == (1, ra_hash.nds_hash(path))


@pytest.mark.parametrize("kind", ["plain", "dsi", "supercard", "short_icon", "icon_past_end", "code_past_end"])
def test_same_as_ra_hash(host, tmp_path, kind):
    path = str(tmp_path / f"{kind}.nds")
    if kind == "plain":
        made_rom(path)
    elif kind == "dsi":
        made_rom(path, unit=3)                      # DSi-enhanced: the same recipe
    elif kind == "supercard":
        made_rom(path, supercard=True)
    elif kind == "short_icon":
        made_rom(path, icon_at=0x5000, size=0x5000 + 0x300)        # the file ends inside the icon block
    elif kind == "icon_past_end":
        made_rom(path, icon_at=0x900000)
    elif kind == "code_past_end":
        made_rom(path, arm9=0x8000, size=0x6000)    # a trimmed file: zeros for what's missing
    assert host_hash(host, path) == (1, ra_hash.nds_hash(path))


def test_refused_like_rcheevos(host, tmp_path):
    big = made_rom(str(tmp_path / "big.nds"), arm9=12 * 1024 * 1024, arm7=5 * 1024 * 1024, size=0x6000)
    with pytest.raises(ra_hash.HashError):
        ra_hash.nds_hash(big)
    assert host_hash(host, big) == (0, "-")
    short = tmp_path / "short.nds"
    short.write_bytes(b"\0" * 100)
    assert host_hash(host, str(short)) == (0, "-")
    assert host_hash(host, str(tmp_path / "missing.nds")) == (-1, "-")


@pytest.mark.skipif(not os.path.exists(ADME), reason="the Animal Crossing ROM isn't there")
def test_real_rom(host):
    assert ra_hash.nds_hash(ADME) == ADME_HASH
    assert host_hash(host, ADME) == (1, ADME_HASH)


# -- the first-time setup, games.idx and the sync's records -------------------------------

def index_lines(sd):
    with open(os.path.join(sd, "DSiRPC", "games.idx"), encoding="utf-8") as f:
        return f.read().splitlines()


def setup(host, sd):
    [line] = [ln for ln in lui.run(host, f"setup {sd}") if ln.startswith("setup ")]
    return tuple(int(x) for x in line.split()[1:])


def test_setup_hashes_once(host, tmp_path):
    sd = str(tmp_path / "sd")
    lui.make_sd(sd)
    n = len(lui.GAMES)
    assert setup(host, sd) == (n, n, 1)               # every game, with the card up
    lines = index_lines(sd)
    assert lines[0] == "DSiRPC games 2"
    games = os.path.join(sd, "roms", "nds")
    for name, *_ in lui.GAMES:
        line = next(ln for ln in lines if ln.split("\t")[0].endswith(name))
        fields = line.split(" ")
        assert fields[6] == ra_hash.nds_hash(os.path.join(games, name)) and fields[7] == "0"
    assert setup(host, sd) == (0, 0, 0)               # nothing new: nothing shown
    # A new file, and one replaced under the same name (another size): only those
    lui.write(os.path.join(games, "New Game.nds"), lui.rom("NEWE", "New Game\nSomeone"))
    lui.write(os.path.join(games, "Tetris DS.nds"), lui.rom("ATRE", "Tetris DS\nNintendo", version=1) + b"\0" * 64)
    assert setup(host, sd) == (2, 2, 1)
    assert setup(host, sd) == (0, 0, 0)


def test_old_index_and_unhashable(host, tmp_path):
    sd = str(tmp_path / "sd")
    lui.make_sd(sd)
    # games.idx from before hashes: its names and favorites kept, every game hashed once
    lui.run(host, f"favorite {sd}|{os.path.join(sd, 'roms', 'nds', 'Tetris DS.nds')}")
    lines = index_lines(sd)
    old = ["DSiRPC games 1"] + [" ".join(ln.split(" ")[:6] + ln.split(" ")[8:]) for ln in lines[1:]]
    with open(os.path.join(sd, "DSiRPC", "games.idx"), "w", encoding="utf-8") as f:
        f.write("\n".join(old) + "\n")
    n = len(lui.GAMES)
    assert setup(host, sd) == (n, n, 1)
    tetris = next(ln for ln in index_lines(sd) if "Tetris DS.nds" in ln)
    assert tetris.split(" ")[3] == "1"                # still a favorite
    # One that can't be hashed (its code over 16 MB): marked, not tried again
    made_rom(os.path.join(sd, "roms", "nds", "Broken.nds"), arm9=12 << 20, arm7=5 << 20, size=0x6000)
    assert setup(host, sd) == (1, 0, 1)
    assert next(ln for ln in index_lines(sd) if "Broken.nds" in ln).split(" ")[6] == "!"
    assert setup(host, sd) == (0, 0, 0)


def roms(host, sd, started=None):
    out = lui.run(host, f"roms {sd}" + (f"|{started}" if started else ""))
    assert out[-1].startswith("roms ") and out[-1].endswith(" 1")      # (the records' sizes add up)
    return [ln.split(" ", 4)[1:] for ln in out if ln.startswith("rom ")]


def test_hashes_for_the_sync_and_the_answer(host, tmp_path):
    sd = str(tmp_path / "sd")
    lui.make_sd(sd)
    assert roms(host, sd) == []                       # nothing hashed yet
    setup(host, sd)
    games = os.path.join(sd, "roms", "nds")
    started = os.path.join(games, "Pokemon Platinum.nds")
    got = roms(host, sd, started)
    assert len(got) == len(lui.GAMES)
    want = {code: ra_hash.nds_hash(os.path.join(games, name)) for name, code, *_ in lui.GAMES}
    assert {code: md5 for code, md5, _, _ in got} == want
    assert [code for code, _, flag, _ in got if flag == "1"] == ["CPUE"]
    assert {code: name for code, _, _, name in got}["ADME"] == "Animal Crossing WW"     # the file's name, for DSiRPC

    # DSiRPC's answer: Platinum has a set, RetroAchievements has ADME but
    # not this file. ADME's set on the SD card (from a link by title) goes;
    # Platinum's stays
    sets = os.path.join(sd, "DSiRPC", "sets")
    with open(os.path.join(sets, "CPUE.DRS"), "rb") as f:
        lui.write(os.path.join(sets, "ADME.DRS"), f.read().replace(b"CPUE", b"ADME", 1))
    out = lui.run(host, f"status {sd}|{want['CPUE']}:1,{want['ADME']}:2")
    assert "status 1" in out
    assert os.path.exists(os.path.join(sets, "CPUE.DRS")) and not os.path.exists(os.path.join(sets, "ADME.DRS"))
    by_name = {ln.split("\t")[0].rsplit("/", 1)[-1]: ln.split(" ")[7] for ln in index_lines(sd)[1:]}
    assert by_name["Pokemon Platinum.nds"] == "1" and by_name["Animal Crossing WW.nds"] == "2"
    assert by_name["Tetris DS.nds"] == "0"
    # The game list: no count, and the file's own name (a hack keeps the original's banner)
    rows = {ln.split("|")[0][5:]: ln.split("|") for ln in lui.run(host, f"games {sd}|1") if ln.startswith("game ")}
    assert rows["ADME"][6] == "0/0" and rows["ADME"][1] == "Animal Crossing WW" and rows["ADME"][7] == "no set"
    assert rows["CPUE"][1].endswith("Platinum Version")          # (a game with a set: its banner's name, as before)
    # A game it doesn't have at all goes the same way
    lui.run(host, f"status {sd}|{want['ADME']}:3")
    assert {ln.split("|")[0][5:]: ln.split("|")[1] for ln in lui.run(host, f"games {sd}|1")
            if ln.startswith("game ")}["ADME"] == "Animal Crossing WW"
    # And a hash it never sent stays unknown
    assert setup(host, sd) == (0, 0, 0)
    assert hashlib.md5(b"").hexdigest() not in "".join(index_lines(sd))


def badges(host, sd):
    """The list's [(code, shown name, badge: "count", "new" or "no set")]"""
    return [(r[0], r[1], r[7]) for r in (ln[5:].split("|") for ln in lui.run(host, f"games {sd}|1")
                                         if ln.startswith("game "))]


def test_every_file_gets_a_state(host, tmp_path):
    """Homebrew with no game code ("####", or four zero bytes), a hack sharing
    its original's code, a commercial game never started, and a file that
    can't be hashed RetroAchievements' way: every hashed file goes to DSiRPC
    by its hash, the unhashable one is "no set" without asking anything, and
    after DSiRPC's answer nothing is "new"; only a hash DSiRPC couldn't check
    (RetroAchievements out of reach) stays "new"."""
    sd = str(tmp_path / "sd")
    lui.make_sd(sd)
    games = os.path.join(sd, "roms", "nds")
    lui.write(os.path.join(games, "Homebrew A.nds"), lui.rom("####", "Homebrew A\nSomeone"))
    zero = bytearray(lui.rom("ZZZZ", "Homebrew B\nSomeone else"))
    zero[0x0C:0x10] = b"\0\0\0\0"
    lui.write(os.path.join(games, "Homebrew B.nds"), bytes(zero))
    lui.write(os.path.join(games, "Platinum Hack.nds"), lui.rom("CPUE", "Pokemon Platinum Version\nA hacker", "ball"))
    made_rom(os.path.join(games, "Too Big.nds"), arm9=12 << 20, arm7=5 << 20, size=0x6000)
    n = len(lui.GAMES) + 4
    assert setup(host, sd) == (n, n - 1, 1)
    # Before any sync: the unhashable one is already "no set", the rest "new"
    # (Platinum, with its set on the card, its count)
    before = badges(host, sd)
    assert [b for c, _, b in before if c == "TEST"] == ["no set"]
    assert all(b == "new" for c, name, b in before if c not in ("TEST", "CPUE"))
    # Every hashed file goes to DSiRPC, homebrew too (no code), the hack apart from Platinum
    got = roms(host, sd)
    assert len(got) == n - 1 and "TEST" not in [c for c, *_ in got]
    homebrew = {name: md5 for code, md5, _, name in got if code == ""}
    assert set(homebrew) == {"Homebrew A", "Homebrew B"} and len(set(homebrew.values())) == 2
    platinum = {name: md5 for code, md5, _, name in got if code == "CPUE"}
    assert set(platinum) == {"Pokemon Platinum", "Platinum Hack"} and len(set(platinum.values())) == 2
    # DSiRPC's answer: Platinum has a set, the hack not this ROM, homebrew no
    # game, the rest a set or none; one it couldn't check (0)
    answer = {md5: (1 if name in ("Pokemon Platinum", "Tetris DS") else 2 if name == "Platinum Hack"
                    else 0 if name == "Mario Kart DS" else 3) for _, md5, _, name in got}
    lui.run(host, f"status {sd}|" + ",".join(f"{m}:{s}" for m, s in answer.items()))
    after = {name: (code, b) for code, name, b in badges(host, sd)}
    assert after["Homebrew A"] == ("-", "no set") and after["Homebrew B"] == ("-", "no set")
    assert after["Platinum Hack"] == ("CPUE", "no set")
    assert after["Pokemon Platinum Version"] == ("CPUE", "count")          # (its set stays: the hack's doesn't count)
    assert os.path.exists(os.path.join(sd, "DSiRPC", "sets", "CPUE.DRS"))
    assert [name for name, (_, b) in after.items() if b == "new"] == ["Mario Kart DS"]
    # The unhashable one and homebrew read "No achievement set" on X (status 3)
    by_name = {ln.split("\t")[0].rsplit("/", 1)[-1]: ln.split(" ")[7] for ln in index_lines(sd)[1:]}
    assert by_name["Too Big.nds"] == "3" and by_name["Homebrew A.nds"] == "3" and by_name["Homebrew B.nds"] == "3"
