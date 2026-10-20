"""Offline play's checker (rpcprobe/probe_ach.c with probe_ach_vm.c), built
for the PC with tests/c/ach/ach_host.c, running a real version 4 set from
core/offline.py against rcheevos.

Every frame the simulated game writes memory, then the console samples (the
frame lane) and ticks, then gets a few visits of the swiHalt hook (or none,
the VBlank doing the checking). The frame lane's unlocks must match
rcheevos frame for frame, order included; DSiRPC's pushed unlocks never
trigger and show as earned in the in-game menu's list; a starved idle side
counts its gaps; unlocks saved to RPCUNLK.BIN read back in core/offline.py
as the console wrote them and aren't checked again in the next session.
"""

import ctypes
import datetime
import os
import random
import subprocess

import pytest

from core import offline, ra_set
from helpers import C_DIR, COMMON_INCLUDE, RPCPROBE, cbuild, gen_set, puzzle_game
from helpers.puzzle_game import RAM_SIZE

# What the puzzle game writes (gen_set.py's memory map)
REGIONS = [(0x100, 0x30), (0x200, 4), (0x300, 0x30), (0x310000, 0x40), (0x320000, 0x40)]
FRAMES = 3000
CLOCK = datetime.datetime(2026, 10, 9, 12, 0, 0)   # ach_host.c's hostRtc()


@pytest.fixture(scope="module")
def ach_host(cc, tmp_path_factory):
    out = tmp_path_factory.mktemp("ach")
    exe = str(out / "ach_host")
    here = os.path.join(C_DIR, "ach")
    cbuild.build(exe, [os.path.join(here, "ach_host.c"), os.path.join(RPCPROBE, "probe_ach.c"),
                       os.path.join(RPCPROBE, "probe_ach_vm.c")],
                 flags=["-I", here, "-I", os.path.join(C_DIR, "stubs"), "-I", RPCPROBE, "-I", COMMON_INCLUDE,
                        "-include", os.path.join(here, "prelude.h"),
                        "-DACH_REG_VCOUNT=hostVcount()", "-DACH_RAM=hostRam", "-DACH_RTC_READ(t)=hostRtc(t)"])
    return exe


def _session(exe, lines):
    r = subprocess.run([exe], input="\n".join(lines) + "\n", capture_output=True, text=True,
                       env=cbuild.run_env(), timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-4000:]
    return r.stdout.splitlines()


def _set(tmp_path, seed, n_ach):
    s = ra_set.RaSet(gen_set.make_set(n_ach, seed=seed))
    data = offline.build_set(s, "TEST")
    path = tmp_path / f"RPCSET_{seed}_{n_ach}.BIN"
    path.write_bytes(data)
    return s, data, offline.read_set(data), path


def _frame_line(mode, f, rng):
    """The console's side of frame `f`: how many idle visits, and what's
    going on around them."""
    if mode == "vblank":            # the swiHalt hook never runs: the VBlank checks
        return "frame 0 0"
    if mode == "starve":            # the hook alive, but no visits for 100 frames
        return "frame 1 0" if 1000 <= f < 1100 else f"frame 1 {rng.choice([1, 2])}"
    if mode == "nullwait":          # altReadMethod: no ROM-read callback
        return f"frame 1 {rng.choice([1, 1, 2, 3, 4])} 0 1 1"
    if mode == "unclean":           # every third frame without a write-back
        return f"frame 1 {rng.choice([1, 2, 3])} 0 {0 if f % 3 == 0 else 1}"
    return f"frame 1 {rng.choice([1, 1, 2, 3, 4])} {int(rng.random() < 0.2)}"   # idle, ROM reads now and then


def _play(seed, mode, s, info, set_path, frames=FRAMES, push_at=None, every_frame=(), first=()):
    """The console's commands for `frames` frames of the puzzle game, and
    rcheevos' frame lane unlocks [(frame, {ids})] (the truth). Pushes three
    frame lane achievements rcheevos hasn't unlocked at frame `push_at`."""
    frame_ids = set(info["frame"])
    rng = random.Random(seed * 13 + len(mode))
    ram_buf = (ctypes.c_uint8 * RAM_SIZE)()
    ram = memoryview(ram_buf).cast("B")
    game = puzzle_game.Game(ram, seed)
    truth = puzzle_game.rc_runtime([(a["id"], a["memaddr"]) for a in s.achievements if a["id"] in frame_ids])
    peek = puzzle_game.peek_from(ram)
    lines = list(first) + [f"set {set_path}"]
    prev = {a: bytes(ram[a:a + n]) for a, n in REGIONS}
    expected, pushed = [], set()
    for f in range(frames):
        game.step()
        for a, n in REGIONS:
            now = bytes(ram[a:a + n])
            if now != prev[a]:
                lines.append(f"w {a:x} {now.hex()}")
                prev[a] = now
        if f == push_at:
            done = {aid for _, ids in expected for aid in ids}
            for aid in sorted(frame_ids - done)[:3]:
                lines.append(f"push {aid} {5000 + aid % 100}")
                pushed.add(aid)
                truth.deactivate_achievement(aid)
        got = {aid for name, aid, _ in truth.frame(peek) if name == "achievement_triggered"}
        if got:
            expected.append((f, got))
        lines.append(_frame_line(mode, f, rng))
        lines.extend(every_frame)
        if f % 500 == 499:
            lines.append("stats")
    lines += ["frame 1 4"] * 20 + ["stats", "list"]
    return lines, expected, pushed


def _stats(out):
    rows = []
    for line in out:
        if line.startswith("stats "):
            rows.append({k: v for k, v in (kv.split("=") for kv in line.split()[1:])})
    return rows


