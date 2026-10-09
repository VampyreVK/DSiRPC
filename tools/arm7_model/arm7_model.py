#!/usr/bin/env python3
"""
arm7_model.py - how many ARM7 cycles the console's achievement checker
(nds-bootstrap's rpcprobe/probe_ach_vm.c) takes for one pass over a game's
set, and where they go. For trying out changes to the checker before they
go anywhere near the console.

It builds the checker exactly as the console runs it (Thumb code, the
cardengine's compiler flags, devkitARM in Docker), runs it on an emulated
ARM (the unicorn package) with the set and the game's memory where the
console has them, and counts what a pass does:

  instructions    1 cycle each (the code runs from the ARM7's WRAM, a
                  32-bit bus with no wait states)
  branches        +2 each (a taken branch refills the pipeline; each basic
                  block ends in one)
  loads, stores   +2 a load, +1 a store (the ARM7TDMI's LDR is 1S+1N+1I,
                  STR is 2N)
  main RAM        +8 cycles for an 8- or 16-bit access, +10 for a 32-bit one
                  (a 16-bit bus with wait states). The set, its state and
                  the game's memory are there.

That isn't cycle-exact (no exact wait states, no interrupts, no other
hardware sharing the bus), but it's steady and close: on 2026-10-08 it put
the old checker at about 2.0 million cycles a pass for Platinum (with a RAM
dump), and on hardware that build did 1.4 passes a second with turns of 16
to 26 scanlines, which agrees within about 15%. Use it to compare versions
and to see what's expensive; check on hardware with the "DSiRPC ach" report
(its passes a second, and l=, the longest turn).

A set has two lanes (core/offline.py's split_lanes()): the pass lane is
measured as passes, and the frame lane as what it costs every frame: the
sampling (in the VBlank interrupt) and the checking of a sample, both on the
first frame (every value changes) and on a frame where nothing changed (the
checker skips an achievement whose values didn't change).

"At N scanlines a frame" turns pass cycles into passes a second, if every
frame gives the pass lane that much of the game's idle time
(RPCPROBE_ACH_IDLE_LINES_PER_FRAME in the checker's rpcprobe_build.h, less
what the frame lane takes, or --lines). A scanline is about 2,130 ARM7
cycles and there are 59.83 VBlanks a second.

Usage, from the repo root:
  python tools/arm7_model/arm7_model.py CPUE                      # Platinum's set, from ra/CPUE.json
  python tools/arm7_model/arm7_model.py CPUE --ram ram_dump.bin   # with a RAM dump, so pointers go where the game's do
  python tools/arm7_model/arm7_model.py ADME --profile functions  # where the cycles go, by function
  python tools/arm7_model/arm7_model.py ADME --profile lines --top 30
  python tools/arm7_model/arm7_model.py CPUE --compare C:\\Projects\\vm_try   # this repo's checker against a changed copy
  python tools/arm7_model/arm7_model.py --set CPUE.DRS            # a set file as the launcher keeps them (sd:/DSiRPC/sets)

--compare (and --vm) take folders with probe_ach_vm.c and probe_ach_vm.h; the
default is nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe. Builds go
in tools/arm7_model/build/ (git ignores it).

Needs Docker with devkitARM (the image the nds-bootstrap build uses; see
docs/DEVELOPMENT.md), the unicorn package (pip install unicorn) and, to build
a set from a game code, rcheevos with DSiRPC's set compiler
(third_party/rcheevos, as for offline play).
"""

import argparse
import bisect
import collections
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

DEFAULT_VM = os.path.join(REPO, "nds-bootstrap", "retail", "cardenginei", "arm7", "source", "rpcprobe")
DEFAULT_IMAGE = "devkitpro/devkitarm:20241104"
TOOLS = "/opt/devkitpro/devkitARM/bin/arm-none-eabi-"
# retail/cardenginei/arm7/Makefile's CFLAGS and ARCH
CFLAGS = "-g -Wall -Os -mcpu=arm7tdmi -mtune=arm7tdmi -fomit-frame-pointer -ffast-math -mthumb -march=armv4t"

# Where things are on the console
WRAM, WRAM_SIZE = 0x037E0000, 0x20000      # the cardengine's code and data, and our stack
MAIN, MAIN_SIZE = 0x02000000, 0x400000     # the game's memory (RetroAchievements address 0)
ACH, ACH_SIZE = 0x0CFB0000, 0x40000        # DSIRPC_ACH_LOCATION: the set, then its state
CODE = 0x037E0400                          # CARDENGINEI_ARM7_LOCATION
STOP = 0x037E0100                          # a return address that ends a call
STACK = 0x037FF000

