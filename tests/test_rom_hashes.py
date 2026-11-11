"""Games linked by their RetroAchievements hash: the sync's version 2 (the
launcher's hashes and file names in the request, "still working" frames
while DSiRPC asks RetroAchievements and gets sets, what it has for each in
the answer; core/offline.py) with launchers and DSiRPCs from before and
after it (launcher/source/sync.c built for the PC, against ConsoleSync); what
DSiRPC keeps and asks (core/rom_hashes.py, app/engine.py's _console_roms()):
every hash asked at once, a few at a time, an outage leaving them unknown, a
game ID plus 1,000,000,000 taken as "not this ROM" (Animal Crossing: Wild
World (USA) got its European set because of it), a hash it doesn't know told
apart by the title, no set sent while a hash waits for its answer or when
there's none, the title link dropped, a set for every game that has one;
games RetroAchievements has no set for named by their file; and RALink
linking by the hash with no title fallback (core/ra_link.py)."""

import json
import logging
import os
import queue
import subprocess
import threading
import time
import types

import pytest

import app.engine as engine_module
from core import games, offline, ra_link, ra_set, rom_hashes
from core.console_sync import ConsoleSync
from helpers import C_DIR, REPO, cbuild, gen_set
from rpc import generic_presence, platinum_presence

LAUNCHER = os.path.join(REPO, "launcher", "source")
ADME_USA = "2936fbd18b66f56ac472231c4becbcd1"
CPUE = "11112222333344445555666677778888"
HACK = "99998888777766665555444433332222"


# -- the format ------------------------------------------------------------------------

def reader(data):
    at = [0]

    def read(n):
        at[0] += n
        return data[at[0] - n:at[0]]
    return read, at


def test_request_and_answer_round_trip():
    roms = [("ADME", ADME_USA, False, "Animal Crossing WW"), ("CPUE", CPUE, True, "Pokemon Platinum")]
    data = offline.build_request("CPUE", {"CPUE": 7}, b"", version=2, roms=roms, hashed=2, hash_ms=1500)
    read, at = reader(data)
    r = offline.parse_sync(read(offline.REQUEST.size), read)
    assert (r["version"], r["game"], r["stamps"], r["roms"], r["hashed"], r["hash_ms"]) == \
        (2, "CPUE", {"CPUE": 7}, roms, 2, 1500)
    assert at[0] == len(data)
    # version 1 has none of it, and parse_request() still gives what it did
    v1 = offline.build_request("CPUE", {}, b"")
    assert offline.parse_request(v1[:offline.REQUEST.size], lambda n: b"") == ("CPUE", {}, b"")
    assert [offline.sync_version(v) for v in (0, 1, 2, 3)] == [1, 1, 2, 2]
    # the answer: version 1 as before, version 2 with the statuses after the sets
    assert offline.build_answer(0, 0, [], 1, {ADME_USA: 2}) == offline.build_answer(0, 0, [])
    a2 = offline.build_answer(0, 0, [], 2, {ADME_USA: offline.RA_NOT_THIS_ROM})
    assert a2[offline.ANSWER_HEADER.size:] == b"\x01\x00" + bytes.fromhex(ADME_USA) + b"\x02\0\0\0"
    # and the "still working" frame before it
    assert offline.build_progress(3, 70, offline.PROGRESS_CHECKING) == b"DRSP\x03\x00\x46\x00\x01\0\0\0"


# -- the launcher's sync against ConsoleSync, old and new ---------------------------------

@pytest.fixture(scope="module")
def launchers(cc, tmp_path_factory):
    out = tmp_path_factory.mktemp("sync")
    src = [os.path.join(C_DIR, "sync", "sync_host.c"), os.path.join(LAUNCHER, "sync.c")]
    flags = ["-std=gnu11", "-I", LAUNCHER]
    return {"new": cbuild.build(str(out / "sync_new"), src, flags=flags),
            "old": cbuild.build(str(out / "sync_old"), src, flags=flags + ["-DSYNC_VERSION=1"])}