@pytest.mark.parametrize("mode", ["idle", "vblank", "starve", "nullwait", "unclean"])
@pytest.mark.parametrize("seed,n_ach", [(1, 60), (2, 300), (3, 120)])
def test_checker_matches_rcheevos(ach_host, rcheevos, tmp_path, seed, n_ach, mode):
    s, data, info, path = _set(tmp_path, seed, n_ach)
    frame_ids = set(info["frame"])
    lines, expected, pushed = _play(seed, mode, s, info, path, push_at=FRAMES // 2)
    out = _session(ach_host, lines)
    console = [int(line.split()[1]) for line in out if line.startswith("T ")]
    marked = {int(line.split()[1]): line for line in out if line.startswith("L ")}
    stats = _stats(out)
    assert stats[-1]["loaded"] == str(len(info["frame"]) + len(info["pass"])), stats[-1]
    assert stats[-1]["frame"] == str(len(info["frame"])) and stats[-1]["stamp"] == "%08X" % info["stamp"]

    # DSiRPC's unlocks: never unlocked on the console, earned in the menu's list
    assert pushed
    for aid in pushed:
        assert aid not in console
        assert "flags=1" in marked.get(aid, "") or "flags=5" in marked.get(aid, ""), (aid, marked.get(aid))
    # The console's own unlocks are marked earned on the console
    for aid in console:
        assert int(marked[aid].split("flags=")[1].split()[0]) & 2, marked[aid]
    # Every unlock is one of the set's, once
    assert len(console) == len(set(console)) and set(console) <= {a["id"] for a in s.achievements}

    frame_console = [aid for aid in console if aid in frame_ids]
    dropped = sum(int(r["dropped"]) for r in stats)
    if mode == "starve":
        assert dropped > 0, "100 frames without the idle side must leave gaps"
        return
    assert dropped == 0, stats
    # The frame lane unlocks exactly what rcheevos does, in order
    k = 0
    for f, ids in expected:
        chunk = set(frame_console[k:k + len(ids)])
        assert chunk == ids, (mode, f, chunk, ids, frame_console[k:k + 6])
        k += len(ids)
    assert k == len(frame_console), (mode, "extra", frame_console[k:])
    assert expected, "the game should unlock some of the frame lane"
    if mode == "unclean":   # (sampling starts once the set's CRC is checked, a frame or two in)
        assert FRAMES // 3 - 5 <= sum(int(r["unclean"]) for r in stats) <= FRAMES // 3
    else:
        assert sum(int(r["unclean"]) for r in stats) == 0
    if mode == "vblank":
        assert all(r["idle"] == "0" for r in stats[:-1])   # (the last: the idle tail)
    elif info["pass"]:
        assert sum(int(r["passes"]) for r in stats) > 0, "the pass lane should have run"


def test_saved_unlocks_read_back_and_stay_unlocked(ach_host, rcheevos, tmp_path):
    s, data, info, path = _set(tmp_path, 4, 150)
    dump = tmp_path / "RPCUNLK.BIN"
    lines, expected, _ = _play(4, "idle", s, info, path, every_frame=["save"])
    out = _session(ach_host, lines + ["save", f"dump {dump}"])
    console = [int(line.split()[1]) for line in out if line.startswith("T ")]
    assert len(console) > 5
    assert out[-1].startswith("saved 0 total %d failed 0 lost 0" % len(console)), out[-1]

    # DSiRPC reads them as the console wrote them
    base = CLOCK.timestamp()
    unlocks = offline.read_unlocks(dump.read_bytes(), now=base + 86400)
    assert [u["id"] for u in sorted(unlocks, key=lambda u: u["seq"])] == console
    assert [u["seq"] for u in sorted(unlocks, key=lambda u: u["seq"])] == list(range(1, len(console) + 1))
    assert {u["code"] for u in unlocks} == {"TEST"}
    assert all(base <= u["when"] <= base + FRAMES / 59 + 2 for u in unlocks), [u["when"] - base for u in unlocks]
    assert offline.count_unlocks(dump.read_bytes()) == len(console)

    # The next session: those are waiting in RPCUNLK.BIN, so never checked again
    lines, _, _ = _play(4, "idle", s, info, path, first=[f"unlockfile {dump}"])
    out = _session(ach_host, lines)
    assert out[0].startswith("loaded ") and out[0].endswith(f"waiting {len(console)}"), out[0]
    again = [int(line.split()[1]) for line in out if line.startswith("T ")]
    assert not set(again) & set(console)


def test_bad_sets_are_refused(ach_host, rcheevos, tmp_path):
    _, data, _, path = _set(tmp_path, 5, 40)
    frames = ["frame 1 2"] * 30 + ["stats"]

    def load(blob, code=""):
        p = tmp_path / "bad.BIN"
        p.write_bytes(blob)
        out = _session(ach_host, [f"set {p} {code}".strip()] + frames)
        assert not [line for line in out if line.startswith("T ")]
        return int(_stats(out)[-1]["loaded"])

    assert load(data) > 0
    assert load(data, "ABCD") == -2                                  # another game's set
    damaged = bytearray(data)
    damaged[len(damaged) // 2] ^= 0x40
    assert load(bytes(damaged)) == -5                                # its CRC doesn't match
    assert load(b"XXXX" + data[4:]) == -1                            # not a set
    assert load(data[:offline.SET_HEADER.size]) in (-3, -4, -5)      # cut short
    assert load(b"") == 0                                            # no RPCSET.BIN: nothing to check
