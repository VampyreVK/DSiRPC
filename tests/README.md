# DSiRPC's tests

Unit and integration tests for the parts that decide whether an achievement
is missed: the console's own code (offline play's checker, the per-frame
capture, the ARM9's idle-time write-back), checked against rcheevos frame
by frame, and the PC side (the offline formats, the launcher's sync, the
protocol client, the Black/White parser, the hub) against a fake DSi.
GitHub runs them all on every change to the code they cover
([`.github/workflows/tests.yml`](../.github/workflows/tests.yml)).

## What's tested

| File | What |
|---|---|
| `test_checker_vm.py` | The console's checker (`rpcprobe/probe_ach_vm.c`) against rcheevos every frame on a simulated game: with and without its change-driven skipping, the frame lane's sample-now-check-later path, passes cut short by a time budget, random condition soups (`fuzz`), DSiRPC's unlocks never triggering, programs cut short |
| `test_offline_checker.py` | Offline play's checker as a whole (`rpcprobe/probe_ach.c`) with a real set from `core/offline.py`: frame lane unlocks in rcheevos' order with idle visits, VBlank-only checking, a starved idle side, ROM reads waiting, no ROM-read callback (`altReadMethod` games) and missed write-backs; pushed unlocks marked earned; unlocks saved to `RPCUNLK.BIN` read back by DSiRPC and not checked again next session; bad sets refused |
| `test_watch_idle.py` | The idle-time write-back: rpcprobe's `OS_Halt` search (`rpcprobe/probe_watch.c`) and the ARM9 half's patching (`cardenginei/arm9/source/dsirpc_watch.c`), freshness, the capture ring and its `'W'`/`'F'` requests, soft resets, the doorbell never rung over nds-bootstrap's own commands |
| `test_offline_format.py` | `core/offline.py`: `RPCUNLK.BIN` slots (torn, repeated, wrong clock), `.DRS` sets (lanes, list, stamp, the console's memory limit), the in-game menu's list, the sync request and answer, `console_sets.json` |
| `test_console_sync.py` | `core/console_sync.py` with a stand-in launcher: discovery, handing over unlocks, taking sets, dry runs, bad requests |
| `test_saves.py` | `core/saves.py`, the PC's copy of the saves: the three-way plan (sync and back-up-only), history kept and pruned, restores, damaged uploads, a save changed by hand in the folder |
| `test_save_session.py` | `core/save_session.py` over loopback TCP with a stand-in launcher: the plan, uploads, downloads, history, restores, the summary, bad requests, save backups off |
| `test_save_sync.py` | The launcher's save sync (`launcher/source/savesync.c`, `sync.c`, `settings.c`) built for the PC against DSiRPC on loopback: a DSi and a 3DS sharing saves, the two-stage check, conflicts both ways, restores, back-up-only mode, exclusions, a swap that didn't finish, the settings |
| `test_dsirpc_client.py` | `core/dsirpc_client.py` against the fake DSi: finding it, reads split to fit, refusals, lost and late replies, the capture, pushed unlocks, the checker's reports, `watch()` |
| `test_bw_parser.py` | `core/bw_parser.py` on a made-up Black/White RAM image: trainer, encrypted party, field, battles, the Continue menu, the quick battle and field reads, the gait |
| `test_hub.py` | `core/hub.py` against the fake DSi in real time: Black/White end to end, the gait in the field, and the RetroAchievements side with and without the console's checker |
| `test_frame_check.py` | `tools/frame_check.py`: its analysis, arguments, logs, capture and counter search |
| `test_launcher_ini.py` | The launcher's `nds-bootstrap.ini` handling (`launcher/source/bootstrap_ini.c`): the game, its save (TWiLight's save places and slots), the rest of TWiLight's ini kept as it was, and DS mode for DSi-enhanced games every time (without it, a 3DS ran Pokémon Black with none of DSiRPC) |

`helpers/` has the shared pieces: the simulated puzzle game and its sets
(`puzzle_game.py`, `gen_set.py`), the Black/White RAM image (`bw_fake.py`),
the fake DSi (`fake_dsi.py`) and the C build (`cbuild.py`). `c/` has the C
harnesses: the console's code is built for the PC with gcc, with stand-ins
for the hardware (`c/stubs/`) and AddressSanitizer and UBSan on, so a bad
read or write in it fails a test instead of passing by luck.

## Running them

From the repo root, once:

```
python -m pip install -r tests/requirements.txt
```

The checker tests need the rcheevos library with DSiRPC's `dsirpc_offline.c`
built in. Windows has it (`third_party/rcheevos/rcheevos.dll`); on Linux,
build `librcheevos.so` as [its README](../third_party/rcheevos/README.md)
says. Then:

```
python -m pytest
```

Without the ones that run against the fake DSi in real time (a minute or so):

```
python -m pytest -m "not realtime"
```

One file, or one test:

```
python -m pytest tests/test_offline_checker.py -k nullwait
```

The C harnesses need Linux and gcc (WSL works); elsewhere they're skipped,
and so are the fake DSi's tests where `127.0.0.2` doesn't exist (macOS:
`sudo ifconfig lo0 alias 127.0.0.2`). The checker library's tests load it
into Python, so they get AddressSanitizer only when its runtime is loaded
first, as GitHub's second step does:

```
LD_PRELOAD=$(gcc -print-file-name=libasan.so) ASAN_OPTIONS=detect_leaks=0 python -m pytest -p no:cacheprovider tests/test_checker_vm.py
```

On GitHub, `DSIRPC_TESTS_REQUIRE_ALL=1` makes a missing compiler or library
fail the run instead of skipping tests.
