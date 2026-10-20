"""The idle-time write-back: rpcprobe's OS_Halt search, asking, freshness and
capture ring (rpcprobe/probe_watch.c) with the ARM9 half's patching
(cardenginei/arm9/source/dsirpc_watch.c), built for the PC with
tests/c/watch/watch_test.c and run one case per process."""

import os
import subprocess

import pytest

from helpers import ARM9_SOURCE, C_DIR, COMMON_INCLUDE, RPCPROBE, cbuild

CASES = ["search", "bad-header", "patch", "guard", "fresh", "no-arm9", "capture", "fetch", "reset", "doorbell"]


@pytest.fixture(scope="module")
def watch_test(cc, tmp_path_factory):
    out = tmp_path_factory.mktemp("watch")
    arm9 = open(os.path.join(ARM9_SOURCE, "dsirpc_watch.c")).read()
    arm9 = cbuild.strip_asm(arm9, "dsirpcIdle:", "void dsirpcIdle(void) {} // (the ARM routine: a stand-in)\n")
    arm9_host = out / "dsirpc_watch_host.c"
    arm9_host.write_text(arm9)
    exe = str(out / "watch_test")
    cbuild.build(exe, [os.path.join(C_DIR, "watch", "watch_test.c"), str(arm9_host),
                       os.path.join(RPCPROBE, "probe_watch.c")],
                 flags=["-no-pie", "-Wno-int-to-pointer-cast", "-Wno-pointer-to-int-cast",
                        "-I", os.path.join(C_DIR, "stubs"), "-I", COMMON_INCLUDE, "-I", RPCPROBE,
                        "-DPW_ARM9_SCAN_START=fakeScanStart",
                        "-DPW_REG_VCOUNT=(*vcountReg())", "-DPW_REG_IPC_SYNC=fakeIpc", "-DPW_RING=fakeRing",
                        "-include", os.path.join(C_DIR, "watch", "watch_decls.h")])
    return exe


def test_every_case_is_run(watch_test):
    r = subprocess.run([watch_test, "--list"], capture_output=True, text=True, env=cbuild.run_env())
    assert r.stdout.split() == CASES


@pytest.mark.parametrize("case", CASES)
def test_watch(watch_test, case):
    r = subprocess.run([watch_test, case], capture_output=True, text=True, env=cbuild.run_env(), timeout=120)
    assert r.returncode == 0 and r.stdout.rstrip().endswith("ok"), r.stdout + r.stderr
