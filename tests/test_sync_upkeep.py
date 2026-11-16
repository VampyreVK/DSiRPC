"""What DSiRPC keeps between syncs, kept honest: RetroAchievements asked
again about a hash it had no set for once that answer is ASK_AGAIN old
(core/rom_hashes.py's due()); the console's shadow notes taken game by game
(one unreadable set file loses only that game's) and left out for
achievements RetroAchievements changed since the console's set was built
(app/engine.py's _shadow_notes(), core/offline.py's remember_set() /
known_set()); and a learned-state file that can't be read says so in the
log."""

import json
import logging
import types

import pytest

import app.engine as engine_module
from core import frame_needs, offline, ra_set, rom_hashes
from test_rom_hashes import CPUE, HACK, Link, engine

DAY = 86400


# -- asking again --------------------------------------------------------------------

def test_due():
    now = 1_800_000_000
    store = rom_hashes.empty()
    rom_hashes.remember(store, "a" * 32, 0, now=now - 31 * DAY)          # no game, a month ago
    rom_hashes.remember(store, "b" * 32, 0, now=now - 2 * DAY)            # no game, lately
    rom_hashes.remember(store, "c" * 32, 1_000_009_594, now=now - 40 * DAY)   # not this ROM, long ago
    rom_hashes.remember(store, "d" * 32, 11732, now=now - 400 * DAY)      # a set: never again
    rom_hashes.remember(store, "e" * 32, 0, now=now)
    del store["games"]["e" * 32]["when"]                                  # (when unknown: old)
    due = {m[0]: rom_hashes.due(store, m, now=now) for m in ("a" * 32, "b" * 32, "c" * 32, "d" * 32, "e" * 32,
                                                             "f" * 32)}
    assert due == {"a": True, "b": False, "c": True, "d": False, "e": True, "f": True}


@pytest.fixture
def ra_dir(tmp_path, monkeypatch):
    d = tmp_path / "ra"
    (d / "cache").mkdir(parents=True)
    monkeypatch.setattr(ra_set, "RA_DIR", str(d))
    return d


def test_asked_again_after_a_month(ra_dir, monkeypatch):
    t = [2_000_000_000.0]
    monkeypatch.setattr(rom_hashes.time, "time", lambda: t[0])
    roms = [("CPUE", HACK, True, "Renegade Platinum"), ("CPUE", CPUE, False, "Pokemon Platinum")]
    link = Link({HACK: 0, CPUE: 11732}, titles={"CPUE": True})
    assert engine(link).roms(roms, 0, 0) == {HACK: rom_hashes.NOT_THIS_ROM, CPUE: rom_hashes.HAS_SET}
    t[0] += 10 * DAY
    engine(link).roms(roms, 0, 0)
    assert sorted(link.asked) == sorted([HACK, CPUE])                 # (not again yet)
    # A month on, RetroAchievements has linked the hack's hash to a set
    t[0] += 21 * DAY
    link.answers[HACK] = 26000
    assert engine(link).roms(roms, 0, 0)[HACK] == rom_hashes.HAS_SET
    assert sorted(link.asked) == sorted([HACK, CPUE, HACK])           # (the one with a set: never again)


def test_out_of_reach_keeps_the_old_answer(ra_dir, monkeypatch):
    t = [2_000_000_000.0]
    monkeypatch.setattr(rom_hashes.time, "time", lambda: t[0])
    roms = [("CPUE", HACK, True, "Renegade Platinum")]
    engine(Link({HACK: 0}, titles={"CPUE": True})).roms(roms, 0, 0)
    t[0] += 40 * DAY
    assert engine(Link({})).roms(roms, 0, 0) == {HACK: rom_hashes.NOT_THIS_ROM}     # (not "new")


# -- the console's shadow notes -----------------------------------------------------------

def set_json(memaddr):
    return {"Success": True, "PatchData": {"ID": 99, "Title": "Test", "ConsoleID": 18, "RichPresencePatch": "",
                                           "Achievements": [{"ID": aid, "Title": f"A{aid}", "Description": "",
                                                             "Points": 1, "Flags": 3, "BadgeName": "0",
                                                             "MemAddr": m} for aid, m in memaddr.items()]}}


