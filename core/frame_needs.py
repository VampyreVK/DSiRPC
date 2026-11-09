"""
frame_needs.py - which achievements are known to need checking every frame,
learned while playing, kept in ra/cache/frame_needs.json.

offline.timing() guesses from an achievement's MemAddr which ones need the
console's frame lane (hit counts, ResetIf, deltas...), but it can't tell a
flag that's set for one frame from a value that stays put, so its guess is
only a default. This file is the proof: an achievement goes in when a
shadow check (Shadow below, on the PC; or the console's, through the
launcher's sync) saw it come out differently when checked every frame and
when checked every few frames, as the pass lane does: one unlocked and the
other didn't, or one saw a reset the other missed. core/offline.py's
split_lanes() puts the proven ones in the frame lane first.

The file (JSON, version 1):

    {"version": 1,
     "games": {"CPUE": {"<achievement id>:<MemAddr hash>": {"when": <Unix time>,
                                                          "by": ["pc", "console"]}}},
     "clean": {"CPUE": {"<achievement id>:<MemAddr hash>": <sessions>}}}

"clean" counts the sessions the console's shadow check watched an
achievement a while (its memory changing) and saw no difference. That's
never final: it only lowers the achievement's place in the frame lane's
order (core/offline.py's CLEAN_SESSIONS), and a proof always wins.

The hash is the CRC-32 of the achievement's MemAddr (8 hex digits), so a
proof only counts for the logic it was made on: when RetroAchievements
changes an achievement, the old entry no longer matches (and prune() drops
it). It's DSiRPC's own knowledge, apart from the set files (ra/*.json), so
downloading a set again never touches it. Proofs only ever get added, from
any device or source (merge() is a union); nothing takes one away but a
changed MemAddr.
"""

import json
import os
import time
import zlib

VERSION = 1
SOURCES = ("pc", "console")


def memaddr_hash(memaddr):
    return f"{zlib.crc32((memaddr or '').encode('utf-8')) & 0xFFFFFFFF:08X}"


def key(aid, memaddr):
    return f"{int(aid)}:{memaddr_hash(memaddr)}"


def path(ra_dir=None):
    if ra_dir is None:
        from . import ra_set
        ra_dir = ra_set.RA_DIR
    return os.path.join(ra_dir, "cache", "frame_needs.json")


def empty():
    return {"version": VERSION, "games": {}, "clean": {}}


def _clean(data):
    """A loaded file as a well-formed one (anything unexpected left out)."""
    out = empty()
    games = data.get("games") if isinstance(data, dict) else None
    if not isinstance(games, dict):
        return out
    for code, entries in games.items():
        if not isinstance(code, str) or not isinstance(entries, dict):
            continue
        for k, v in entries.items():
            aid, _, h = str(k).partition(":")
            if not aid.isdigit() or len(h) != 8 or not isinstance(v, dict):
                continue
            by = [s for s in v.get("by", []) if s in SOURCES] or ["pc"]
            when = v.get("when") if isinstance(v.get("when"), (int, float)) else 0
            out["games"].setdefault(code, {})[f"{int(aid)}:{h.upper()}"] = {"when": int(when), "by": sorted(set(by))}
    clean = data.get("clean")
    for code, entries in (clean.items() if isinstance(clean, dict) else ()):
        if not isinstance(code, str) or not isinstance(entries, dict):
            continue
        for k, v in entries.items():
            aid, _, h = str(k).partition(":")
            if aid.isdigit() and len(h) == 8 and isinstance(v, int) and v > 0:
                out["clean"].setdefault(code, {})[f"{int(aid)}:{h.upper()}"] = v
    return out


def load(ra_dir=None):
    try:
        with open(path(ra_dir), encoding="utf-8") as f:
            return _clean(json.load(f))
    except (OSError, ValueError):
        return empty()