def run_launcher(exe, port, tmp_path, roms=()):
    hashes = tmp_path / "hashes.txt"
    hashes.write_text("".join(f"{c or '-'} {m} {int(s)} {n}\n" for c, m, s, n in roms))
    r = subprocess.run([exe, str(port), str(tmp_path / "sets"), str(tmp_path / "RPCUNLK.BIN"), "-", str(hashes)],
                       capture_output=True, text=True, env=cbuild.run_env(), timeout=120)
    lines = r.stdout.splitlines()
    head = next(ln for ln in lines if ln.startswith("sync ")).split()
    return [int(x) for x in head[1:]], {ln.split()[1]: int(ln.split()[2]) for ln in lines if ln.startswith("status ")}


TWO = [("ADME", ADME_USA, False, "Animal_Crossing_WW"), ("CPUE", CPUE, True, "Platinum"),
       ("", "aaaa0000aaaa0000aaaa0000aaaa0000", False, "Homebrew")]     # (no game code: four zero bytes)


@pytest.mark.parametrize("launcher,dsirpc", [("new", "new"), ("new", "old"), ("old", "new"), ("old", "old")])
def test_old_and_new(launchers, tmp_path, monkeypatch, launcher, dsirpc):
    if dsirpc == "old":
        monkeypatch.setattr(offline, "SYNC_VERSION", 1)   # DSiRPC before the hashes: it answers 1, reads 1
    seen = []

    def on_roms(roms, hashed, ms, progress):
        seen.append((roms, hashed, ms))
        for i in range(3):                             # still working...
            progress(i, 3, offline.PROGRESS_CHECKING)
        return {r[1]: (offline.RA_NOT_THIS_ROM if r[0] == "ADME" else offline.RA_NO_GAME if not r[0]
                       else offline.RA_SET) for r in roms}
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", on_roms=on_roms)
    sync.start()
    try:
        (r, version, *_, n), statuses = run_launcher(launchers[launcher], sync.port, tmp_path, TWO)
    finally:
        sync.stop()
    assert r == 1
    if launcher == dsirpc == "new":
        assert version == 2 and sync.last["version"] == 2
        assert seen == [(TWO, len(TWO), 1234)]      # (the host says it hashed every one, in 1234 ms)
        assert statuses == {ADME_USA: offline.RA_NOT_THIS_ROM, CPUE: offline.RA_SET, TWO[2][1]: offline.RA_NO_GAME}
        assert n == 3
    else:
        assert version == 1 and sync.last["version"] == 1 and seen == [] and statuses == {}


def test_progress_while_working(launchers, tmp_path):
    """Frames the launcher reads as it waits, at both steps, then the answer"""
    def on_roms(roms, hashed, ms, progress):
        for i in range(4):
            time.sleep(0.2)
            progress(i + 1, 4, offline.PROGRESS_CHECKING)
        return {}

    def sets(game, stamps, unlocks=(), progress=None):
        for i in range(3):
            progress(i + 1, 3, offline.PROGRESS_SETS)
        return []
    sync = ConsoleSync(sets, lambda u: None, port=0, host="127.0.0.1", on_roms=on_roms)
    sync.start()
    try:
        exe = launchers["new"]
        hashes = tmp_path / "hashes.txt"
        hashes.write_text(f"CPUE {CPUE} 1 P\n")
        out = subprocess.run([exe, str(sync.port), str(tmp_path / "sets"), str(tmp_path / "RPCUNLK.BIN"), "-",
                              str(hashes)], capture_output=True, text=True, env=cbuild.run_env(), timeout=120).stdout
    finally:
        sync.stop()
    assert "Checking games 4/4" in out and "Getting sets 3/3" in out
    assert next(ln for ln in out.splitlines() if ln.startswith("sync ")).split()[1:3] == ["1", "2"]


# -- what DSiRPC does with them --------------------------------------------------------------

def set_file(game_id, title):
    return {"Success": True, "GameId": game_id, "Title": title, "ConsoleId": 18, "RichPresencePatch": "",
            "Sets": [{"Type": "core", "Title": title, "Achievements": []}]}


@pytest.fixture
def ra_dir(tmp_path, monkeypatch):
    d = tmp_path / "ra"
    (d / "cache").mkdir(parents=True)
    monkeypatch.setattr(ra_set, "RA_DIR", str(d))
    (d / "ADME.json").write_text(json.dumps(set_file(9594, "Animal Crossing: Wild World")))
    return d


