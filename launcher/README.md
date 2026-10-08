# DSiRPC launcher

A small BlocksDS app that connects the DSi to Wi-Fi in **DSi mode**, then
starts our nds-bootstrap build with the game you pick, without
disconnecting, so the game side can keep using the connection. It grew out
of stage 4 of the project (the "handoff spike").

It connects with the WPA2 settings saved in DSi connection slots 4-6 using
BlocksDS + DSWiFi (MIT licensed), and no Wi-Fi password is stored in any file.
Once the game is running, the Wi-Fi chip does the WPA2 encryption itself.

## What it does

1. Connects with the saved Wi-Fi settings in DSi mode. It tries up to 3
   times: a try fails if it can't connect within 30 s, or if no IPv4 address
   comes from DHCP within 10 s after that. (DSWiFi also says "Associated"
   once an IPv6 address is ready, which can come before DHCP has answered;
   that was the `0.0.0.0` on the first try.) **B** skips it, and **START**
   when it can't connect, for [offline play](#offline-play).
2. Shows the IP, gateway, mask and the DSi's MAC.
3. Broadcasts 3 UDP test packets on port 4242, so no PC address is needed.
   `spikes/stage1-listen/pc/listener.py` can show them.
4. Writes `/RPCHAND.TXT` (`mode=dsi`, `ip=`, `gateway=`, `mask=`, `mac=`,
   `time=`, then `end`) for the in-game side. The name has to be 8.3, because
   nds-bootstrap's ARM7 file lookup only matches short names. `time=` is the
   console's clock in seconds since 2000 (local time), for dating unlocks.
5. Syncs with DSiRPC, if it's running ([below](#the-sync-with-dsirpc)).
6. **START:** pick a game. A file browser opens in the launcher's own folder
   (**A** opens a folder or picks the `.nds`, **B** goes up a folder,
   **START** goes back). The launcher then:
   - finds our nds-bootstrap build next to itself: `nds-bootstrap-dsirpc.nds`,
     or the only `nds-bootstrap*.nds` in that folder. If there's neither, it
     asks you to pick it with the same browser;
   - points `sd:/_nds/nds-bootstrap.ini` at the game (below);
   - syncs with DSiRPC again, naming the game, so DSiRPC can send its set;
   - copies the game's set to `sd:/RPCSET.BIN` (or deletes that file if
     there's no set), makes sure `sd:/RPCUNLK.BIN` is there, and rewrites
     `RPCHAND.TXT` with the current time;
   - starts nds-bootstrap directly, still connected ([CHAINLOAD.md](CHAINLOAD.md)).

   **SELECT:** disconnect cleanly, then exit.
   **Y:** exit without disconnecting, back to your menu (the old way: then
   start our nds-bootstrap build from there).

### The game, the ini and your save

nds-bootstrap boots whatever `sd:/_nds/nds-bootstrap.ini` names, the file
TWiLight Menu++ rewrites for every game it launches. If it already names the
game you picked, the launcher leaves it alone. Otherwise it sets:

- `NDS_PATH` to the game;
- `SAV_PATH` to the game's **existing** save file, found where TWiLight keeps
  saves: in a `saves` folder next to the game, next to the game, or in
  `sd:/_nds/TWiLightMenu/saves`, with the game's save slot (`.sav1` to `.sav9`)
  if you set one in TWiLight's per-game settings. Where the last game's save
  was tells it which place TWiLight is set to use;
- `MANUAL_PATH`, `HOMEBREW_ARG`, `DONOR_SDK_VER`, `PATCH_MPU_REGION` and
  `PATCH_MPU_SIZE` back to their defaults (they were the last game's);

and it deletes `sd:/_nds/nds-bootstrap/cheatData.bin` and `wideCheatData.bin`,
the last game's cheats and 3DS widescreen patch, which TWiLight rewrites (or
deletes) for every game it launches anyway. Everything else in the ini
(language, DSi mode, CPU boost and so on) stays as TWiLight last wrote it.

A game that has never been started from TWiLight has no save file yet, and
the launcher won't make one (the right size depends on the game), so it
says so and goes back: start that game once from TWiLight first.

## Offline play

