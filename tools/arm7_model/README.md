# ARM7 cost model for the achievement checker

`arm7_model.py` tells you how many ARM7 cycles the console's achievement
checker (nds-bootstrap's `rpcprobe/probe_ach_vm.c`) spends on one pass over
a game's set, and where they go, without touching the console. It's for
trying out changes to the checker: build a changed copy, compare, keep what
helps.

## What it does

1. Builds the checker the way the console runs it: Thumb code with the
   cardengine's compiler flags (`retail/cardenginei/arm7/Makefile`), with
   devkitARM in Docker. `bench.c` is the driver around it, and `bench.ld`
   puts it all in ARM7 WRAM, like the cardengine.
2. Builds the game's set from `ra/CODE.json` with DSiRPC's own
   `core/offline.py` (or takes a `CODE.DRS` file with `--set`).
3. Runs it on an emulated ARM ([unicorn](https://www.unicorn-engine.org/))
   with the set where the console has it (`DSIRPC_ACH_LOCATION`) and the
   game's memory at `0x02000000`: a warm-up pass, then the measured ones.
4. Counts instructions, branches and memory accesses, and turns them into
   cycles.

## The model

| What | Cycles |
|---|---|
| An instruction | 1 (the code runs from WRAM: a 32-bit bus, no wait states) |
| A taken branch (each basic block ends in one) | +2 (the pipeline refills) |
| A load / a store | +2 / +1 (the ARM7TDMI's LDR is 1S+1N+1I, STR is 2N) |
| Main RAM (the set, its state, the game's memory) | +8 for an 8- or 16-bit access, +10 for a 32-bit one (a 16-bit bus with wait states) |

It isn't cycle-exact: no exact wait states, no interrupts, nothing else on
the bus. But it's steady and close. On 2026-10-08 it put the old checker at
about 2.0 million cycles a pass for Platinum (with a RAM dump), and on
hardware that build did 1.4 passes a second with turns of 16 to 26
scanlines, which agrees within about 15%. Treat it as a ruler for comparing
versions and finding hot spots, and confirm on hardware with the console's
"DSiRPC ach" report: its passes a second, and `l=`, its longest turn (see
`rpcprobe/DEBUGGING.md`).

A set has two lanes (DSiRPC's `core/offline.py`, `split_lanes()`). The
frame lane is reported as what it costs every frame: the sampling (in the
VBlank) and the checking of a sample, on a frame where every value changed
and on one where none did (the checker skips an achievement whose values
and hits didn't change). The pass lane is reported as a pass, the same two
ways (the first pass, and one after the checker has seen nothing change).
"At N scanlines a frame: about X to Y passes a second" assumes the pass lane
gets that much of the game's idle time every frame
(`RPCPROBE_ACH_IDLE_LINES_PER_FRAME` from the checker's `rpcprobe_build.h`,
less the frame lane's checking when nothing changed, or `--lines`). A
scanline is about 2,130 ARM7 cycles and there are 59.83 VBlanks a second.
DSiRPC's `offline.frame_costs()` (how big a frame lane may be) was fitted to
this model; refit it when the checker changes much.

## Using it

You need Docker with the devkitARM image (the one the nds-bootstrap build
uses; see `docs/DEVELOPMENT.md`) and the unicorn package:
`pip install unicorn`. Building a set from a game code also needs rcheevos
with DSiRPC's set compiler (`third_party/rcheevos`, as for offline play).

From the repo root:

```
python tools/arm7_model/arm7_model.py CPUE
python tools/arm7_model/arm7_model.py CPUE --ram ram_dump.bin
python tools/arm7_model/arm7_model.py ADME --profile functions
python tools/arm7_model/arm7_model.py ADME --profile lines --top 30
python tools/arm7_model/arm7_model.py CPUE --compare C:\Projects\vm_try
python tools/arm7_model/arm7_model.py --set CPUE.DRS
```

| Option | Meaning |
|---|---|
| `CODE` | A game with a set in `ra/` (DSiRPC downloads it the first time the game runs) |
| `--set FILE` | A set file instead (`sd:/DSiRPC/sets/CODE.DRS` from the SD card) |
| `--ram FILE` | A 4 MB RAM dump of that game. Without one, memory is all zeros, so pointer chains all lead to address 0. Platinum's costs about 10% more with its dump |
| `--profile functions` / `lines` | Where the instructions go in a pass: by function (with how often each is entered), or by source line (with the line) |
| `--compare FOLDER...` | Also run the checker in these folders and show the difference |
| `--vm FOLDER` | The checker to measure first (default: this repo's `nds-bootstrap/.../rpcprobe`) |
| `--keep-every N` | Say "stop" at every Nth time check, as a budget running out does, to see what carrying on costs |
| `--passes N` | Passes to average once nothing changes (default 2) |
| `--lines N` | The pass lane's scanlines a frame, for "passes a second" |
| `--image NAME` | The devkitARM image (default `devkitpro/devkitarm:20241104`, or `$DEVKITARM_IMAGE`) |

A folder for `--compare` or `--vm` needs `probe_ach_vm.c` and
`probe_ach_vm.h`. To try a change, copy `rpcprobe/` somewhere, edit
the copy and compare it with the repo's. Builds go in
`tools/arm7_model/build/`, which git ignores.

Speed is all this measures. A change to the checker also has to keep giving
exactly rcheevos' results (every achievement's state and every hit count,
frame by frame), which this tool doesn't check.

## What it found (2026-10-08)

Main RAM wasn't the cost; instructions were. Switch statements compiled to
`__gnu_thumb1_case_*` calls, an operand's value and type went through
memory, and each condset phase recounted where it starts. After the fixes,
a pass takes these many cycles (no RAM dump):

| Set | Before | After |
|---|---|---|
| CPUE (Platinum) | 1,829,108 | 1,253,478 (-31%) |
| ADME | 4,862,628 | 3,728,563 (-23%) |
| ATRE | 1,232,070 | 933,518 (-24%) |
| BL9E | 558,106 | 422,492 (-24%) |
| AMCE | 866,490 | 697,803 (-19%) |
| VSOE | 1,346,968 | 1,124,685 (-17%) |