class Link:
    """RALink's side: what RetroAchievements says of each hash (None: out of
    reach) and whether it has a game by a code's title"""

    def __init__(self, answers, titles=None, delay=0.0):
        self.answers, self.titles, self.delay, self.asked = answers, titles or {}, delay, []
        self.lock = threading.Lock()

    def lookup_hash(self, md5, timeout=10.0):
        with self.lock:
            self.asked.append(md5)
        time.sleep(self.delay)
        return self.answers.get(md5)

    def title_has_game(self, code):
        return self.titles.get(code)


def engine(link):
    e = types.SimpleNamespace(ra_link=link, ra_enabled=True)
    e.roms = types.MethodType(engine_module.Engine._console_roms, e)
    return e


def test_animal_crossing_usa(ra_dir, caplog):
    """The bug: RetroAchievements answers 1,000,009,594 for the USA file of
    Animal Crossing (a hash it knows, that no set supports), which was taken
    as a game with a set: the European set kept going to the console"""
    link = Link({ADME_USA: 1_000_009_594, CPUE: 11732})
    with caplog.at_level(logging.INFO):
        got = engine(link).roms([("ADME", ADME_USA, False, "Animal Crossing WW"), ("CPUE", CPUE, True, "Platinum")],
                                2, 1500)
    assert got == {ADME_USA: rom_hashes.NOT_THIS_ROM, CPUE: rom_hashes.HAS_SET}
    assert "the launcher hashed 2 game(s) in 1.5 s" in caplog.text
    assert f"no set for Animal Crossing WW (ADME, hash {ADME_USA}): it has the game, but not this ROM" in caplog.text
    # The European set it was linked to by title: moved aside, not used or sent any more
    assert not (ra_dir / "ADME.json").exists() and (ra_dir / "cache" / "unsupported" / "ADME.json").exists()
    assert "ADME" not in ra_set.codes(str(ra_dir))
    store = rom_hashes.load()
    assert rom_hashes.game_id(store, ADME_USA) == 0 and not rom_hashes.may_send(store, "ADME")
    assert rom_hashes.set_codes(store) == {"CPUE": 11732}
    # Asked once: the next sync answers from what's kept
    assert engine(link).roms([("ADME", ADME_USA, False, "Animal Crossing WW")], 0, 0) == \
        {ADME_USA: rom_hashes.NOT_THIS_ROM}
    assert sorted(link.asked) == sorted([ADME_USA, CPUE])


def test_animal_crossing_kept_from_before(ra_dir):
    """rom_hashes.json from the build that had it wrong: the answer kept
    there is read the new way, without asking again"""
    store = rom_hashes.empty()
    rom_hashes.record(store, [("ADME", ADME_USA, True, "")])
    rom_hashes.remember(store, ADME_USA, 1_000_009_594)
    rom_hashes.save(store)
    link = Link({})
    assert engine(link).roms([("ADME", ADME_USA, True, "Animal Crossing WW")], 0, 0) == \
        {ADME_USA: rom_hashes.NOT_THIS_ROM}
    assert link.asked == [] and not (ra_dir / "ADME.json").exists()


def test_unknown_hash_told_apart_by_title(ra_dir):
    link = Link({ADME_USA: 0, HACK: 0}, titles={"ADME": True, "IPKE": False})
    got = engine(link).roms([("ADME", ADME_USA, False, "Animal Crossing WW"), ("IPKE", HACK, False, "Heart Red")], 0, 0)
    assert got == {ADME_USA: rom_hashes.NOT_THIS_ROM, HACK: rom_hashes.NO_GAME}


HOMEBREW_A = "aaaa0000aaaa0000aaaa0000aaaa0000"
HOMEBREW_B = "bbbb0000bbbb0000bbbb0000bbbb0000"


