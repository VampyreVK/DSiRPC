"""Builds the C test harnesses (tests/c/) and the console code they test
with the PC's gcc, with the sanitizers on, so a bad read or write in
rpcprobe's code fails the test instead of passing by luck."""

import os
import shutil
import subprocess

# What a run of a harness needs: leaks don't matter in a test that exits,
# undefined behaviour does
RUN_ENV = {"ASAN_OPTIONS": "detect_leaks=0:abort_on_error=0",
           "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1"}


def gcc():
    """The compiler, or None."""
    return shutil.which("gcc")


def asan_loaded():
    """True when this Python already has AddressSanitizer's runtime (started
    with LD_PRELOAD, as CI's ASan step does), so a library built with it can
    be loaded here with ctypes."""
    try:
        with open("/proc/self/maps") as f:
            return "libasan" in f.read()
    except OSError:
        return False


def shared_sanitizers():
    """Sanitizers for a library this Python loads: ASan only when its runtime
    is already here, UBSan always."""
    return ("address", "undefined") if asan_loaded() else ("undefined",)


def _env():
    # The compiler itself mustn't run under a preloaded ASan runtime
    env = dict(os.environ)
    env.pop("LD_PRELOAD", None)
    return env


def run_env():
    """The environment to run a harness in."""
    env = _env()
    env.update(RUN_ENV)
    return env


def build(out, sources, flags=(), shared=False, sanitize=("address", "undefined")):
    """Compiles `sources` into `out` (an executable, or a shared library with
    shared=True). Fails the test with gcc's messages if it doesn't build."""
    cmd = [gcc(), "-O1", "-g", "-fno-omit-frame-pointer", "-Wall"]
    if sanitize:
        cmd += ["-fsanitize=" + ",".join(sanitize), "-fno-sanitize-recover=undefined"]
    if shared:
        cmd += ["-shared", "-fPIC"]
    cmd += list(flags) + ["-o", out] + list(sources)
    r = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    if r.returncode != 0:
        raise AssertionError("build failed:\n" + " ".join(cmd) + "\n" + r.stderr)
    return out


def strip_asm(src, marker, replacement=""):
    """The source with its top-level asm(...) block holding `marker` swapped
    for `replacement` (the ARM routine can't run on the PC)."""
    start = src.index("asm(\n")
    end = src.index("\n);\n", start) + len("\n);\n")
    assert marker in src[start:end], "the asm block moved"
    return src[:start] + replacement + src[end:]
