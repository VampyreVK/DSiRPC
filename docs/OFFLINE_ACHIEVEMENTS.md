# Offline RetroAchievements: how they work

DSiRPC's console checks a game's RetroAchievements itself, on the DSi's or
3DS's second processor (the ARM7), while the game runs, with or without
Wi-Fi, and unlocks exactly what rcheevos (the engine emulators use) would.
This document follows an achievement end to end: how the PC turns a set into
something the console can run, how it gets there, how the console checks it
without slowing the game, how it learns which achievements need checking
every frame, and how the unlocks get back. The byte-level formats are in
[DOCUMENTATION.md](DOCUMENTATION.md) (sections 6 to 8); this is the why and
the how.

```
PC (core/offline.py)                       Console
RetroAchievements set (ra/CODE.json)
  -> rcheevos parses it
  -> dsirpc_offline.c: a program           launcher (sync, TCP 4245)
  -> split_lanes(): frame lane / pass lane   sd:/DSiRPC/sets/CODE.DRS
  -> build_set(): CODE.DRS  ------------>    RPCSET.BIN when the game starts
                                           nds-bootstrap, ARM7 (rpcprobe/)
                                             probe_ach.c: load, sample, check
                                             probe_ach_vm.c: rcheevos' rules
ra/cache/frame_needs.json  <-- notes --      RPCUNLK.BIN: unlocks and notes
unlocks (RetroAchievements) <-- unlocks --   launcher (next sync)
```

## 1. Building a set on the PC

**What goes in.** `app/engine.py` asks `core/offline.py`'s `build_set()` for
a set whenever the launcher syncs. A set holds the achievements of the game
that are left to unlock as far as DSiRPC knows (`--blank-ra` builds whole
sets), official, from the core or a bonus set, that read only main RAM
(`ra_game._unreachable()` leaves out the rest), and that rcheevos can parse.

**Parsing is rcheevos'.** DSiRPC loads rcheevos (`core/rcheevos.py`, the
library in `third_party/rcheevos/`) and has it parse every achievement, as
an emulator would. Its own addition to the library,
`third_party/rcheevos/dsirpc_offline.c` (`dsirpc_offline_compile()`, through
`rcheevos.compile_offline()`), then writes out what rcheevos parsed as a
compact program: the memory values to read (plain ones, and rcheevos'
"modified" ones: the AddSource, SubSource, AddAddress and Remember chains),
then each achievement's groups with their conditions in the order rcheevos
evaluates them, 16 bytes a condition. The program format is version 3 (the
layout is at the top of `probe_ach_vm.c`): an achievement's group count is a
u16 whose bit 15 says whether it has a core group, so up to 32,767 groups
(version 2 had a u8: 255). Left out, and checked only by the PC while it's
watching: achievements that need floating point (the ARM7 has no FPU), and
any with more than 32,767 groups or 65,535 conditions. Because the console
runs rcheevos' own parse, an AddAddress chain or a Remember is exactly
rcheevos', not a reimplementation of its text format.

**Two lanes.** rcheevos' rules are meant to be checked every frame: a hit
count counts frames, a delta compares with the frame before, a one-frame
flag is gone the next frame. The console can't check a whole big set every
frame, so a set has two programs:

- the **frame lane**: achievements checked on every frame the game draws,
  from memory read at the start of that frame;
- the **pass lane**: the rest, checked in passes, one after another, as fast
  as the time left allows (tens a second for most sets).

`split_lanes()` fills the frame lane in this order:

1. achievements **proven** to need every frame (section 6);
2. achievements `timing()` guesses need it that haven't been found clean.
   `timing()` reads the MemAddr: 3 for hit targets, ResetIf, PauseIf,
   ResetNextIf, AddHits and SubHits, 2 for deltas and priors, 1 otherwise;
3. guesses the console found **clean** (no difference) in `CLEAN_SESSIONS`
   (2) sessions or more;
4. everything else.

Within each group the cheapest go first, so as many as possible fit. Each
candidate is tried by compiling the lane with it (`compile_offline(frame +
[t])`), so memory values that achievements share count once, as they do on
the console, where a chain's root often feeds hundreds of conditions. That's
a compile per achievement, a tenth of a second for a big set.