CYCLES_PER_SECOND = 33513982
VBLANKS_PER_SECOND = 59.8261
CYCLES_PER_LINE = CYCLES_PER_SECOND / VBLANKS_PER_SECOND / 263


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


# -- the set ---------------------------------------------------------------------

def load_set(args):
    """(set file bytes, where it came from)"""
    if args.set:
        with open(args.set, "rb") as f:
            return f.read(), args.set
    from core import offline, ra_set
    from core.rcheevos import RcheevosError, RcheevosMissing
    code = args.code.upper()
    s = ra_set.for_game(code, os.path.join(REPO, "ra"))
    if not s:
        fail(f"No set for {code} in ra/ (DSiRPC downloads it the first time the game runs, or use --set)")
    try:
        return offline.build_set(s, code), f"ra/{code}.json"
    except (RcheevosMissing, RcheevosError, offline.FormatError) as e:
        fail(f"Couldn't build {code}'s set: {e}")


def _lane(program):
    from core import offline
    if not program:
        return None
    n_plain, n_mod, n_ach, n_conds = offline.program_counts(program)
    return {'program': program, 'state_size': offline.state_size(program), 'plain': n_plain,
            'mod': n_mod, 'achievements': n_ach, 'conditions': n_conds}


def describe_set(data):
    """{'code', 'pass': lane or None, 'frame': lane or None}; a lane is
    {'program', 'state_size', 'plain', 'mod', 'achievements', 'conditions'}"""
    from core import offline
    if len(data) < offline.SET_HEADER.size or data[:4] != offline.SET_MAGIC:
        fail("That isn't an offline set file (CODE.DRS)")
    s = offline.read_set(data)
    return {'code': s['code'], 'pass': _lane(s['program'] if s['pass'] else b""),
            'frame': _lane(s['frame_program'])}


# -- building the checker --------------------------------------------------------

def build(vm_dir, out_dir, image):
    """Builds bench.c with the checker in vm_dir into out_dir (Docker)."""
    for name in ("probe_ach_vm.c", "probe_ach_vm.h"):
        if not os.path.isfile(os.path.join(vm_dir, name)):
            fail(f"No {name} in {vm_dir}")
    os.makedirs(out_dir, exist_ok=True)
    steps = [
        f"{TOOLS}gcc {CFLAGS} -c /vm/probe_ach_vm.c -o /out/probe_ach_vm.o",
        f"{TOOLS}gcc {CFLAGS} -ffreestanding -nostdlib -Wl,--no-warn-rwx-segments -T /tool/bench.ld"
        f" -I/vm /tool/bench.c /out/probe_ach_vm.o -lc -lgcc -o /out/bench.elf",
        f"{TOOLS}objcopy -O binary /out/bench.elf /out/bench.bin",
        f"{TOOLS}nm -S /out/bench.elf > /out/bench.nm",
        f"{TOOLS}objdump -dl --no-show-raw-insn /out/bench.elf > /out/bench.dis",
        f"{TOOLS}size /out/probe_ach_vm.o > /out/size.txt",
    ]
    cmd = ["docker", "run", "--rm", "-v", f"{vm_dir}:/vm:ro", "-v", f"{HERE}:/tool:ro",
           "-v", f"{out_dir}:/out", image, "sh", "-c", " && ".join(steps)]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        fail("Docker isn't installed (or isn't on PATH); it builds the checker with devkitARM")
    if done.returncode != 0:
        fail(f"Building the checker in {vm_dir} failed:\n{done.stdout}{done.stderr}")
    with open(os.path.join(out_dir, "size.txt")) as f:
        code_bytes = int(f.read().split("\n")[1].split()[0])  # text
    return code_bytes


def read_symbols(out_dir):
    """{name: address}, and [(start, size, name)] of the functions"""
    symbols, functions = {}, []
    with open(os.path.join(out_dir, "bench.nm")) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            symbols[parts[-1]] = int(parts[0], 16)
            if len(parts) == 4 and parts[2] in "tT":
                functions.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
    functions.sort()
    return symbols, functions