def save(data, ra_dir=None):
    """Writes the file whole (a temporary file, then renamed over it, so a
    crash never leaves half of one)."""
    p = path(ra_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def add(data, code, aid, memaddr, source="pc", when=None):
    """Notes a proof. Returns True if it's new (for this MemAddr)."""
    entries = data["games"].setdefault(code, {})
    k = key(aid, memaddr)
    e = entries.get(k)
    if e is None:
        entries[k] = {"when": int(when if when is not None else time.time()), "by": [source]}
        return True
    if source not in e["by"]:
        e["by"] = sorted(set(e["by"]) | {source})
    return False


def add_clean(data, code, aid, memaddr):
    """Notes a session the console's shadow check found no difference for
    an achievement. Returns its count now."""
    entries = data.setdefault("clean", {}).setdefault(code, {})
    k = key(aid, memaddr)
    entries[k] = entries.get(k, 0) + 1
    return entries[k]


def clean_counts(data, code, achievements):
    """{id: sessions} of achievements [{'id', 'memaddr'}] found clean (on
    their MemAddr as it is now)."""
    entries = data.get("clean", {}).get(code, {})
    out = {}
    for a in achievements:
        n = entries.get(key(a["id"], a.get("memaddr")))
        if n:
            out[a["id"]] = n
    return out


def merge(data, other):
    """Adds every proof in other to data (a union: the earliest time, every
    source), and its clean counts (the larger of the two: the same sessions
    may have reached both). Returns how many proofs were new."""
    new = 0
    other = _clean(other)
    for code, entries in other["clean"].items():
        mine = data.setdefault("clean", {}).setdefault(code, {})
        for k, v in entries.items():
            mine[k] = max(mine.get(k, 0), v)
    for code, entries in other["games"].items():
        mine = data["games"].setdefault(code, {})
        for k, v in entries.items():
            if k not in mine:
                mine[k] = dict(v)
                new += 1
            else:
                mine[k] = {"when": min(mine[k]["when"], v["when"]) or max(mine[k]["when"], v["when"]),
                           "by": sorted(set(mine[k]["by"]) | set(v["by"]))}
    return new


def proven(data, code, achievements):
    """The ids, of achievements [{'id', 'memaddr'}] (a set's), with a proof
    made on their MemAddr as it is now."""
    entries = data["games"].get(code, {})
    return {a["id"] for a in achievements if key(a["id"], a.get("memaddr")) in entries}


def prune(data, code, achievements):
    """Drops this game's proofs for achievements whose MemAddr has changed
    since (the set has the achievement, with another hash). Proofs for
    achievements the set doesn't have are kept: another version of the
    game's set may. Returns how many went."""
    now = {str(a["id"]): memaddr_hash(a.get("memaddr")) for a in achievements}
    gone = 0
    for entries in (data["games"].get(code), data.get("clean", {}).get(code)):
        if not entries:
            continue
        old = [k for k in entries if k.split(":")[0] in now and k.split(":")[1] != now[k.split(":")[0]]]
        for k in old:
            del entries[k]
        gone += len(old)
    return gone


class Shadow:
    """Checks achievements twice: every frame, and every `every` frames (the
    pass lane's way), from the same frames of memory, and notes the ones
    that come out differently: one unlocked and the other hadn't within a
    window of a few of the sparse checks, or one saw a reset (rcheevos'
    achievement_reset: a ResetIf cleared its hits) the other didn't in that
    window. Either is proof the achievement needs checking every frame.

        sh = Shadow([(id, memaddr), ...], every=8)
        sh.frame(peek)       # each frame
        sh.proofs            # {id: reason}
    """

    def __init__(self, achievements, every=8, window=3, runtime=None):
        if runtime is None:
            from .rcheevos import Runtime as runtime
        self.every = max(2, int(every))
        self.span = self.every * max(1, int(window))  # frames
        self.proofs = {}
        self.dense, self.sparse = runtime(), runtime()
        self.ids, self.memaddr = [], {}
        for aid, memaddr in achievements:
            try:
                self.dense.activate_achievement(aid, memaddr)
                self.sparse.activate_achievement(aid, memaddr)
            except Exception:
                for rt in (self.dense, self.sparse):
                    try:
                        rt.deactivate_achievement(aid)
                    except Exception:
                        pass
                continue
            self.ids.append(aid)
            self.memaddr[aid] = memaddr
        self.n = 0
        self.pending = {aid: {"dense": [], "sparse": []} for aid in self.ids}  # unmatched [(frame, name)]

    def close(self):
        for rt in (self.dense, self.sparse):
            rt.close()

    def frame(self, peek):
        f = self.n
        self.n += 1
        self._note("dense", f, self.dense.frame(peek))
        if f % self.every == 0:
            self._note("sparse", f, self.sparse.frame(peek))
        for aid in list(self.pending):
            for side, waiting in self.pending[aid].items():
                if waiting and f - waiting[0][0] > self.span:
                    at, name = waiting[0]
                    self._proof(aid, f"{'missed' if side == 'dense' else 'extra'} "
                                     f"{'unlock' if name == 'achievement_triggered' else 'reset'} (frame {at})")
                    break

    def _note(self, side, f, events):
        """An unlock or a reset on one side: it cancels one of its kind the
        other side had within `span` frames, or waits for one."""
        other = "sparse" if side == "dense" else "dense"
        for name, aid, _ in events:
            if aid not in self.pending or name not in ("achievement_triggered", "achievement_reset"):
                continue
            theirs = self.pending[aid][other]
            for i, (at, n) in enumerate(theirs):
                if n == name and f - at <= self.span:
                    del theirs[i]
                    break
            else:
                self.pending[aid][side].append((f, name))

    def _proof(self, aid, why):
        self.proofs[aid] = why
        del self.pending[aid]
        for rt in (self.dense, self.sparse):
            rt.deactivate_achievement(aid)
