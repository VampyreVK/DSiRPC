"""The console's checker (rpcprobe/probe_ach_vm.c, built for the PC as a
library and driven with ctypes through tests/c/vm/vm_shim.c) against
rcheevos, frame by frame, on the simulated puzzle game.

Every frame:
  - the checker with change-driven skipping triggers exactly what rcheevos does
  - the checker without skipping (a second build) agrees on every state
  - the frame lane path (sample now, check later through a ring with a
    random lag) triggers the same
  - a pass that stops every few time checks (a budget) triggers the same

UBSan is always on; ASan too when this Python already has its runtime
(CI's ASan step preloads it; tests/README.md has the command).
"""

import ctypes
import os
import random

import pytest

from helpers import C_DIR, RPCPROBE, cbuild, gen_set, puzzle_game
from helpers.puzzle_game import RAM_SIZE

SKIP_LINE = "if ((st & SETTLED) && unchanged(vm, a)) return 1;"
FRAMES = 2500


def _no_skip(src):
    return src.replace(SKIP_LINE, "")


class Vm:
    def __init__(self, lib, k, program, ram):
        self.lib, self.k = lib, k
        self.prog = ctypes.create_string_buffer(program, len(program))
        r = lib.shim_load(k, self.prog, len(program), ram, RAM_SIZE)
        assert r == 0, f"AchVm_Load: {r}"
        self.n = lib.shim_count(k)
        self.out = (ctypes.c_uint32 * 4096)()

    def pass_(self, stop_every=0):
        n = self.lib.shim_pass(self.k, stop_every, self.out)
        return sorted(self.out[:n])

    def sample(self, buf):
        return self.lib.shim_sample(self.k, buf)

    def run_sampled(self, buf):
        n = self.lib.shim_run_sampled(self.k, buf, self.out)
        return sorted(self.out[:n])

    def states(self):
        return [self.lib.shim_state(self.k, i) & 0x83 for i in range(self.n)]

    def unlock(self, aid):
        return self.lib.shim_unlock(self.k, aid)


def _build(out, name, patch=None):
    src = open(os.path.join(RPCPROBE, "probe_ach_vm.c")).read()
    if patch:
        patched = patch(src)
        assert patched != src, "the patch no longer applies to probe_ach_vm.c"
        src = patched
    c = out / f"probe_ach_vm_{name}.c"
    c.write_text(src)
    path = str(out / f"libvm_{name}.so")
    cbuild.build(path, [str(c), os.path.join(C_DIR, "vm", "vm_shim.c")], flags=["-I", RPCPROBE],
                 shared=True, sanitize=cbuild.shared_sanitizers())
    lib = ctypes.CDLL(path)
    lib.shim_load.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    lib.shim_pass.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p]
    lib.shim_sample.argtypes = [ctypes.c_int, ctypes.c_void_p]
    lib.shim_run_sampled.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    lib.shim_unlock.argtypes = [ctypes.c_int, ctypes.c_uint32]
    lib.shim_id.restype = ctypes.c_uint32
    return lib


@pytest.fixture(scope="module")
def libs(cc, rcheevos, tmp_path_factory):
    out = tmp_path_factory.mktemp("vm")
    return _build(out, "skip"), _build(out, "full", _no_skip)


def _compile(rcheevos, d):
    achs = [(a["ID"], a["MemAddr"]) for a in d["PatchData"]["Achievements"]]
    program, left = rcheevos.compile_offline(achs)
    return program, [x for x in achs if x[0] not in left], left


@pytest.mark.parametrize("kind,seed", [("set", 1), ("set", 2), ("set", 3), ("set", 4),
                                       ("fuzz", 1), ("fuzz", 2), ("fuzz", 3)])
