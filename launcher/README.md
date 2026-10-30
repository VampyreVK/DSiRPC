# DSiRPC launcher

A small BlocksDS app that connects the DSi to Wi-Fi in **DSi mode**, then
starts our nds-bootstrap build with the game you pick, without
disconnecting, so the game side can keep using the connection.

It connects with the WPA2 settings saved in DSi connection slots 4-6 using
BlocksDS + DSWiFi (MIT licensed), and no Wi-Fi password is stored in any file.
Once the game is running, the Wi-Fi chip does the WPA2 encryption itself.

The top screen shows DSiRPC's pixel DSi, as on the desktop app's waiting
screen (`source/topscreen.c`): its Wi-Fi sign lights up arc by arc while the
launcher connects, green once it's connected, red if it can't, dark offline.
The bottom screen has two looks ([below](#the-modern-look)): the modern one
(the default) draws panels, tiles and the games' icons; the classic one is
the text console.

## What it does

1. Connects with the saved Wi-Fi settings in DSi mode. It tries up to 3
   times: a try fails if it can't connect within 30 s, or if no IPv4 address
   comes from DHCP within 10 s after that (DSWiFi can say "Associated"
   before DHCP has answered). **B** skips it, and **START** when it can't
   connect, for [offline play](#offline-play).
2. Shows the console's IP, gateway and MAC addresses (and DSiRPC's, once
   it's found, when the main screen is drawn again).
3. Writes `/RPCHAND.TXT` (`mode=dsi`, `ip=`, `gateway=`, `mask=`, `mac=`,
   `time=`, then `end`) for the in-game side. The name has to be 8.3, because
   nds-bootstrap's ARM7 file lookup only matches short names. `time=` is the
   console's clock in seconds since 2000 (local time); the in-game side reads
   the clock itself to date unlocks, and only falls back to `time=` plus the
   VBlanks since when it can't.
4. Syncs with DSiRPC, if it's running ([below](#the-sync-with-dsirpc)),
   then, if DSiRPC has other versions of the launcher or nds-bootstrap,
   offers them ([Updates](#updates)).
5. **START:** pick a game. A file browser opens in `sd:/roms/nds`, or in the
   launcher's own folder if there's no such folder (**A** opens a folder or
   picks the `.nds`, **B** goes up a folder, **START** picks the game last
   started from the launcher, **SELECT** goes back). The launcher then:
   - finds our nds-bootstrap build next to itself: `nds-bootstrap-dsirpc.nds`,
     or the only `nds-bootstrap*.nds` in that folder. If there's neither, it
     asks you to pick it with the same browser;
   - points `sd:/_nds/nds-bootstrap.ini` at the game (below), and remembers
     it for **START** in the browser (`LAST_GAME` in `launcher.ini`);
   - syncs with DSiRPC again, naming the game, so DSiRPC can send its set;
   - copies the game's set to `sd:/RPCSET.BIN` (or deletes that file if
     there's no set), makes sure `sd:/RPCUNLK.BIN` is there, and rewrites
     `RPCHAND.TXT` with the current time;
   - starts nds-bootstrap directly, still connected ([CHAINLOAD.md](CHAINLOAD.md)).

   **SELECT:** disconnect cleanly, then exit.
   **X:** exit without disconnecting, back to your menu (the old way: then
   start our nds-bootstrap build from there). X doesn't put a set in
   `RPCSET.BIN`, so the console's achievement checker and the in-game
   menu's list only work then if the last game started with START was the
   same one.
   **Y:** the [save sync](#the-save-sync). **L+R:** the
   [settings](#settings).

### The save sync

Y lists every game in `sd:/roms/nds` (subfolders too; the whole SD card if
there's no such folder) with its saves, found the way TWiLight Menu++ keeps
them: in a `saves` folder next to the game, in `sd:/roms/nds/saves`, next to
the game, or in `sd:/_nds/TWiLightMenu/saves`, as `.sav` and `.sav1` to
`.sav9`. A save no game is named after (a renamed backup, say) is left
alone. Each save is named to DSiRPC by the game's code and its ROM header's
CRC, so the same game shares its saves between consoles whatever its file is
called there.

`saves.idx` in the launcher's folder has each save's size, time and CRC32
as last seen, and its CRC at its last sync (or at the last plan that found
it in sync with the PC). Only a save whose size or time differs is read
again (for its CRC); that also tells a save nds-bootstrap only touched (it
updates a save's time whenever it starts the game) from one that changed.
The main screen counts the changed ones at startup.

DSiRPC (`core/saves.py`) compares each save three ways (the console's now,
the PC's live save, and what the console had at its last sync: its own
`saves.idx` says, or else what DSiRPC remembers it sent or took) and
answers with a plan: back up, take the newer one (and whose it is), ask
(changed on both), or nothing. A save written after the PC's live one (by
the consoles' clocks) is never replaced without asking: whatever the plan
says, the launcher makes a download over it a conflict. The launcher shows it, with the console each
save came from, and carries out what you pick, one request per connection
(`core/save_session.py` describes the exchange). An upload carries the
save's time, which dates DSiRPC's copy; DSiRPC keeps it as one of that
console's backups, next to the live save. A download goes to a
`.tmp` file, is checked against its CRC, then swapped in, with the old save
kept as `.bak` until that's done (a scan puts a `.bak` back if the console
went off in between). A console's save always goes to the PC before
anything replaces it. A save goes through memory both ways, so the SD card
and the Wi-Fi are never busy at once (reading the SD card while the Wi-Fi
sent damaged a few blocks in a hundred on a 3DS): one going out is read
whole, twice, until both reads agree, before it's sent; one coming in is
received whole, then written and read back. An exchange that fails on the
way (the network, or DSiRPC finding the save damaged or unable to store it)
is tried again, up to 3 times, and the screen says so. An upload's CRC is
read from the save as it goes,
since `saves.idx` can be out of date (a save written in place with its time
unchanged), and if a save the list called unchanged turns out to have
changed, a download over it stops (it's on the PC by then) for you to look
again: it's a conflict now.

### Settings

L+R opens them; they're kept in `launcher.ini` next to the launcher:

- `DSIRPC_IP`: DSiRPC's address, or empty to ask for it with a broadcast.
  With an address, the syncs ask there only.
- `SAVE_MODE`: `sync` (back up, and take newer saves from the PC) or
  `backup` (only back up; DSiRPC keeps those in history and never offers
  them to the other consoles).
- `AUTO_UPDATE`: `on` (ask DSiRPC for [updates](#updates) as the launcher
  starts) or `off`.
- `LOOK`: `modern` or `classic` ([below](#the-modern-look)). It changes as
  soon as it's picked on the settings screen.
- `SOUNDS`: `on` or `off`, the modern look's menu sounds (the classic look
  has none, so it has no Sounds row either).
- `GAME_SORT`: `recent`, `name` or `favorites`, the modern game list's order
  (L/R there, not on the settings screen).
- `LAST_GAME`: the game last started from the launcher, for **START** on the
  main screen and in the game browser (not on the settings screen).

### The modern look

`source/ui.c` draws the bottom screen as an 8-bit bitmap (BG3 in mode 5, 64
KB into VRAM C, above the text console's font and map, which stay where
`consoleDemoInit()` put them for the classic look): the frame is drawn in
memory and the rows that changed are copied over (VRAM takes no 8-bit
writes), the text is the console's own 8x8 font with each letter as wide as
it is, and the colors are the desktop app's. The spinner on the
connecting screen's current step turns by palette, from a cothread, so it
keeps turning while the launcher works (the network code waits a frame at a
time). The menu sounds are short samples made at startup (soft sine notes
that fade), so they end by themselves.

The screens are the classic ones' with the same keys, drawn differently,
plus:

- **Connecting:** a checklist (Wi-Fi, IP address, DSiRPC, Achievements),
  the update's card under it (`source/update.c`), and a card when it can't
  connect.
- **The main screen:** four tiles, Play, Saves (with how many changed),
  Settings and Exit, picked with the D-pad and A or a tap. **START** starts
  the game last started (`LAST_GAME`) without the list.
- **The game list** (`source/picker.c`): the games in `sd:/roms/nds` and its
  folders (found as the save sync finds them), each with its banner icon at
  half size, its name and its achievements (earned / all, counted from its
  set's list and the unlocks waiting in `RPCUNLK.BIN`). **L**/**R** change
  the order, **Y** makes a favorite, **X** lists the achievements, with the
  one picked described on the top screen. `games.idx` keeps each game's
  name, publisher and code from its banner by the file's size and time, so
  only new or changed games are read, plus the favorites and when each game
  was last started from the launcher (written in the classic look too, when
  a game starts). If nds-bootstrap isn't next to the launcher, the classic
  file browser asks for it.
- **The top screen** (`top_modern()`): the bar has a status chip
  (Connecting, Connected, No Wi-Fi, Offline) and the battery icon (filled to
  the DSi's step: 100, 75, 50, 25 or 10%, a DS only high or low; cyan while
  charging), the DSi is drawn 3x with a note under it (which PC DSiRPC is
  on, or what went wrong), and the game list and save sync show the picked
  game's or save's details instead.
- **Playtimes** (`source/stats.c`): after its first sync, the launcher asks
  DSiRPC how long each game ran while it watched, with the PC's name and
  whether it's signed in to RetroAchievements and has Discord on
  ([DOCUMENTATION.md](../docs/DOCUMENTATION.md#playtimes-tcp-4245)), and
  keeps the answer in `stats.idx`, so the game list has it offline too.

### Updates

`source/update.c`, so a new build doesn't need the SD card taken out. After
the first sync, the launcher asks DSiRPC which console files it has (the
ones that came with it: `core/console_update.py` describes the exchange)
and compares them with its own file (`argv[0]`, or `dsirpc-launcher.nds`
in its folder) and nds-bootstrap's: a different size says so, else the
CRC32. `update.idx` in the launcher's folder keeps each file's CRC32 with
its size and time, so a file is only read when it changed (nds-bootstrap is
about 1.7 MB). A missing nds-bootstrap counts as different, and goes where
the launcher looks for it.

When one differs, the launcher says which, with DSiRPC's version: **A**
updates, **B** goes on without. Each file is downloaded to its name +
`.tmp`, its size and CRC32 and its `.nds` header's own CRC checked, then
read back from the SD card and checked again; if anything's off (or DSiRPC's
files changed in the meantime), the `.tmp` files go and nothing else
changes. With every file there, the launcher tells DSiRPC it's leaving,
turns the Wi-Fi off and swaps them in with no file open: each old file
becomes `.bak`, the `.tmp` takes its name, and if any of that fails every
file goes back as it was. Then the `.bak` files go, and **START** exits, to
start the new launcher from TWiLight Menu++. (It can replace its own file
while running: all of it is in memory.)

The exchange never changes, so this launcher can update from any later
DSiRPC, and it still finds a DSiRPC from another release (the syncs refuse
it, the update doesn't). DSiRPC offers nothing while **Console updates** is
off in its tray menu.

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
deletes) for every game it launches anyway.

A DSi-enhanced game (Pokémon Black and White, and later) is also set to run
in DS mode (`DSI_MODE = 0`), every time, even when the ini already names it:
DSiRPC's part of nds-bootstrap (the memory server, the achievement checker,
the in-game menu's achievements) only runs in DS mode, and TWiLight may have
left DSi mode on, which is also nds-bootstrap's default when the key is
missing. A DSi-exclusive game can only run in DSi mode, and a DS game
ignores the setting, so theirs stays as it is.
Everything else in the ini (language, CPU boost and so on) stays as TWiLight
last wrote it.

A game that has never been started from TWiLight has no save file yet, and
the launcher won't make one (the right size depends on the game), so it
says so and goes back: start that game once from TWiLight first.

## Offline play

Without Wi-Fi (**B** while connecting, or **START** when it couldn't), the
launcher turns Wi-Fi off and works the same way, minus the syncs.
`RPCHAND.TXT` then holds only `mode=offline`, `time=` and `end`; with no
`ip` or `mac`, the in-game side leaves the network alone. The keys are
**START** (pick a game) and **SELECT** (exit); in the modern look, the Saves
tile waits for DSiRPC.

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
1.5 s (or sends it to the address in its settings). If DSiRPC answers, the
launcher connects to it over TCP (the same port) and sends the game being
started (if any), the stamp of every set it
has, and `RPCUNLK.BIN` as it is. DSiRPC answers with how many unlocks it
took and the sets that are new or changed. When DSiRPC took as many unlocks
as the launcher counted, the launcher zeroes them in the file; otherwise it
keeps them for next time. Each set is written to `CODE.TMP` first, then
renamed, so a set that doesn't arrive whole never replaces the old one.

**B** skips the sync at any point. Nothing is lost: unlocks stay on the SD
card until DSiRPC has them.

Once it has found DSiRPC, the launcher sends it `DSiRPC here` (and the
console model) every 5 seconds while it waits for a key, and `DSiRPC bye`
when it exits with **SELECT** or **X**, so DSiRPC stops showing the console
as connected once the launcher's gone (`sync_frame()`, `sync_bye()`).

## Build

From PowerShell, in the repo root:

```
docker run --rm -v "C:\Projects\DSiRPC\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
```

The output is `dsirpc-launcher.nds`. The same command first builds the loader
in `loader/` (it ends up inside the launcher). Copy the launcher to the SD
card next to our nds-bootstrap build (`nds-bootstrap-dsirpc.nds`), for example
both in `sd:/DSiRPC/` as in the release download, and start it in DSi mode.

In the DSi's menus (and TWiLight Menu++) it shows as "DSiRPC / RPC & RA
Tracking / VampyreVK" with an animated icon: the pixel DSi from DSiRPC's
waiting screen looking for a connection (`icon.gif`, made by
`tools/make_pixel_dsi.py`; BlocksDS's ndstool turns a GIF with several
frames into a DSi animated icon, up to 8 frames of 16 colours).

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
| `source/main.c` | Connecting (with the retries), the results screen and the keys; the modern look's checklist, main screen and starting screen |
| `source/topscreen.c` | The top screen: the pixel DSi and its Wi-Fi sign, animated from a cothread; the modern look's bar (status chip, battery), note and details |
| `source/ui.c` | The modern look's drawing: the bitmap, text, icons, banner icons, panels, key hints, the spinner, taps and sounds |
| `source/picker.c` | The modern look's game list (`games.idx`), and each game's achievements |
| `source/stats.c` | DSiRPC's playtimes, in `stats.idx` (tested on a PC against DSiRPC: `tests/test_playtime.py`) |
| `source/browser.c` | The file browser (START: the last game) |
| `source/bootstrap_ini.c` | Pointing `nds-bootstrap.ini` at the game, finding its save, DS mode for DSi-enhanced games (tested on a PC: `tests/test_launcher_ini.py`) |
| `source/sync.c` | Offline play: the sync with DSiRPC, the sets and the unlock file; finding DSiRPC (broadcast or the address in the settings) |
| `source/savesync.c` | The save sync's work: finding the saves, `saves.idx`, the exchange with DSiRPC, safe downloads (tested on a PC against DSiRPC: `tests/test_save_sync.py`) |
| `source/saveui.c` | The save sync's screens, in both looks: the list, conflicts, older versions, progress |
| `source/settings.c` | `launcher.ini` (and the last game) and the settings screen, in both looks |
| `source/update.c` | Updates from DSiRPC: the check, `update.idx`, safe downloads, the swap and its screens (tested on a PC against DSiRPC: `tests/test_console_update.py`) |
| `source/chainload.c` | Starting nds-bootstrap without going back to the menu |
| `source/loader_blobs.s` | Embeds the two files built in `loader/` |
| `loader/` | The bootstub and loader `chainload.c` installs ([loader/README.md](loader/README.md)) |
| `icon.gif` | The launcher's animated icon (made by `tools/make_pixel_dsi.py`, don't edit by hand) |

## License

The launcher's own code is MIT. `loader/` is GPLv2 or later (devkitPro's
nds-bootloader and NDS Homebrew Menu's bootstub), and the built
`dsirpc-launcher.nds` includes it, so the `.nds` as a whole is GPLv2 or later.

## Known limits

- If starting nds-bootstrap directly ever fails on a console, **X** still
  exits connected the old way.
- **TWiLight's per-game settings other than the save slot aren't applied**
  to a game picked here; the ini keeps the last launch's.
- **255 offline unlocks fit** in `RPCUNLK.BIN` before the launcher has to
  hand them to DSiRPC.
- **Group-key renewals aren't handled after the launcher exits.** DSWiFi's
  driver does them in software, and once the launcher exits nothing is
  running that driver. If hello packets stop at a suspiciously regular
  interval, check the router's WPA "group key update interval".