**The cost model.** A candidate goes in only while the lane's costs stay
within three budgets, in ARM7 cycles (a frame is 263 scanlines of 2,130
cycles):

| Budget | Cycles | What it pays for |
|---|---|---|
| `FRAME_SAMPLE_CYCLES` | 42,000 (about 20 scanlines) | reading the lane's memory values at the start of every VBlank |
| `FRAME_CHECK_CYCLES` | 110,000 (about 52 scanlines) | checking one sample in the game's idle time, when most values didn't change |
| `FRAME_BUSY_CYCLES` | 7 x 110,000 | checking one sample where every value changed, which the ring then has to absorb |

`frame_costs()` gives sampling as `192 x plain + 500 x modified + 150` and
steady checking as `119 x values + 350 x achievements + conditions`;
`frame_busy_cost()` gives `545 x values + 2659 x achievements + 436 x
conditions`. The constants are fitted to the checker itself, run on
`tools/arm7_model` (the Thumb build in an emulator, counting instructions
and memory waits), the busy one so that it never comes out under what the
model measured.

**Fitting it in.** The console sets aside 512 KB (`DSIRPC_ACH_SIZE`) at
`DSIRPC_ACH_LOCATION` (`0x0CF08000`, right below the in-game menu's window),
less 4 KB for reading `RPCUNLK.BIN` and 2 KB for the per-frame capture's
ring: 506 KB (`offline.ACH_MEMORY`; 250 KB of 256 KB until 2026-11-11,
which Pokemon HeartGold's 166 achievements didn't fit). The set file, the
pass lane's state, the frame lane's state twice (one copy samples, one
checks), its ring of samples and, when there's room, the shadow check's copy
all have to fit (`set_memory()`). `build_set()` fits the set with the
smallest ring (`RING_MIN`, 8 samples) and, while it doesn't fit, gives up in
this order:

1. the shadow check's copy (logged once a run: "no room for the shadow
   check's copy of the frame lane");
2. frame lane places, the least needed first: those achievements move to
   the pass lane, where they take one state instead of two plus the ring;
3. the biggest pass lane achievements.

Then the ring doubles while the set still fits, up to `RING_MAX` (256
samples, about 4.3 seconds). Of the eight sets on the development PC,
seven get 128 or 256 samples; Animal Crossing: Wild World (157 achievements, 173 KB) fits whole
with 8 and no shadow check.

**The list and the stamp.** After the programs comes the list for the
in-game menu (`build_list()`): every achievement of the game with its title,
description, points and whether it's earned. The header's stamp is the
CRC-32 of everything after it; `ra/cache/console_sets.json` remembers which
achievements each stamp has in which lane (`remember_set()`), and a set is
only sent when the console's copy is missing or has another stamp.

## 2. Getting it to the console

The launcher (`launcher/source/sync.c`) syncs with DSiRPC over TCP 4245
whenever it connects and when a game is picked: it sends the stamps of the
sets it has and `RPCUNLK.BIN`, and gets back the sets that changed, which it
writes to `sd:/DSiRPC/sets/CODE.DRS`. Starting a game, it puts the game's set
in `RPCSET.BIN` beside it and starts DSiRPC's nds-bootstrap. The answer's
`taken` is how many valid slots DSiRPC took from `RPCUNLK.BIN`, and the
launcher clears the file only when that matches its own count, so nothing
is lost on a bad connection.

## 3. On the console: loading

On the game's first VBlank (the only time the VBlank may read the SD card),
`probe_ach.c`'s loader reads `RPCSET.BIN` into `DSIRPC_ACH_LOCATION`. The
header is checked first: "DRSE", versions 2 to 5, the running game's code.
Byte 44 (the ring's size) is read before anything else, because the menu's
anchor is then written over bytes 40-63. `AchVm_Load()` sets up each lane's
state after the set: every memory value with its last change, every
condition's hit count, the change-stamp map (below). The frame lane gets a
second VM for sampling (`sampleVm`), the ring, and the shadow check's copy
if what's left holds it. `RPCUNLK.BIN` is read into the 4 KB after the set's
space, to find where the next slot goes and which of the game's
achievements already wait there; those aren't checked again. Over the next
few VBlanks the set's CRC-32 is checked a slice at a time, and only then
does it run.

## 4. The checker (`probe_ach_vm.c`)

The interpreter is a port of rcheevos 12.5's `rc_runtime_do_frame`, without
floating point: a pass reads every memory value (pointer chains and
AddSource chains included), then evaluates every achievement with rcheevos'
rules: hit counts and targets, ResetIf, PauseIf, AndNext and OrNext,
AddHits and SubHits, Measured, alt groups, ResetNextIf, Remember, and an
achievement having to be false once before it can trigger. A pass is
rcheevos' "frame".

**Skipping what can't have changed.** An achievement checked again with the
same memory values and deltas, and the same state and hits, gives the same
result, so it's skipped. Each memory value has a list of the achievements
that name it (`mapStart`, `mapList`); when a value changes, its achievements
are stamped with the update number (`achChange`), so `unchanged()` is a
compare: an achievement is unchanged when its stamp is older than the update
before this one (deltas need two quiet updates) and its last check left its
state and hits as they were (`achSig`, a hash of the hit counts that
matter). On a frame where little changes, most achievements cost a small
fraction of a full check. The commonest AddSource, SubSource and AddAddress
links (two operands, each a constant or a masked memory value) take a fast
path, picked once at load (`fastModified()`).

The checker is plain C, and the same file runs on a PC in the tests (section
9), side by side with rcheevos.

## 5. The frame lane: sampling, the ring, the ARM9 cache

**Sampling.** At the start of every VBlank, `ProbeAch_Sample()` reads every
memory value the frame lane uses, all at once, into the next slot of the
ring (`AchVm_Sample()`, on the sampling VM). Reading at the same point of
every frame is what makes a one-frame flag visible: it's there at the start
of the frame after the game set it.

**Checking.** Later, in the game's idle time, the checking takes the samples
in order (`AchVm_RunFed()`), each as one pass with that sample as its memory,
prior values and changes included. So every frame is checked as it was,
however late. The checking is resumable: it stops whenever its time is up
and carries on next time from the same achievement.

**Time.** The checking runs while the game's ARM7 idles, from
nds-bootstrap's swiHalt hook (`ProbeAch_Idle()`), outside interrupts, so the
game's own interrupts come first: at most 16 scanlines a visit and 120 a
frame (`RPCPROBE_ACH_IDLE_LINES_PER_VISIT`, `..._PER_FRAME`), stopping at once
when nds-bootstrap has a ROM read to serve. The frame lane's samples come
first, then the shadow check, then the pass lane, which can stop after any
8 memory values or conditions. A game whose swiHalt can't be hooked gets its
checking in the VBlank instead: 20 scanlines after the rest of the tick
(`RPCPROBE_ACH_LINES_PER_VBLANK`).

**The ring.** The ring holds 8 to 256 samples (the set's header says how
many). In a busy stretch (a load, a line clear, a level where every value
moves) the checking falls behind and the ring fills; it catches up when the
game goes quiet. Only if it falls a whole ring behind does a frame go
unsampled (`fd=` in the report, "not sampled" in DSiRPC's log). With 83
achievements every frame, Tetris DS's busy stretches outran an 8- or
16-sample ring during development; with 256 it loses none.

**The ARM9's cache.** The game runs on the ARM9, whose data cache can hold a
write for a while before it reaches main RAM, where the ARM7 reads it.
DSiRPC's ARM9 half patches the game's `OS_Halt` so the ARM9 writes its data
cache back whenever the game idles, which most games do once their frame is
done, so the values are in main RAM by the next VBlank. rpcprobe finds
`OS_Halt` by its three instructions in the game's static code
(`probe_watch.c`) and hands the addresses to the ARM9 (`dsirpc_watch.c`),
which patches each one only if all three words are still there. Some games'
SDK puts `OS_Halt` in ITCM instead (an autoload block the game copies there
as it starts), which the ARM7 can't read: when rpcprobe's search finds none,
it asks anyway, and the ARM9 searches ITCM itself, once a game, and patches
what it finds the same way. Hellos say whether it's there (`a9=2` or more)
and how many copies were found (`a9s=`), and DSiRPC logs it in words
("ARM9 half found, 1 idle call(s) patched"); the report counts samples
taken with no write-back since the VBlank before (`fc=`). A game whose
idle call is neither (`a9=1 a9s=0`) gets no write-backs, so a value can be
read a frame or more late, and one that changes and changes back while it's
still in the cache can be missed; `tools/find_idle.py` shows where such a
game waits.

## 6. Learning which achievements need every frame

`timing()` is only a guess: it can't tell a flag that's set for one frame
from a value that stays put, so many guessed achievements would be fine in
the pass lane, and the frame lane is where the cost is. So DSiRPC learns.

**The shadow check, on the console.** A third copy of the frame lane
(`shadowVm`, when the set left room) checks every 8th sample again
(`SH_EVERY`), the way the pass lane would see it. Each unlock and each reset
(a ResetIf clearing hits) the frame lane sees counts +1 for its achievement,
each the shadow sees -1. An achievement left uneven for more than
`SH_WINDOW` (3) shadow passes is **proven** to need the frame lane; one whose
memory changed for `SH_CLEAN` (600) samples with nothing uneven is **clean**
so far. Either way a note goes into the unlock queue (ID `0xFFFFFFFE` or
`0xFFFFFFFD`, the achievement's ID in the slot's "when"), and the
achievement isn't judged again that start. The shadow never holds up the
frame lane: it gets its own copy of the sample (`shSample`), runs only while
no sample waits, stops for a new one, and skips a due sample if it's still
on the last. It never unlocks anything. At most 64 notes a start, and they
never take the last 32 free slots of `RPCUNLK.BIN`.

**The shadow check, on the PC.** While DSiRPC watches a game, the
achievements it checks every frame from the per-frame capture
(`core/frame_capture.py`) also go through `frame_needs.Shadow`: two rcheevos
runtimes on the same frames, one every frame and one every 8th, with the
same rule for a difference.

**Where it's kept.** Both feed `ra/cache/frame_needs.json`
(`core/frame_needs.py`): proofs by achievement ID and the CRC-32 of its
MemAddr (so a proof stops counting when RetroAchievements changes the
achievement), with who found it (`pc`, `console`), and clean counts by
session. Proofs are only ever added (`merge()` is a union; downloading a set
never touches the file). At a sync, `engine._shadow_notes()` adds the
console's notes before the sets are built, so a set with a new proof goes
back at the same sync. In `split_lanes()` a proof puts an achievement first,
a clean count only moves it down; nothing else changes. `--clear-learning
[CODE]` forgets it all (with a backup, `frame_needs.json.bak`) and throws
away the console's waiting notes, for testing.

## 7. Saving unlocks

An unlock goes into a small queue (`ACH_PENDING`, 8) with the console's time.
The SD card can't be touched from the VBlank once the game runs, so the
queue is written from the swiHalt hook (`Probe_HaltTick()` ->
`ProbeAch_SaveOne()`), under the same lock nds-bootstrap's own saves and
ROM reads use, one 16-byte slot at a time: achievement ID, game code, when
(seconds since 2000 by the console's clock), the sequence number and a check
word, so a half-written slot is skipped. A game whose swiHalt can't be
hooked saves from the VBlank after two seconds without a halt. An unlock's
sequence number is its slot less the notes before it that start, so the
unlocks' numbers stay one after another. One slot per start keeps the
start's playtime instead, rewritten each minute.

The in-game menu reads the set's list, which the checker marks as it
unlocks, through an anchor in the set's header (bytes 40-63:
`common/include/dsirpc_ach_menu.h`), so new unlocks show up top the moment
the menu opens. On a DSi, the LED picked for TWiLight Menu++'s "ROM read
LED" setting pulses while there are unlocks the menu hasn't shown yet
(`probe_led.c`, through the BPTWL chip); opening the menu stops it.

## 8. While DSiRPC is watching

Online, the checker reports after each hello (`DSiRPC ach ...`: what it runs,
its unlocks, passes a second, its frame lane's numbers and the set's stamp).
The stamp tells DSiRPC which achievements the console checks, so DSiRPC
leaves those to it and checks only the rest on the PC: the ones that need
every frame through the per-frame capture's 8 watched values, the others
about once a second. Each console unlock counts in DSiRPC as soon as its
report arrives. If the reports stop for 10 seconds, the PC checks everything
again. Once a minute DSiRPC logs the checker's speed: passes a second, its
longest VBlank turn, frames a second checked, frames not sampled, and
samples without the ARM9's write-back.

## 9. When something doesn't fit, and other fallbacks

| What | What happens |
|---|---|
| The set doesn't fit in 506 KB | No shadow check, then frame lane achievements move to the pass lane, then the biggest pass lane ones are left out (section 1) |
| An achievement needs floating point, or has more than 32,767 groups | Not in the set; checked by the PC while DSiRPC watches |
| The checking falls a whole ring behind | Frames go unsampled until there's room (`fd=`); the pass lane waits |
| No swiHalt hook | Checking (20 scanlines) and saving happen in the VBlank |
| No ARM9 write-back | Values can be read a frame late (`fc=` counts those samples) |
| The set is damaged, another game's, or a version the console doesn't know | Not used; the report's `n` says why, and so does the in-game menu |
| `RPCUNLK.BIN` is full | Unlocks still count in the menu and the reports, but aren't saved (`x=`) until the launcher hands the file to DSiRPC |
| No room for notes | No notes that start; unlocks always keep 32 slots |
| The reports stop for 10 s | The PC checks everything again |

## 10. How it's tested

- `tests/test_checker_vm.py`: the interpreter beside rcheevos on the same
  memory, on real sets and on random achievements using every condition
  type, size and operator, stopping at random points: every state and every
  hit count must match after every frame, with and without the skipping.
- `tests/test_offline_checker.py`: `probe_ach.c` itself (the `ach_host`
  harness in `tests/c/ach`), with real sets from `core/offline.py`,
  checking in the idle time and in the VBlank, rings from 8 to 256, the
  shadow check on and off, long busy stretches (the frame lane must never
  drop a sample the ring can hold, and never wait for the shadow), and the
  shadow notes.
- `tests/test_offline_format.py`, `tests/test_frame_needs.py`,
  `tests/test_unlocks.py`: the set and unlock formats, the lane picker, the
  fitting order and the ring, the learning and `--clear-learning`.
- `tests/test_igm_menu.py`: the in-game menu's own code on the PC, reading a
  set's list and anchor.

The harnesses build the console's C with the PC's gcc and the sanitizers on,
mapping the DS's memory at its real addresses, so a bad read or write fails
a test.

## 11. Files

| File | What |
|---|---|
| `core/offline.py` | `build_set()`, `split_lanes()`, `timing()`, `frame_costs()`, `set_memory()`, `build_list()`, `read_set()`, the unlock file (`read_unlocks()`, `read_shadow_notes()`, `count_slots()`), the sync's messages |
| `core/frame_needs.py` | `frame_needs.json`: proofs, clean counts, `merge()`, `prune()`, `wipe()`, and `Shadow`, the PC's shadow check |
| `core/console_sync.py` | The launcher's sync on the PC side |
| `core/rcheevos.py`, `third_party/rcheevos/dsirpc_offline.c` | rcheevos, and the compiler to the console's program |
| `app/engine.py` | Which sets to build, the console's unlocks and notes |
| `launcher/source/sync.c` | The launcher's sync |
| `nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/probe_ach.c` | Loading, sampling, the ring, the shadow check, saving, the reports |
| `.../rpcprobe/probe_ach_vm.c` | The interpreter (rcheevos' rules), the skipping, sampling |
| `.../rpcprobe/probe_led.c` | The achievement LED |
| `.../arm9_igm/source/dsirpc_ach.c` | The in-game menu's achievements |
| `nds-bootstrap/retail/common/include/dsirpc_ach_menu.h` | The menu's anchor and list |