def read_lines(out_dir):
    """{instruction address: 'file:line'} from objdump -dl's listing"""
    where, current = {}, "?"
    source = re.compile(r"^(/\S+):(\d+)")
    instruction = re.compile(r"^\s*([0-9a-f]+):\t")
    with open(os.path.join(out_dir, "bench.dis")) as f:
        for line in f:
            m = source.match(line)
            if m:
                current = f"{m.group(1)}:{m.group(2)}"
                continue
            m = instruction.match(line)
            if m:
                where[int(m.group(1), 16)] = current
    return where


# -- the model ---------------------------------------------------------------------

class Model:
    """The checker built in out_dir, with a set (and maybe a RAM dump) loaded."""

    def __init__(self, out_dir, info, ram=None, keep_every=0, profile=False):
        try:
            from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_BLOCK, UC_HOOK_MEM_READ,
                                 UC_HOOK_MEM_WRITE, UC_MEM_WRITE)
            from unicorn import arm_const
        except ImportError:
            fail("This needs the unicorn package: pip install unicorn")
        self.arm = arm_const
        self.write = UC_MEM_WRITE
        self.symbols, self.functions = read_symbols(out_dir)
        mu = self.mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        mu.mem_map(WRAM, WRAM_SIZE)
        mu.mem_map(MAIN, MAIN_SIZE)
        mu.mem_map(ACH, ACH_SIZE)
        with open(os.path.join(out_dir, "bench.bin"), "rb") as f:
            mu.mem_write(CODE, f.read())
        if ram:
            with open(ram, "rb") as f:
                mu.mem_write(MAIN, f.read()[:MAIN_SIZE])
        program = info['program']
        mu.mem_write(ACH + 64, program)
        state = ACH + ((64 + len(program) + 3) & ~3)
        if state + info['state_size'] > ACH + ACH_SIZE:
            fail("The set and its state don't fit in the checker's 256 KB")
        mu.mem_write(self.symbols["keepEvery"], struct.pack("<I", keep_every))

        self.counts = collections.Counter()
        self.blocks = collections.Counter() if profile else None
        self.measured = 1  # passes the counts are for
        mu.hook_add(UC_HOOK_BLOCK, self._block)
        for start, size in ((MAIN, MAIN_SIZE), (ACH, ACH_SIZE)):
            mu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self._main, begin=start, end=start + size - 1)
        mu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self._wram, begin=WRAM, end=WRAM + WRAM_SIZE - 1)

        result = self.call("bench_load", len(program), state, info['state_size'])
        if result != 0:
            fail(f"The checker didn't take the set (AchVm_Load: {result - (1 << 32) if result >> 31 else result})")

    def _block(self, mu, address, size, user_data):
        thumb = mu.reg_read(self.arm.UC_ARM_REG_CPSR) & 0x20
        self.counts['instructions'] += size // 2 if thumb else size // 4
        self.counts['branches'] += 1
        if self.blocks is not None:
            self.blocks[(address, size, 2 if thumb else 4)] += 1

    def _main(self, mu, access, address, size, value, user_data):
        self.counts['main writes' if access == self.write else 'main reads'] += 1
        self.counts['main waits'] += 10 if size == 4 else 8

    def _wram(self, mu, access, address, size, value, user_data):
        self.counts['WRAM writes' if access == self.write else 'WRAM reads'] += 1

    def call(self, name, *args):
        a = self.arm
        for register, value in zip((a.UC_ARM_REG_R0, a.UC_ARM_REG_R1, a.UC_ARM_REG_R2), args):
            self.mu.reg_write(register, value)
        self.mu.reg_write(a.UC_ARM_REG_SP, STACK)
        self.mu.reg_write(a.UC_ARM_REG_LR, STOP | 1)
        self.mu.emu_start(self.symbols[name] | 1, STOP)
        return self.mu.reg_read(a.UC_ARM_REG_R0)

    def word(self, name):
        return struct.unpack("<I", self.mu.mem_read(self.symbols[name], 4))[0]

    def _cycles(self):
        k = self.counts
        return (k.get('instructions', 0) + 2 * k.get('branches', 0)
                + 2 * (k.get('WRAM reads', 0) + k.get('main reads', 0))
                + k.get('WRAM writes', 0) + k.get('main writes', 0) + k.get('main waits', 0))

    def frames(self, n=4):
        """The frame lane: (sampling, checking on the first frame, checking
        on a frame where nothing changed), in cycles."""
        out = ACH + ACH_SIZE - 0x8000  # (the samples go somewhere out of the way)
        costs = []
        for _ in range(n):
            self.counts.clear()
            self.call("bench_sample", out)
            sample = self._cycles()
            self.counts.clear()
            self.call("bench_run_sampled", out)
            costs.append((sample, self._cycles()))
        return costs[-1][0], costs[0][1], costs[-1][1]

    def passes(self, n):
        """Runs a first pass (every value changes from 0), two more for the
        checker to see nothing changed, then n passes; returns the averages
        of those n, with the first pass's cycles as 'first'."""
        self.counts.clear()
        self.call("bench_pass")
        first = self._cycles()
        self.call("bench_pass")
        self.call("bench_pass")
        self.counts.clear()
        if self.blocks is not None:
            self.blocks.clear()
        checks = self.word("keepCalls")
        calls = sum(self.call("bench_pass") for _ in range(n))
        self.measured = n
        c = {k: v / n for k, v in self.counts.items()}
        c['cycles'] = (c.get('instructions', 0) + 2 * c.get('branches', 0)
                       + 2 * (c.get('WRAM reads', 0) + c.get('main reads', 0))
                       + c.get('WRAM writes', 0) + c.get('main writes', 0) + c.get('main waits', 0))
        c['time checks'] = (self.word("keepCalls") - checks) / n
        c['calls'] = calls / n
        c['first'] = first
        return c