@pytest.fixture
def sets(ra_dir, monkeypatch):
    real = ra_set.for_game
    monkeypatch.setattr(ra_set, "for_game", lambda code, d=None: real(code, d or str(ra_dir)))
    return ra_dir


def notes_engine():
    e = types.SimpleNamespace()
    e.notes = types.MethodType(engine_module.Engine._shadow_notes, e)
    return e


def test_one_bad_set_file_loses_only_its_notes(sets, caplog):
    (sets / "AAAA.json").write_text(json.dumps(set_json({1: "0xH0100=1", 2: "0xH0101=1"})))
    (sets / "BBBB.json").write_text("{ not json")
    notes = [{"code": "AAAA", "id": 1, "proven": True}, {"code": "BBBB", "id": 7, "proven": True},
             {"code": "AAAA", "id": 2, "proven": False}]
    with caplog.at_level(logging.INFO):
        notes_engine().notes(notes, {})
    needs = frame_needs.load()
    assert frame_needs.proven(needs, "AAAA", [{"id": 1, "memaddr": "0xH0100=1"}]) == {1}
    assert frame_needs.clean_counts(needs, "AAAA", [{"id": 2, "memaddr": "0xH0101=1"}]) == {2: 1}
    assert "BBBB: 1 shadow note(s) left out" in caplog.text


def test_notes_about_changed_logic_are_left_out(sets, caplog, rcheevos):
    """The console ran a set built when achievement 2 was different: its note
    about 2 is about logic that's gone; 1's still holds"""
    old = {1: "0xH0100=1_d0xH0100=0", 2: "0xH0101=1_d0xH0101=0"}
    s_old = ra_set.RaSet(set_json(old))
    data = offline.build_set(s_old, "AAAA")
    offline.remember_set(data, memaddr=old)
    stamp = offline.set_stamp(data)
    assert offline.known_set(stamp)["mem"][2] == frame_needs.memaddr_hash(old[2])
    new = {**old, 2: "0xH0101=2_d0xH0101=0"}
    (sets / "AAAA.json").write_text(json.dumps(set_json(new)))
    notes = [{"code": "AAAA", "id": 1, "proven": True}, {"code": "AAAA", "id": 2, "proven": True}]
    with caplog.at_level(logging.INFO):
        notes_engine().notes(notes, {"AAAA": stamp})
    needs = frame_needs.load()
    assert frame_needs.proven(needs, "AAAA", [{"id": i, "memaddr": m} for i, m in new.items()]) == {1}
    assert "AAAA: 1 shadow note(s) left out: RetroAchievements changed" in caplog.text
    # A set remembered before the logic was kept (or not known): taken as before
    notes_engine().notes([{"code": "AAAA", "id": 2, "proven": True}], {"AAAA": 0x12345678})
    assert frame_needs.proven(frame_needs.load(), "AAAA", [{"id": 2, "memaddr": new[2]}]) == {2}


# -- unreadable files say so ---------------------------------------------------------------

def test_unreadable_files_are_logged(ra_dir, caplog):
    (ra_dir / "cache" / "frame_needs.json").write_text("{ torn")
    (ra_dir / "cache" / "rom_hashes.json").write_text("[1, 2")
    with caplog.at_level(logging.WARNING):
        assert frame_needs.load() == frame_needs.empty()
        assert rom_hashes.load() == rom_hashes.empty()
    assert "couldn't read" in caplog.text and "frame_needs.json" in caplog.text and "rom_hashes.json" in caplog.text
    caplog.clear()
    (ra_dir / "cache" / "frame_needs.json").unlink()
    (ra_dir / "cache" / "rom_hashes.json").unlink()
    with caplog.at_level(logging.WARNING):
        frame_needs.load()
        rom_hashes.load()
    assert caplog.text == ""            # (not there yet: nothing to say)