def test_homebrew_without_a_code(ra_dir, caplog):
    """Files with no game code (homebrew, "####" on the console: four zero
    bytes) go by their hash: two of them stay apart, one RetroAchievements
    doesn't know is "no such game" without a title search, and one it has a
    set for is said to be unusable (the console's sets go by game code)"""
    data = offline.build_request("", {}, b"", version=2, roms=[("", HOMEBREW_A, False, "Homebrew A")])
    read, _ = reader(data)
    assert offline.parse_sync(read(offline.REQUEST.size), read)["roms"] == [("", HOMEBREW_A, False, "Homebrew A")]
    titles = []
    link = Link({HOMEBREW_A: 0, HOMEBREW_B: 4242})
    link.title_has_game = lambda code: titles.append(code) or True
    with caplog.at_level(logging.INFO):
        got = engine(link).roms([("", HOMEBREW_A, False, "Homebrew A"), ("", HOMEBREW_B, False, "Homebrew B")], 2, 100)
    assert got == {HOMEBREW_A: rom_hashes.NO_GAME, HOMEBREW_B: rom_hashes.HAS_SET} and titles == []
    assert "no set for Homebrew A (no game code, hash" in caplog.text
    assert "a set for Homebrew B (no game code" in caplog.text and "can't be given it" in caplog.text
    store = rom_hashes.load()
    assert {e["name"] for e in store["roms"].values()} == {"Homebrew A", "Homebrew B"}
    assert rom_hashes.set_codes(store) == {} and (ra_dir / "ADME.json").exists()     # (nothing else touched)


def test_files_sharing_a_code_stay_apart(ra_dir):
    """A ROM hack keeps its original's code: each file gets its own answer"""
    link = Link({CPUE: 11732, HACK: 0}, titles={"CPUE": True})
    got = engine(link).roms([("CPUE", CPUE, False, "Pokemon Platinum"), ("CPUE", HACK, True, "Renegade Platinum")],
                            0, 0)
    assert got == {CPUE: rom_hashes.HAS_SET, HACK: rom_hashes.NOT_THIS_ROM}
    store = rom_hashes.load()
    assert rom_hashes.may_send(store, "CPUE") and rom_hashes.set_codes(store) == {"CPUE": 11732}


def test_waiting_for_an_answer_sends_nothing(ra_dir):
    """A known hash RetroAchievements hasn't answered (out of reach): nothing
    decided, nothing dropped, and no set meanwhile (not the one linked by
    its title)"""
    link = Link({})
    got = engine(link).roms([("ADME", ADME_USA, False, "Animal Crossing WW"), ("CPUE", CPUE, False, "Platinum")], 0, 0)
    assert got == {ADME_USA: rom_hashes.UNKNOWN, CPUE: rom_hashes.UNKNOWN}
    assert (ra_dir / "ADME.json").exists()
    store = rom_hashes.load()
    assert not rom_hashes.may_send(store, "ADME")
    assert rom_hashes.may_send(store, "AMCE")       # (no hash known: a launcher from before, as before)


def test_every_hash_at_once(ra_dir):
    roms = [("A%03d" % i, f"{i:032x}", i == 69, f"Game {i}") for i in range(70)]
    link = Link({md5: 1000 + i for i, (_, md5, _, _) in enumerate(roms)}, delay=0.05)
    steps = []
    t0 = time.time()
    got = engine(link).roms(roms, 70, 0, lambda d, n, what: steps.append((d, n, what)))
    took = time.time() - t0
    assert set(got.values()) == {rom_hashes.HAS_SET} and len(link.asked) == 70     # no cap
    assert took < 70 * 0.05 / 2                                                   # a few at a time
    assert roms[69][1] in link.asked[:engine_module.HASH_LOOKUP_THREADS]          # the started one first
    assert steps[0] == (0, 70, offline.PROGRESS_CHECKING) and steps[-1] == (70, 70, offline.PROGRESS_CHECKING)


def test_an_outage_ends_cleanly(ra_dir):
    roms = [("A%03d" % i, f"{i:032x}", False, f"Game {i}") for i in range(40)]
    link = Link({}, delay=0.02)
    got = engine(link).roms(roms, 0, 0, lambda *a: None)
    assert got == {r[1]: rom_hashes.UNKNOWN for r in roms}       # all "new" on the console
    assert len(link.asked) < len(roms)                           # the rest not tried this time
    assert rom_hashes.load()["games"] == {}


