# DSiRPC changes to nds-bootstrap

This folder is a copy of [DS-Homebrew/nds-bootstrap](https://github.com/DS-Homebrew/nds-bootstrap)
(GPLv3, see `LICENSE`) at upstream commit
`f5f9ea48` ("Update Title list.txt"), modified for DSiRPC. Everything else in
this folder is unchanged upstream code.

## Modified files

| File | Change |
|---|---|
| `retail/cardenginei/arm9/source/cardengine.c` | `myIrqHandlerIPC` calls `dsirpcWatchService()` (the ARM9 half of the per-frame capture: puts its VBlank hook in when rpcprobe rings), except in the DLDI, GSDD and TWLSDK variants. |
| `retail/cardenginei/arm9/source/misc.c` | `reset()` calls `dsirpcWatchReset()`, so a soft reset frees the per-frame capture's VBlank hooks for the reloaded game (same variants). |
| `retail/cardenginei/arm7/source/cardengine.c` | Includes `rpcprobe/probe_hook.h` and calls `Probe_VBlankTick(ndsHeader, readOngoing ? NULL : &saveMutex)` from `myIrqHandlerVBlank`, and `Probe_HaltTick(&saveMutex)` at the end of `runCardEngineCheckHalt()` (the swiHalt hook, outside interrupts), which saves the achievement checker's unlocks to the SD card while it holds `saveMutex` (not in the `ALTERNATIVE`/`TWLSDK` variants). Also fixes four compile errors in upstream's debug-only code (`fatTableCache`, `getBootFileCluster` arguments, `calledViaIPC`, `nocashMessage.h`). In the same variants, `cardReadLED()` returns at once: the ROM read LED setting's LED is the achievement LED instead (`rpcprobe/probe_led.c`). |
| `retail/cardenginei/arm7/source/inGameMenu.c` | Includes `rpcprobe/probe_hook.h`. `inGameMenu()` first calls `Probe_MenuOpened()` (the achievements unlocked so far count as seen, so the achievement LED stops, and the menu can show them), calls `Probe_LidClosed()` right before the menu's own `swiSleep()` (the lid closing with the menu open on a DSi), so the DSi doesn't sleep with the Wi-Fi chip still connected, which switches it off, and `Probe_MenuClosed()` before resetting or quitting the game (none of them in the `ALTERNATIVE`/`TWLSDK` variants). |
| `retail/cardenginei/arm9_igm/source/inGameMenu.c`, `inGameMenu.h` | DSiRPC's achievements (`dsirpc_ach.c`, below): `MENU_ACHIEVEMENTS`, `Ach_Open()` when the menu opens and an "Achievements" item when there's a list, `Ach_DrawMain()` at the end of `drawMainMenu()`, `Ach_Screen()` for the item; `menuItems` has room for 9. Not in the B4DS builds, which compile the same source. |
| `retail/common/source/my_fat.c`, `retail/common/source/my_sd.c` | Fix compile errors in upstream's debug-only code with GCC 14: `#include "nocashMessage.h"` (only when `DEBUG` is defined) and `(u32)` casts on the pointers passed to `dbg_hexa()` in `my_fat.c`. Non-debug builds are byte-identical. |
| `retail/cardenginei/arm7/Makefile` | Adds `source/rpcprobe` to `SOURCES`. Builds with `-Os` instead of `-O2` to stay inside the 61 KB ARM7 region. |
| `retail/bootloaderi/source/arm7/main.arm7.c` | `DSIRPC_KEEP_DSI_WIFI 1`: skips switching the Wi-Fi board to old DS mode, so the launcher's DSi-mode connection survives into the game. As a result, the game's own Wi-Fi doesn't work. Also, `romLocationAdjust()` skips the achievement checker's memory (`DSIRPC_ACH_LOCATION`, below), so the ROM cache and ROM-in-RAM loading never use it, and `isROMLoadableInRAM()`'s limit is `DSIRPC_ACH_SIZE` smaller to make up for it. |
| `retail/common/include/locations.h` | Adds `DSIRPC_ACH_LOCATION` (`0x0CFB0000`) and `DSIRPC_ACH_SIZE` (`0x40000`): main RAM for the in-game achievement checker's set and state, taken from the ROM cache's area. |
| `retail/bootloaderi/source/arm7/patch_common.c` | `DSIRPC_PLATINUM_NO_WIRELESS_SEARCH 1`: for Pokémon Platinum USA Rev 1 (`CPUE`, rev 1) only, and only if the expected instructions are found. It makes `CommManager_InitializeSearchParty` (`0x02037D48`) return immediately and `CommManager_GetAvailableConnections` (`0x02037DA0`) return 0. This removes the "A communication error has occurred" screen after Continue. |

## Added files

`retail/cardenginei/arm7/source/rpcprobe/`, the in-game side of DSiRPC:

| File | Role |
|---|---|
| `probe_hook.c/.h` | VBlank state machine: load `/RPCHAND.TXT`, probe the chip, broadcast hellos (with the game's code, ROM version and header CRC), service requests; `Probe_HaltTick()` saves the checker's unlocks (and the VBlank does, only if the swiHalt hook never runs); on a DSi, the lid closing turns the Wi-Fi off for the rest of the game (`Probe_LidClosed()`: a "DSiRPC lid" packet, the chip disconnected, its power cut); drives the achievement LED |
| `twl_wifi.c/.h` | Minimal SDIO access to the DSi's Atheros chip (cut down from BlocksDS DSWiFi, MIT): CMD53 block transfers for sending and receiving frames, CMD52 for register reads (and as the fallback each direction switches to by itself if CMD53 fails); `TwlWifi_Shutdown()` disconnects the chip and turns its interrupts off when the lid closes |
| `probe_led.c/.h` | The DSi's LEDs through the BPTWL chip (I2C): the achievement LED (the ROM read LED setting's LED pulses while achievements unlocked this game haven't been seen in the in-game menu), and the Wi-Fi chip's SDIO power cut when the lid closes |
| `probe_req.c/.h` | Answers memory requests (`'R'`) and ARP, hands `'W'`/`'F'` to `probe_watch.c`, counts EAPOL |
| `probe_watch.c/.h` | Per-frame capture: up to 8 watched values recorded every VBlank into a 2 KB ring, drained by the PC; records the ARM9 half's snapshot of them and reads main RAM itself when there's none |
| `probe_net.c/.h` | Builds LLC/SNAP + IPv4 + UDP frames for the (broadcast) hellos |
| `rpcprobe_config.c/.h` | Reads `/RPCHAND.TXT` (written by the launcher; `time=` is the console's clock, which dates offline unlocks); defines the UDP port, 4244 |
| `probe_ach.c/.h` | Offline play's achievement checker: loads `/RPCSET.BIN` (from the launcher) and `/RPCUNLK.BIN` on the first VBlank, checks the set's CRC, runs it in a time budget every VBlank, saves each unlock into its own `/RPCUNLK.BIN` slot (from the swiHalt hook), and reports with a "DSiRPC ach" packet after each hello; marks the console's unlocks in a version 3 set's achievement list and keeps the anchor the in-game menu reads (`dsirpc_ach_menu.h`); dates each unlock by the console's clock (`clock.c`'s `rtcGetTimeAndDate()`, only while the game isn't using the clock) |
| `probe_ach_vm.c/.h` | The checker's interpreter, a port of rcheevos 12.5's evaluation without floating point, for the program DSiRPC builds with rcheevos (its `third_party/rcheevos/dsirpc_offline.c`) |
| `rpcprobe_build.h` | Build switches: `RPCPROBE_REQUESTS` (0 = hello packets only), `RPCPROBE_RX_CMD53` / `RPCPROBE_TX_CMD53` (0 = CMD52 only for that direction), how often a hello still goes out with CMD52, the per-VBlank receive limits, and the achievement checker's `RPCPROBE_ACH` (0 = off), time budget and `RPCPROBE_ACH_SAVE_FALLBACK` |
| `DEBUGGING.md`, `TWL_RX_NOTES.md` | Debugging guide and chip notes |

Also added, outside `rpcprobe/`:

| File | Role |
|---|---|
| `retail/cardenginei/arm9/source/dsirpc_watch.c` | The ARM9 half of the per-frame capture: a hook in front of the game's VBlank interrupt handler (entry 0 of its interrupt table) snapshots the watched values (reading through the ARM9's cache) at the start of every VBlank into the shared block and writes them back to RAM. The hook goes in, or back in, when rpcprobe rings. Compiled out of the DLDI, GSDD and TWLSDK variants. |
| `retail/common/include/dsirpc_watch_block.h` | The 288-byte block both halves share (the list and four numbered snapshots), split by cache line between the CPU that writes it |
| `retail/cardenginei/arm9_igm/source/dsirpc_ach.c`, `dsirpc_ach.h` | The in-game menu's achievements: on its main screen, the unlocks new since it last opened and how many are earned; the Achievements screen, every achievement of the game, earned ones first (newest first, with when), with the highlighted one's description. Reads the set's list and the anchor through the MPU change the RAM viewer uses, and only from an anchor the ARM7 marked open. Compiled out of the B4DS builds. |
| `retail/common/include/dsirpc_ach_menu.h` | What `probe_ach.c` keeps for the menu in `DSIRPC_ACH_LOCATION`: the anchor (in the RAM copy of the set header's bytes 40-63) and the list's layout |

## Updating to a newer nds-bootstrap

Copy the `rpcprobe/` folder over, then re-apply the changes to the seven
modified files by hand. They're small; to see them exactly, diff each file
against upstream commit `f5f9ea48`. Before trusting a new upstream version, check that
the Platinum patch's instruction check still matches, that
`cardenginei_arm7` still links (it has a fixed-size region), and that
nothing new in nds-bootstrap uses `DSIRPC_ACH_LOCATION`'s 256 KB.