Without Wi-Fi (**B** while connecting, or **START** when it couldn't), the
launcher turns Wi-Fi off and works the same way, minus the syncs.
`RPCHAND.TXT` then holds only `mode=offline`, `time=` and `end`; with no
`ip` or `mac`, the in-game side leaves the network alone. The keys are
**START** (pick a game) and **SELECT** (exit).

### The files on the SD card

| File | What |
|---|---|
| `sets/CODE.DRS` (next to the launcher) | Each game's achievement set, as DSiRPC sent it: the achievements left to unlock, already turned into the program the console's checker runs, and the list of all the game's achievements for nds-bootstrap's in-game menu |
| `sd:/RPCSET.BIN` | A copy of the started game's set, so the in-game side only needs a fixed name in the root; nds-bootstrap's checker (`rpcprobe/probe_ach.c`) runs it |
| `sd:/RPCUNLK.BIN` | Unlocks waiting for DSiRPC: 4096 bytes, made at full size by the launcher so the in-game side (`rpcprobe/probe_ach.c`) only ever writes into it, a 16-byte slot per unlock |

The formats are in DSiRPC's `core/offline.py` and in
[docs/DOCUMENTATION.md](../docs/DOCUMENTATION.md#offline-play-the-launchers-sync-tcpudp-4245).
The launcher never looks past a set's header (any version: it only needs the
game code and the stamp): DSiRPC builds them, and the in-game side reads
them.

### The sync with DSiRPC

`source/sync.c`. The launcher broadcasts `DSiRPC sync?` on UDP 4245 for
1.5 s. If DSiRPC answers, the launcher connects to it over TCP (the same
port) and sends the game being started (if any), the stamp of every set it
has, and `RPCUNLK.BIN` as it is. DSiRPC answers with how many unlocks it
took and the sets that are new or changed. When DSiRPC took as many unlocks
as the launcher counted, the launcher zeroes them in the file; otherwise it
keeps them for next time. Each set is written to `CODE.TMP` first, then
renamed, so a set that doesn't arrive whole never replaces the old one.

**B** skips the sync at any point. Nothing is lost: unlocks stay on the SD
card until DSiRPC has them.

## Build

From PowerShell, in the repo root:

```
docker run --rm -v "C:\Projects\DSiRPC\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
```

The output is `dsirpc-launcher.nds`. The same command first builds the loader
in `loader/` (it ends up inside the launcher). Copy the launcher to the SD
card next to our nds-bootstrap build (`nds-bootstrap-dsirpc.nds`), for example
both in `sd:/DSiRPC/` as in the release download, and start it in DSi mode.

## Checking the connection

`tools/hello_listener.py` (in the repo root's `tools/` folder) prints the
"DSiRPC hello" packets the in-game side broadcasts once a second (UDP 4244).
Quit DSiRPC first, since it uses the same port:

```
python tools\hello_listener.py
```

What each field means is in [docs/DOCUMENTATION.md, section 7](../docs/DOCUMENTATION.md#7-wire-protocol).

## Files

| File | What it is |
|---|---|
| `source/main.c` | Connecting (with the retries), the results screen and the keys |
| `source/browser.c` | The file browser |
| `source/bootstrap_ini.c` | Pointing `nds-bootstrap.ini` at the game, finding its save |
| `source/sync.c` | Offline play: the sync with DSiRPC, the sets and the unlock file |
| `source/chainload.c` | Starting nds-bootstrap without going back to the menu |
| `source/loader_blobs.s` | Embeds the two files built in `loader/` |
| `loader/` | The bootstub and loader `chainload.c` installs ([loader/README.md](loader/README.md)) |

## License

The launcher's own code is MIT. `loader/` is GPLv2 or later (devkitPro's
nds-bootloader and NDS Homebrew Menu's bootstub), and the built
`dsirpc-launcher.nds` includes it, so the `.nds` as a whole is GPLv2 or later.

## Known limits

- **Starting nds-bootstrap directly is new** and needs testing on hardware.
  If it doesn't work, **Y** still exits connected the old way.
- **TWiLight's per-game settings other than the save slot aren't applied**
  to a game picked here; the ini keeps the last launch's.
- **Saving offline unlocks is new.** The whole loop worked on hardware on
  2026-10-08 (a Tetris DS unlock made offline reached RetroAchievements at
  the next sync), with only a few games tried so far. 255 unlocks fit
  before the launcher has to hand them to DSiRPC.
- **Group-key renewals aren't handled after the launcher exits.** DSWiFi's
  driver does them in software, and once the launcher exits nothing is
  running that driver. If hello packets stop at a suspiciously regular
  interval, check the router's WPA "group key update interval".
