"""core/frame_needs.py: the file of achievements found to need checking every
frame (its format, merging and the MemAddr hash rule), the shadow check
that finds them, and core/offline.py putting them in the frame lane first."""

import json

import pytest

from core import frame_needs, offline, ra_set
from helpers import gen_set


def test_a_proof_counts_for_its_memaddr_only():
    data = frame_needs.empty()
    assert frame_needs.add(data, "TEST", 5, "0xH0010=1", "pc", when=100)
    assert not frame_needs.add(data, "TEST", 5, "0xH0010=1", "console")   # (known: only the source is added)
    assert data["games"]["TEST"][frame_needs.key(5, "0xH0010=1")] == {"when": 100, "by": ["console", "pc"]}
    achs = [{"id": 5, "memaddr": "0xH0010=1"}, {"id": 6, "memaddr": "0xH0011=1"}]
    assert frame_needs.proven(data, "TEST", achs) == {5}
    assert frame_needs.proven(data, "OTHR", achs) == set()
    # RetroAchievements changed achievement 5: the proof no longer counts, and prune() drops it
    changed = [{"id": 5, "memaddr": "0xH0010=2"}]
    assert frame_needs.proven(data, "TEST", changed) == set()
    assert frame_needs.prune(data, "TEST", [{"id": 6, "memaddr": "x"}]) == 0   # (5 isn't in that set: kept)
    assert frame_needs.prune(data, "TEST", changed) == 1
    assert data["games"]["TEST"] == {}


def test_merge_is_a_union():
    a, b = frame_needs.empty(), frame_needs.empty()
    frame_needs.add(a, "TEST", 1, "m1", "pc", when=200)
    frame_needs.add(a, "TEST", 2, "m2", "pc", when=300)
    frame_needs.add(b, "TEST", 2, "m2", "console", when=250)
    frame_needs.add(b, "TEST", 3, "m3", "console", when=400)
    frame_needs.add(b, "OTHR", 9, "m9", "console", when=500)
    assert frame_needs.merge(a, b) == 2
    assert frame_needs.proven(a, "TEST", [{"id": i, "memaddr": f"m{i}"} for i in (1, 2, 3)]) == {1, 2, 3}
    assert a["games"]["TEST"][frame_needs.key(2, "m2")] == {"when": 250, "by": ["console", "pc"]}
    assert frame_needs.proven(a, "OTHR", [{"id": 9, "memaddr": "m9"}]) == {9}
    assert frame_needs.merge(a, b) == 0   # (again: nothing new, nothing lost)
    assert len(a["games"]["TEST"]) == 3


def test_the_file_round_trips_and_survives_damage(tmp_path):
    data = frame_needs.empty()
    frame_needs.add(data, "TEST", 7, "0xH0001=1", "console", when=123)
    frame_needs.save(data, str(tmp_path))
    assert frame_needs.load(str(tmp_path)) == data
    assert not (tmp_path / "cache" / "frame_needs.json.tmp").exists()
    path = tmp_path / "cache" / "frame_needs.json"
    for bad in ("", "{not json", "[]", json.dumps({"games": {"TEST": {"x:y": {}, "8:ABCDEF01": "no"}}})):
        path.write_text(bad)
        assert frame_needs.load(str(tmp_path)) == frame_needs.empty()
    path.write_text(json.dumps({"games": {"TEST": {"8:abcdef01": {"when": 5, "by": ["pc", "elsewhere"]}}}}))
    assert frame_needs.load(str(tmp_path))["games"]["TEST"] == {"8:ABCDEF01": {"when": 5, "by": ["pc"]}}


class FakeRuntime:
    """rcheevos' runtime for the shadow tests: an achievement 'flag A' unlocks
    the first frame memory[A] is 1; 'reset A' has a hit count that a frame
    with memory[A] == 2 resets (an achievement_reset event when it had
    hits)."""

    def __init__(self):
        self.achs, self.done, self.hits = {}, set(), {}

    def activate_achievement(self, aid, memaddr):
        kind, a = memaddr.split()
        self.achs[aid] = (kind, int(a))
        self.hits[aid] = 0

    def deactivate_achievement(self, aid):
        self.achs.pop(aid, None)

    def frame(self, peek):
        out = []
        for aid, (kind, a) in self.achs.items():
            v = peek(a, 1)
            if kind == "flag" and v == 1 and aid not in self.done:
                self.done.add(aid)
                out.append(("achievement_triggered", aid, 0))
            elif kind == "reset":
                if v == 2 and self.hits[aid]:
                    self.hits[aid] = 0
                    out.append(("achievement_reset", aid, 0))
                elif v == 1:
                    self.hits[aid] += 1
        return out

    def close(self):
        pass


def _run(achs, frames, every=8):
    sh = frame_needs.Shadow(achs, every=every, runtime=FakeRuntime)
    for mem in frames:
        sh.frame(lambda a, n, mem=mem: mem.get(a, 0))
    return sh.proofs


def test_the_shadow_finds_what_the_pass_lane_would_miss():
    # A flag that's set for one frame between the sparse checks: proof
    one_frame = [{}] * 13 + [{0x10: 1}] + [{}] * 40
    assert set(_run([(1, "flag 16")], one_frame)) == {1}
    # A value that stays set: both see it, no proof
    held = [{}] * 13 + [{0x20: 1}] * 40
    assert _run([(2, "flag 32")], held) == {}
    # A reset that lasts one frame, with hits counted before it: the sparse side misses it
    flicker = [{0x30: 1}] * 10 + [{0x30: 2}] + [{0x30: 1}] * 40
    assert set(_run([(3, "reset 48")], flicker)) == {3}
    # Several at once: only the one that differs is proven
    mixed = [{**a, **b} for a, b in zip(one_frame, held)]
    assert set(_run([(1, "flag 16"), (2, "flag 32")], mixed)) == {1}


@pytest.fixture(scope="module")
def big_set(rcheevos):
    s = ra_set.RaSet(gen_set.make_set(250, seed=2))
    todo = [(a["id"], a["memaddr"]) for a in s.playable_achievements]
    return s, todo


def test_proven_ones_go_in_the_frame_lane_first(big_set):
    s, todo = big_set
    frame, rest = offline.split_lanes(todo)
    assert rest, "the set should be too big for the frame lane"
    # some that didn't make it: proven, they go first
    picked = [t[0] for t in rest[:3]]
    frame2, rest2 = offline.split_lanes(todo, proven=picked)
    assert set(picked) <= {t[0] for t in frame2}
    # the build carries it through (and the list still has everything)
    info = offline.read_set(offline.build_set(s, "TEST", proven=picked))
    assert set(picked) <= set(info["frame"])
    assert set(info["frame"]) | set(info["pass"]) == {a["id"] for a in s.playable_achievements}