def test_checker_matches_rcheevos(libs, rcheevos, kind, seed):
    lib_skip, lib_full = libs
    d = (gen_set.fuzz_set if kind == "fuzz" else gen_set.make_set)(200, seed=seed)
    program, achs, left = _compile(rcheevos, d)
    assert kind == "fuzz" or not left, f"rcheevos left out {left}"
    ram_buf = (ctypes.c_uint8 * RAM_SIZE)()
    ram = memoryview(ram_buf).cast("B")
    game = puzzle_game.Game(ram, seed)
    truth = puzzle_game.rc_runtime(achs)
    peek = puzzle_game.peek_from(ram)

    skip = Vm(lib_skip, 0, program, ram_buf)
    full = Vm(lib_full, 0, program, ram_buf)
    lane_sample = Vm(lib_skip, 1, program, ram_buf)
    lane_check = Vm(lib_skip, 2, program, ram_buf)
    budget = Vm(lib_skip, 3, program, ram_buf)
    rng = random.Random(seed * 7 + 1)
    pending = []
    triggers = 0
    for f in range(FRAMES):
        game.step()
        want = sorted(aid for name, aid, _ in truth.frame(peek) if name == "achievement_triggered")
        assert full.pass_() == want, f"frame {f}: no skipping"
        assert skip.pass_() == want, f"frame {f}: skipping"
        assert budget.pass_(stop_every=rng.choice([1, 2, 3, 5, 9, 40])) == want, f"frame {f}: budget"
        st_s, st_f = skip.states(), full.states()
        assert st_s == st_f, (f, [(i, a, b) for i, (a, b) in enumerate(zip(st_s, st_f)) if a != b][:5])
        triggers += len(want)
        buf = (ctypes.c_uint32 * 8192)()
        lane_sample.sample(buf)
        pending.append((f, buf, want))
        while pending and (len(pending) >= 8 or rng.random() < 0.6):
            ff, b, w = pending.pop(0)
            assert lane_check.run_sampled(b) == w, f"frame {ff}: frame lane"
    while pending:
        ff, b, w = pending.pop(0)
        assert lane_check.run_sampled(b) == w, f"frame {ff}: frame lane"
    if kind == "set":
        assert triggers > 50, "the game should unlock plenty in this many frames"


def test_unlocked_never_triggers(libs, rcheevos):
    """DSiRPC's unlocks (AchVm_SetUnlocked) are never checked again; the rest
    carry on as rcheevos says."""
    lib_skip, _ = libs
    program, achs, _ = _compile(rcheevos, gen_set.make_set(120, seed=9))
    ram_buf = (ctypes.c_uint8 * RAM_SIZE)()
    ram = memoryview(ram_buf).cast("B")
    game = puzzle_game.Game(ram, 9)
    truth = puzzle_game.rc_runtime(achs)
    peek = puzzle_game.peek_from(ram)
    vm = Vm(lib_skip, 0, program, ram_buf)
    done, unlocked = set(), set()
    for f in range(2000):
        if f == 300:
            for aid in sorted({a for a, _ in achs} - done)[:10]:
                assert vm.unlock(aid) == 1
                truth.deactivate_achievement(aid)
                unlocked.add(aid)
        game.step()
        want = sorted(aid for name, aid, _ in truth.frame(peek) if name == "achievement_triggered")
        got = vm.pass_()
        assert got == want, f"frame {f}"
        done.update(got)
    assert unlocked and not (done & unlocked)
    assert vm.unlock(123456789) == 0, "an ID the set doesn't have"


def test_truncated_program_is_refused(libs, rcheevos):
    """A program cut short (a short read from the SD card) is refused, or
    loads and runs without reading past its end (the sanitizers watch)."""
    lib_skip, _ = libs
    program, _, _ = _compile(rcheevos, gen_set.make_set(40, seed=5))
    ram_buf = (ctypes.c_uint8 * RAM_SIZE)()
    out = (ctypes.c_uint32 * 4096)()
    for n in list(range(0, 64)) + list(range(64, len(program), 7)):
        cut = ctypes.create_string_buffer(program[:n], max(n, 1))
        if lib_skip.shim_load(0, cut, n, ram_buf, RAM_SIZE) == 0:
            lib_skip.shim_pass(0, 0, out)
    assert lib_skip.shim_load(0, ctypes.create_string_buffer(program, len(program)), len(program),
                              ram_buf, RAM_SIZE) == 0