# -- reports ----------------------------------------------------------------------------

def budget_lines(vm_dir, override):
    if override:
        return override
    try:
        with open(os.path.join(vm_dir, "rpcprobe_build.h")) as f:
            m = re.search(r"#define\s+RPCPROBE_ACH_IDLE_LINES_PER_FRAME\s+(\d+)", f.read())
        return int(m.group(1)) if m else 120
    except OSError:
        return 120


def report_frame(label, code_bytes, costs):
    sample, first, steady = costs
    lines = lambda c: c / CYCLES_PER_LINE
    print(f"\n{label}, the frame lane (checker code: {code_bytes:,} bytes)")
    print(f"  sampling: {sample:,.0f} cycles a frame ({lines(sample):.1f} scanlines of the VBlank)")
    print(f"  checking a sample: {first:,.0f} cycles when every value changed ({lines(first):.1f} scanlines), "
          f"{steady:,.0f} when none did ({lines(steady):.1f})")


def report(label, code_bytes, c, lines):
    rate = lambda cycles: lines * CYCLES_PER_LINE * VBLANKS_PER_SECOND / cycles if lines > 0 else 0
    print(f"\n{label}, the pass lane (checker code: {code_bytes:,} bytes)")
    print(f"  one pass: {c['first']:,.0f} cycles when every value changed, {c['cycles']:,.0f} when none did "
          f"(this, below)")
    print(f"    instructions {c.get('instructions', 0):,.0f}, branches {c.get('branches', 0):,.0f}")
    print(f"    WRAM reads/writes {c.get('WRAM reads', 0):,.0f} / {c.get('WRAM writes', 0):,.0f}, "
          f"main RAM reads/writes {c.get('main reads', 0):,.0f} / {c.get('main writes', 0):,.0f}")
    print(f"    time checks {c['time checks']:,.0f}" + (f", in {c['calls']:.1f} turns" if c['calls'] > 1 else ""))
    print(f"  at {lines} scanlines a frame: about {rate(c['first']):.1f} to {rate(c['cycles']):.1f} passes a second")


def instructions_by_address(model):
    """{address: instructions executed there in a pass}"""
    out = collections.Counter()
    for (address, size, step), n in model.blocks.items():
        for a in range(address, address + size, step):
            out[a] += n
    return {a: n / model.measured for a, n in out.items()}


def profile_functions(model, top):
    by_address = instructions_by_address(model)
    starts = [f[0] for f in model.functions]
    per, entered = collections.Counter(), collections.Counter()
    for address, n in by_address.items():
        i = bisect.bisect_right(starts, address) - 1
        start, size, name = model.functions[i] if i >= 0 else (0, 0, "?")
        name = name if address < start + size else "?"
        per[name] += n
    for (address, size, step), n in model.blocks.items():
        i = bisect.bisect_right(starts, address) - 1
        if i >= 0 and address == model.functions[i][0]:
            entered[model.functions[i][2]] += n / model.measured
    total = sum(per.values())
    print(f"\n  instructions by function, a pass ('calls': entries at its start):")
    for name, n in per.most_common(top):
        print(f"    {name:32s} {n:11,.0f} {100 * n / total:5.1f}%   calls {entered[name]:,.0f}")


