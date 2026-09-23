# DSiRPC changes to nds-bootstrap

This folder is a copy of [DS-Homebrew/nds-bootstrap](https://github.com/DS-Homebrew/nds-bootstrap)
(GPLv3, see `LICENSE`) at upstream commit
`f5f9ea48` ("Update Title list.txt"), modified for DSiRPC. Everything else in
this folder is unchanged upstream code.

## Modified files

| File | Change |
|---|---|
| `retail/cardenginei/arm7/source/cardengine.c` | Includes `rpcprobe/probe_hook.h` and calls `Probe_VBlankTick()` from `myIrqHandlerVBlank` (not in the `ALTERNATIVE`/`TWLSDK` variants). Also fixes four compile errors in upstream's debug-only code (`fatTableCache`, `getBootFileCluster` arguments, `calledViaIPC`, `nocashMessage.h`). |
| `retail/common/source/my_fat.c`, `retail/common/source/my_sd.c` | Fix compile errors in upstream's debug-only code with GCC 14: `#include "nocashMessage.h"` (only when `DEBUG` is defined) and `(u32)` casts on the pointers passed to `dbg_hexa()` in `my_fat.c`. Non-debug builds are byte-identical. |
| `retail/cardenginei/arm7/Makefile` | Adds `source/rpcprobe` to `SOURCES`. Builds with `-Os` instead of `-O2` to stay inside the 61 KB ARM7 region. |
| `retail/bootloaderi/source/arm7/main.arm7.c` | `DSIRPC_KEEP_DSI_WIFI 1`: skips switching the Wi-Fi board to old DS mode, so the launcher's DSi-mode connection survives into the game. As a result, the game's own Wi-Fi doesn't work. |
| `retail/bootloaderi/source/arm7/patch_common.c` | `DSIRPC_PLATINUM_NO_WIRELESS_SEARCH 1`: for Pokémon Platinum USA Rev 1 (`CPUE`, rev 1) only, and only if the expected instructions are found. It makes `CommManager_InitializeSearchParty` (`0x02037D48`) return immediately and `CommManager_GetAvailableConnections` (`0x02037DA0`) return 0. This removes the "A communication error has occurred" screen after Continue. |

## Added files

`retail/cardenginei/arm7/source/rpcprobe/`, the in-game side of DSiRPC:

| File | Role |
|---|---|
| `probe_hook.c/.h` | VBlank state machine: load `/RPCHAND.TXT`, probe the chip, broadcast hellos, service requests |
| `twl_wifi.c/.h` | Minimal CMD52 SDIO access to the DSi's Atheros chip (cut down from BlocksDS DSWiFi, MIT) |
| `probe_req.c/.h` | Answers memory requests and ARP, counts EAPOL |
| `probe_net.c/.h` | Builds LLC/SNAP + IPv4 + UDP frames for the (broadcast) hellos |
| `rpcprobe_config.c/.h` | Reads `/RPCHAND.TXT` (written by the launcher); defines the UDP port, 4244 |
| `rpcprobe_build.h` | `RPCPROBE_REQUESTS` switch (0 = hello packets only) |
| `DEBUGGING.md`, `TWL_RX_NOTES.md` | Debugging guide and chip notes |

## Updating to a newer nds-bootstrap

Copy the `rpcprobe/` folder over, then re-apply the changes to the six
modified files by hand. They're small; to see them exactly, diff each file
against upstream commit `f5f9ea48`. Before trusting a new upstream version, check that
the Platinum patch's instruction check still matches and that
`cardenginei_arm7` still links (it has a fixed-size region).