@pytest.fixture
def made_set(rcheevos):
    return ra_set.RaSet(gen_set.make_set(8, seed=5))


def test_a_set_for_every_game(ra_dir, monkeypatch, made_set):
    """A game on the SD card RetroAchievements has a set for, never started
    and without a set here: fetched and sent at the sync. One it has none
    for isn't, even with a set linked by title in ra/"""
    store = rom_hashes.empty()
    rom_hashes.record(store, [("TEST", CPUE, False, "Test"), ("ADME", ADME_USA, False, "AC")])
    rom_hashes.remember(store, CPUE, made_set.id)
    rom_hashes.remember(store, ADME_USA, 1_000_009_594)
    rom_hashes.save(store)
    monkeypatch.setattr(offline, "remember_set", lambda *a, **k: None)
    real_codes, real_for_game = ra_set.codes, ra_set.for_game      # (their default folder is bound at import)
    monkeypatch.setattr(ra_set, "codes", lambda d=None: real_codes(d or str(ra_dir)))
    monkeypatch.setattr(ra_set, "for_game", lambda code, d=None: real_for_game(code, d or str(ra_dir)))
    fetched = []

    class SetLink:
        def set_for_code(self, code):
            fetched.append(code)
            return made_set if code == "TEST" else None

        def known_unlock_times(self, game_id):
            return {}

    e = types.SimpleNamespace(clear_ra=False, _cleared=False, ra_link=SetLink(), ra_enabled=True, blank_ra=False,
                              unlocks=types.SimpleNamespace(times=lambda ids: {}))
    steps = []
    out = engine_module.Engine._offline_sets(e, None, {}, (), lambda *a: steps.append(a))
    assert [code for code, _ in out] == ["TEST"] and fetched == ["TEST"]
    assert (0, 1, offline.PROGRESS_SETS) in steps and (1, 1, offline.PROGRESS_SETS) in steps


def test_named_by_the_file(ra_dir):
    """A file RetroAchievements has no set for (a ROM hack of Platinum, say)
    goes by its file's name in the log, Discord and the overlay; one with a
    set as before"""
    store = rom_hashes.empty()
    rom_hashes.record(store, [("CPUE", HACK, True, "Pokemon Renegade Platinum"), ("ATRE", CPUE, True, "Tetris DS")])
    rom_hashes.remember(store, HACK, 0, False)
    rom_hashes.remember(store, CPUE, 9878)
    rom_hashes.save(store)
    assert games.name({"code": "CPUE"}) == "Pokemon Renegade Platinum (CPUE)"
    assert platinum_presence._name() == "Pokemon Renegade Platinum"
    assert generic_presence.title({"code": "CPUE"}) == "Pokemon Renegade Platinum"
    assert generic_presence.title({"code": "ATRE"}) == games.NAMES.get("ATRE", "ATRE")
    assert games.file_name("ATRE") is None and games.file_name("AMCE") is None


class Api:
    def __init__(self, answers):
        self.answers, self.username, self.token, self.host, self.titles = answers, "u", "t", "h", 0
        self.signed_in = False

    def game_id_for_hash(self, md5):
        return self.answers[md5]

    def system_games(self, console_id):
        self.titles += 1
        return []


@pytest.mark.parametrize("answer", [0, 1_000_009_594])
def test_link_by_hash_no_title_fallback(ra_dir, answer):
    store = rom_hashes.empty()
    rom_hashes.record(store, [("ADME", ADME_USA, True, "AC")])
    rom_hashes.save(store)
    api = Api({ADME_USA: answer})
    link = ra_link.RALink(api=api, ra_dir=str(ra_dir))
    try:
        game = types.SimpleNamespace(code="ADME", inbox=queue.Queue())
        link._prepare(game, ra_set.for_game("ADME", str(ra_dir)), 0)
        kind, value = game.inbox.get_nowait()
        assert kind == "unsupported" and "this version" in value
        assert game.inbox.empty()                                 # never linked by its title
        assert rom_hashes.game_id(rom_hashes.load(str(ra_dir)), ADME_USA) == 0
        assert link.set_for_code("ADME") is None                  # and none for offline play
    finally:
        link.stop()
