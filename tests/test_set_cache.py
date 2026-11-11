"""Offline sets built once: core/offline.py's build_set() keeps what it built
in ra/cache/built/ by a digest of everything the set depends on, so a sync
compares stamps without building anything when nothing changed (Pokemon
HeartGold's set took about 30 s at every sync); and the fit to the console's
memory found by halving (_fit_fast()) instead of one step at a time
(_fit_slow(), kept as the reference), the same set byte for byte."""

import os
import types

import pytest

import app.engine as engine_module
from core import offline, ra_set
from helpers import REPO, gen_set

REAL_RA = os.path.join(REPO, "ra")


@pytest.fixture
def made(rcheevos):
    return ra_set.RaSet(gen_set.make_set(200, seed=7))


def counting(monkeypatch):
    from core import rcheevos
    n = [0]
    real = rcheevos.compile_offline

    def counted(*a, **k):
        n[0] += 1
        return real(*a, **k)
    monkeypatch.setattr(rcheevos, "compile_offline", counted)
    return n


# -- the fit ---------------------------------------------------------------------------

def test_fast_fit_is_the_slow_fit(made, monkeypatch):
    """Every way a set can be too big (no room for the shadow copy, frame
    lane achievements moved, achievements left out), at memory sizes all
    the way down: the same bytes both ways"""
    full = len(offline.build_set(made, "TEST"))
    need = 64                                       # (no room for anything)
    seen = set()
    for memory in [offline.ACH_MEMORY] + [int(full * f) for f in (2.0, 1.4, 1.2, 1.1, 1.0, 0.9, 0.7, 0.5, 0.2)] + [need]:
        monkeypatch.setattr(offline, "ACH_MEMORY", memory)
        slow = offline.build_set(made, "TEST", fit=offline._fit_slow)
        fast = offline.build_set(made, "TEST")
        assert fast == slow, memory
        d = offline.read_set(fast)
        n_frame = len(d["frame"])
        seen.add("all" if n_frame and not d["pass"] or n_frame == 190 else "some moved" if n_frame else
                 "all moved" if len(d["pass"]) == 200 else "left out")
    assert {"all", "some moved", "left out"} <= seen      # (the cases above went through each step)


@pytest.mark.skipif(not os.path.exists(os.path.join(REAL_RA, "IPKE.json")), reason="HeartGold's set isn't in ra/")
def test_real_sets(rcheevos):
    """The sets in ra/ on this PC (HeartGold's among them): the same bytes"""
    for code in sorted(ra_set.codes(REAL_RA)):
        s = ra_set.for_game(code, REAL_RA)
        assert offline.build_set(s, code) == offline.build_set(s, code, fit=offline._fit_slow), code


# -- the cache ---------------------------------------------------------------------------

def test_built_once(made, tmp_path, monkeypatch):
    built = str(tmp_path / "built")
    first = offline.build_set(made, "TEST", cache_dir=built)
    n = counting(monkeypatch)
    assert offline.build_set(made, "TEST", cache_dir=built) == first and n[0] == 0    # (after a restart too: on disk)
    assert len(os.listdir(built)) == 1


@pytest.mark.parametrize("change", ["set", "skipped", "earned", "proven", "clean", "builder"])
def test_built_again_when_something_changed(made, tmp_path, monkeypatch, change):
    built = str(tmp_path / "built")
    ids = [a["id"] for a in made.playable_achievements]
    args = dict(skip_ids=(), earned={}, proven=(), clean={})
    offline.build_set(made, "TEST", cache_dir=built, **args)
    s = made
    if change == "set":         # (a new download: RetroAchievements changed an achievement)
        s = ra_set.RaSet(gen_set.make_set(200, seed=7))
        s.achievements[0]["title"] = "Renamed"
    elif change == "skipped":
        args["skip_ids"] = {ids[0]}
    elif change == "earned":
        args["earned"] = {ids[0]: 1700000000}
    elif change == "proven":    # (what frame_needs learned, or --clear-learning forgetting it)
        args["proven"] = {ids[1]}
    elif change == "clean":
        args["clean"] = {ids[2]: 3}
    else:
        monkeypatch.setattr(offline, "_build_key", lambda *a: "another-builder")
    n = counting(monkeypatch)
    offline.build_set(s, "TEST", cache_dir=built, **args)
    assert n[0] > 0
    assert len(os.listdir(built)) == 2      # (the newest kept, BUILT_KEEP of them)


def test_a_damaged_one_is_built_again(made, tmp_path):
    built = str(tmp_path / "built")
    first = offline.build_set(made, "TEST", cache_dir=built)
    [name] = os.listdir(built)
    with open(os.path.join(built, name), "r+b") as f:
        f.seek(100)
        f.write(b"\xff\xff\xff\xff")
    assert offline.build_set(made, "TEST", cache_dir=built) == first


def test_ticks_while_building(made, monkeypatch):
    monkeypatch.setattr(offline, "ACH_MEMORY", 20000)       # (so the fit has steps)
    ticks = []
    offline.build_set(made, "TEST", tick=lambda: ticks.append(1))
    assert len(ticks) >= 3


# -- the sync -------------------------------------------------------------------------

@pytest.fixture
def ra_dir(tmp_path, monkeypatch, made):
    d = tmp_path / "ra"
    (d / "cache").mkdir(parents=True)
    monkeypatch.setattr(ra_set, "RA_DIR", str(d))
    monkeypatch.setattr(offline, "remember_set", lambda *a, **k: None)
    monkeypatch.setattr(ra_set, "codes", lambda *a: ["TEST"])
    monkeypatch.setattr(ra_set, "for_game", lambda code, *a: made if code == "TEST" else None)
    from core import frame_needs, rom_hashes
    monkeypatch.setattr(rom_hashes, "load", lambda *a: rom_hashes.empty())
    monkeypatch.setattr(frame_needs, "path", lambda *a: str(d / "cache" / "frame_needs.json"))
    return d


def engine():
    return types.SimpleNamespace(clear_ra=False, _cleared=False, ra_link=None, ra_enabled=False, blank_ra=False,
                                 unlocks=types.SimpleNamespace(times=lambda ids: {}))


def test_the_sync_builds_nothing_when_nothing_changed(ra_dir, monkeypatch):
    e = engine()
    [(code, data)] = engine_module.Engine._offline_sets(e, None, {})
    assert code == "TEST" and os.listdir(ra_dir / "cache" / "built")
    n = counting(monkeypatch)
    stamps = {"TEST": offline.set_stamp(data)}
    assert engine_module.Engine._offline_sets(engine(), None, stamps) == [] and n[0] == 0


def test_a_long_build_keeps_the_launcher_waiting(ra_dir, monkeypatch):
    monkeypatch.setattr(engine_module, "BUILD_TICK", 0.0)
    monkeypatch.setattr(offline, "ACH_MEMORY", 20000)
    said = []
    engine_module.Engine._offline_sets(engine(), None, {}, (), lambda *a: said.append(a))
    assert len(said) > 2 and all(a[2] == offline.PROGRESS_SETS for a in said)