def profile_lines(model, out_dir, vm_dir, top):
    by_address = instructions_by_address(model)
    where = read_lines(out_dir)
    per = collections.Counter()
    for address, n in by_address.items():
        per[where.get(address, "?")] += n
    total = sum(per.values())
    sources = {}

    def text(place):
        m = re.match(r"^/(vm|tool)/(.+):(\d+)$", place)
        if not m:
            return ""
        path = os.path.join(vm_dir if m.group(1) == "vm" else HERE, m.group(2))
        if path not in sources:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    sources[path] = f.read().split("\n")
            except OSError:
                sources[path] = []
        n = int(m.group(3))
        return sources[path][n - 1].strip()[:70] if 0 < n <= len(sources[path]) else ""

    print(f"\n  instructions by source line, a pass:")
    for place, n in per.most_common(top):
        short = place.replace("/vm/", "").replace("/tool/", "")
        print(f"    {short:24s} {n:10,.0f} {100 * n / total:5.1f}%  {text(place)}")


def main():
    ap = argparse.ArgumentParser(description="An ARM7 cost model for the console's achievement checker")
    ap.add_argument("code", nargs="?", help="a game code with a set in ra/ (e.g. CPUE)")
    ap.add_argument("--set", help="a set file (CODE.DRS) instead of a game code")
    ap.add_argument("--ram", help="a 4 MB RAM dump of the game (default: all zeros)")
    ap.add_argument("--vm", default=DEFAULT_VM, help="the folder with probe_ach_vm.c/.h (default: this repo's)")
    ap.add_argument("--compare", nargs="+", default=[], metavar="FOLDER", help="other checker folders to run too")
    ap.add_argument("--profile", choices=["functions", "lines"], help="where the instructions go")
    ap.add_argument("--top", type=int, default=20, help="rows in a profile (default 20)")
    ap.add_argument("--passes", type=int, default=2, help="passes to average, after a warm-up pass (default 2)")
    ap.add_argument("--keep-every", type=int, default=0, metavar="N",
                    help="stop and carry on every N time checks, like a VBlank budget running out (default: never)")
    ap.add_argument("--lines", type=int, help="the scanline budget for 'passes a second' (default: rpcprobe_build.h's)")
    ap.add_argument("--image", default=os.environ.get("DEVKITARM_IMAGE", DEFAULT_IMAGE),
                    help=f"the devkitARM Docker image (default {DEFAULT_IMAGE}, or $DEVKITARM_IMAGE)")
    args = ap.parse_args()
    if not args.code and not args.set:
        ap.error("give a game code (e.g. CPUE) or --set FILE")

    data, source = load_set(args)
    lanes = describe_set(data)
    print(f"Set: {lanes['code']} from {source}")
    for name in ("frame", "pass"):
        info = lanes[name]
        if info:
            print(f"  {name} lane: {info['achievements']} achievements, {info['conditions']:,} conditions, "
                  f"{info['plain']:,} + {info['mod']:,} memory values ({len(info['program']) / 1024:.0f} KB "
                  f"+ {info['state_size'] / 1024:.0f} KB of state)")
        else:
            print(f"  {name} lane: empty")
    print(f"Game memory: {args.ram or 'all zeros (--ram for a dump)'}")

    first = None
    for n, vm_dir in enumerate([args.vm] + args.compare):
        vm_dir = os.path.abspath(vm_dir)
        out_dir = os.path.join(HERE, "build", f"vm{n}")
        code_bytes = build(vm_dir, out_dir, args.image)
        label = os.path.relpath(vm_dir, REPO) if vm_dir.startswith(REPO) else vm_dir
        frame_lines = 0
        if lanes['frame']:
            costs = Model(out_dir, lanes['frame'], args.ram).frames()
            report_frame(label, code_bytes, costs)
            frame_lines = costs[2] / CYCLES_PER_LINE
        info = lanes['pass']
        if not info:
            continue
        model = Model(out_dir, info, args.ram, args.keep_every, profile=bool(args.profile))
        c = model.passes(max(1, args.passes))
        report(label, code_bytes, c, max(0, budget_lines(vm_dir, args.lines) - round(frame_lines)))
        if first is None:
            first = c
        else:
            print(f"  against the first: {100 * (c['cycles'] / first['cycles'] - 1):+.1f}% cycles")
        if args.profile == "functions":
            profile_functions(model, args.top)
        elif args.profile == "lines":
            profile_lines(model, out_dir, vm_dir, args.top)


if __name__ == "__main__":
    main()
