# DSiRPC Technical Documentation

How DSiRPC works, in detail: the parts, the network protocol, what was
changed in nds-bootstrap, the Pokémon Platinum memory map, the sprite
pipeline and troubleshooting. For installing and using DSiRPC, start with the
[README](../README.md); for running it from the source code, building the
console files and making releases, see [DEVELOPMENT.md](DEVELOPMENT.md).

## TL;DR

A custom build of nds-bootstrap runs a small memory server on the DSi's ARM7,
alongside the retail game. The launcher first connects the DSi to the WPA2
network saved in connection slots 4-6 and leaves the Wi-Fi chip connected.
nds-bootstrap then boots Platinum and keeps using that connection to answer
"read these addresses" requests from the PC over UDP. On the PC, Python reads
the game state (trainer, party, location, facing, battle), decrypts and
parses it, and pushes it to Discord as Rich Presence with animated sprites.
Pokémon Platinum (USA, Rev 1) gets the full presence; any other DS game shows
its name, box art and RetroAchievements rich presence. Every game's
RetroAchievements achievements are checked while you play (softcore unlocks
sent only if you choose so). On Windows, DSiRPC
runs as a tray icon (`DSiRPC.bat`) after a one-time `Setup.bat`.

---

## Contents

1. [How it works](#1-how-it-works)
2. [Requirements](#2-requirements)
3. [Setup details](#3-setup-details)
4. [Every-session flow](#4-every-session-flow)
5. [PC tools reference](#5-pc-tools-reference)
6. [Discord Rich Presence behaviour](#6-discord-rich-presence-behaviour)
7. [Wire protocol](#7-wire-protocol)
8. [DSi side: what was changed in nds-bootstrap](#8-dsi-side-what-was-changed-in-nds-bootstrap)
9. [Memory map (Platinum USA Rev 1)](#9-memory-map-platinum-usa-rev-1)
10. [Sprite assets pipeline](#10-sprite-assets-pipeline)
11. [Debugging and troubleshooting](#11-debugging-and-troubleshooting)
12. [Known limitations and next steps](#12-known-limitations-and-next-steps)
13. [Repository layout](#13-repository-layout)
14. [History and credits](#14-history-and-credits)

---

## 1. How it works

```
 DSi                                                      PC
 ---                                                      --
 dsirpc-launcher.nds (BlocksDS + DSWiFi)
   connects in DSi mode with the saved slot 4-6 WPA2
   settings (up to 3 tries), writes sd:/RPCHAND.TXT (IP, MAC,
   gateway), START = pick a game: points nds-bootstrap.ini at
   it and starts our nds-bootstrap, without disconnecting
        |
        v
 our nds-bootstrap build  --boots-->  Pokémon Platinum
   ARM7 VBlank hook (cardengine.c -> Probe_VBlankTick)
     first VBlank: read RPCHAND.TXT
     a few seconds later: probe the already-connected chip
     then every VBlank: read at most one packet
       ARP request for our IP  -> ARP reply
       'R' memory request      -> 'D' reply with bytes
     once a second: "DSiRPC hello" broadcast   ---UDP 4244--->  core/dsirpc_client.py (DSiClient)
                                              <--'R' request--  core/dsi_memory.py (DsiRam)
                                              ---'D' reply---->  core/parser.py (PlatinumParser)
                                                                 core/hub.py (StateHub), in dsirpc.py
                                                                    |                    |
                                                                    v                    v
                                                          Discord (pypresence)    overlay window
```

The design keeps the DSi side dumb. It only answers "give me N bytes at
address X", and all interpretation happens on the PC. Adding a new field to
the presence is a Python change, not a new DSi build.

### Why it's built this way

- **The Wi-Fi hangs off the DSi's Atheros chip in DSi mode.** The network
  the DSi can reach is WPA2 and only appears in connection slots 4-6. Slots
  4-6 only exist in DSi mode, and in DSi mode the chip does the WPA2
  encryption itself. The launcher does the association and the 4-way
  handshake with DSWiFi. The in-game side then only sends and receives
  already-framed packets through the chip over SDIO.
- **The board stays in DSi mode.** Stock nds-bootstrap switches the Wi-Fi
  board to old DS mode for DS games, which drops the association. Our build
  keeps DSi mode (`DSIRPC_KEEP_DSI_WIFI`). As a side effect, Platinum's own
  Wi-Fi doesn't work, and it couldn't reach a WPA2-only network anyway.
- **Platinum's main-menu wireless search is patched out.** With no DS-mode
  Wi-Fi, the title menu's search for Ranger, Wii and Mystery Gift
  connections failed with "A communication error has occurred". A small
  patch turns that search into a no-op.
- **The ARM7 VBlank hook is the only place code can live alongside a retail
  game.** The DS has no multitasking, and nds-bootstrap's cardengine already
  runs on ARM7 every VBlank for the whole game session.

---

## 2. Requirements

See the README's [What you need](../README.md#what-you-need). In short: a
modded DSi or 3DS with TWiLight Menu++, a WPA2 network saved in DSi
connection slot 4, 5 or 6 (on a DSi), Pokémon Platinum USA Rev 1 for the full
presence, a 64-bit Windows PC on the same network, and the Discord desktop
app. Running from the source code also needs Python 3, and building the
console files Docker ([DEVELOPMENT.md](DEVELOPMENT.md#2-requirements)).

---

## 3. Setup details

Installing from a release is in the README's [Install](../README.md#install);
running from the source code and the build commands are in
[DEVELOPMENT.md](DEVELOPMENT.md). This section covers the details. Release
downloads (the Windows zip and both `.nds` files) come from the GitHub Action
in `.github/workflows/build.yml` (see
[DEVELOPMENT.md, section 9](DEVELOPMENT.md#9-builds-and-releases)).

### 3.1 Build gotcha: make doesn't notice flag changes

If you only change `CFLAGS` in an nds-bootstrap Makefile (for example adding
or removing `-DDEBUG`), make reuses the old object files and you get a mixed
build. Once, this left debug logging half-enabled and caused a party-menu
black screen. Delete `nds-bootstrap\retail\cardenginei\arm7\build`, or touch
the sources, before rebuilding. From PowerShell:

```
Get-ChildItem C:\Projects\DSiRPC\nds-bootstrap\retail\cardenginei\arm7\source -Recurse -Include *.c,*.s | ForEach-Object { $_.LastWriteTime = Get-Date }
```

### 3.2 SD card files

| File | Where | Notes |
|---|---|---|
| `dsirpc-launcher.nds` | Next to our nds-bootstrap build: `sd:/DSiRPC/` in the release download's `SD card` folder | Must be started in **DSi mode** |
| Our `nds-bootstrap-nightly.nds`, renamed `nds-bootstrap-dsirpc.nds` | Next to the launcher | Kept separate from TWiLight's stock copy so the two don't get mixed up. The launcher looks for this name in its folder (or the only `nds-bootstrap*.nds` there), and asks for it otherwise |
| `RPCHAND.TXT` | SD root | Written by the launcher every time; don't edit it |
| `sets/CODE.DRS` | Next to the launcher | Achievement sets for offline play, from DSiRPC ([section 7](#offline-play-the-launchers-sync-tcpudp-4245)) |
| `RPCSET.BIN` | SD root | A copy of the started game's set (none if it has no set); the in-game achievement checker loads it on the game's first VBlank ([section 8](#the-achievement-checker-probe_achc)) |
| `RPCUNLK.BIN` | SD root | Unlocks from offline play waiting for DSiRPC; the launcher makes it (4096 bytes), the game writes a slot per unlock (nds-bootstrap's `rpcprobe/probe_ach.c`), and the launcher clears it once DSiRPC has them |

The launcher also edits TWiLight's `sd:/_nds/nds-bootstrap.ini` (`NDS_PATH`,
`SAV_PATH`, and the last game's per-game values) when you pick a game it
doesn't already name ([launcher/README.md](../launcher/README.md#the-game-the-ini-and-your-save)).
Apart from that there's no config file: the Wi-Fi settings come from the DSi's
own saved connections, and the in-game side broadcasts its hellos, so it
never needs the PC's IP. Replies to memory requests go back to whichever PC
asked. An `RPCPROBE.CFG` left over from an older version is ignored and can
be deleted (old ones can hold your Wi-Fi password).

`RPCHAND.TXT` is written by the launcher, for example:

```
mode=dsi
ip=192.168.2.195
gateway=192.168.2.1
mask=255.255.255.0
mac=00:23:CC:12:34:56
time=844387200
end
```

`time` is the console's clock (seconds since 2000-01-01, local time), for
dating unlocks in offline play. When the launcher plays offline, the file is
only `mode=offline`, `time=` and `end`: with no `ip` or `mac`, the in-game
side leaves the network alone. The file needs an 8.3 name because
nds-bootstrap's ARM7 file lookup only matches short names.

### 3.3 PC side

- A release download has its own Python in `python\` (Python's embeddable
  package with the packages from `requirements.txt`, see
  [DEVELOPMENT.md, section 9](DEVELOPMENT.md#the-windows-download)), so
  `Setup.bat` just runs `dsirpc.py setup` (section 5). From the source code,
  `Setup.bat` first makes the `.venv` and installs `requirements.txt`
  (pypresence 4.6 or later, pygame-ce, Pillow, pystray).
- Settings live in `dsirpc.cfg` (gitignored; `dsirpc.cfg.sample` lists them),
  which setup writes. An older `PokemonPlatinumRPC.cfg` is still read while
  there's no `dsirpc.cfg`, and its settings move over the first time
  anything is saved.
- The Discord application ID is `discord_client_id` (or `--client-id`). The
  bold "Playing/Competing in ..." name comes from the application's name in
  the Discord Developer Portal. For other games, `[discord_apps]` can name an
  application per game code and a `default` one (section 6). A release
  download's `defaults.cfg` holds the applications it comes with, used while
  `dsirpc.cfg` leaves them empty.
- Games with a RetroAchievements set in `ra/` get their achievements checked
  and their RA rich presence (section 6, "RetroAchievements"). Signed in
  (setup), DSiRPC downloads sets by itself; it can also copy them from
  RALibretro's `RACache` (`racache` and `auto_import` in `[ra]`), and
  `tools/ra_tool.py` adds them by hand. The rcheevos library that evaluates
  them is prebuilt in `third_party/rcheevos/` (Windows x64).
- With RetroAchievements signed in, `dsirpc.cfg` holds your login token
  (never the password): keep it to yourself.
- Allow Python through the Windows firewall for UDP on private networks:
  both `pythonw.exe` (the tray) and `python.exe` (the console and tools), in
  `python\` (a release download) or `.venv\Scripts\`.

### 3.4 Sprites on GitHub Pages

Discord loads the images from `https://vampyrevk.github.io/DSiRPC/Assets/...`,
so new or changed assets only show up after they are committed and pushed.
Until then, Discord shows an empty image slot. `Assets/` must stay at the
repo root, and `.nojekyll` makes Pages serve the files as they are. See
[section 10](#10-sprite-assets-pipeline).

---

## 4. Every-session flow

1. **Launcher (DSi mode).** Wait for `ASSOCIATED`. A try that can't connect
   within 30 s, or gets no IPv4 address within 10 s after associating, is
   retried, up to 3 tries. (DSWiFi reports "Associated" as soon as an IPv4
   *or IPv6* address is ready, so it could finish with `0.0.0.0` while DHCP
   was still going.) The screen shows the IP, gateway, mask and MAC. Three
   test packets are broadcast on UDP 4242, which
   `spikes/stage1-listen/pc/listener.py` can pick up. The launcher writes
   `RPCHAND.TXT`.
2. **START: pick the game.** A file browser opens in the launcher's folder
   (A opens or picks, B goes up a folder, START goes back). The launcher
   finds our nds-bootstrap next to itself, or asks for it with the same
   browser. Unless `sd:/_nds/nds-bootstrap.ini` already names the game, it
   sets `NDS_PATH` and `SAV_PATH` (the game's existing save, in whichever of
   TWiLight's save places it is, with its per-game save slot), resets the
   last game's manual, donor-SDK and MPU-patch values, and deletes the last
   game's cheat files. A game with no save yet has to be started from
   TWiLight once. Then it installs a bootstub and nds-bootloader and exits
   into them, which boots our nds-bootstrap with `argv[0]` set to its path,
   without disconnecting ([launcher/CHAINLOAD.md](../launcher/CHAINLOAD.md)).
3. **Or SELECT / Y.** SELECT disconnects cleanly and exits; use it when
   you're not going to play. Y exits connected, back to your menu, the
   two-step way: launching our nds-bootstrap build from there boots the game
   the ini names (the last one TWiLight or the launcher set up).
4. **In game.** On the first VBlank the ARM7 side reads `RPCHAND.TXT`.
   A couple of seconds later it probes the chip and starts serving. It sends a
   gratuitous ARP so the PC learns its MAC, then broadcasts one hello packet
   per second.
   If the board was ever found in old DS mode, it waits 15 seconds for the
   game to finish booting before switching it back, which delays the first
   hello.
5. **PC.** DSiRPC (the tray icon, or `dsirpc.py` in a console; it can be
   started before any of this) learns the DSi's IP from its first hello and
   waits as long as it takes; `tools/dsi_status.py` gives up after 15 s. On a
   network that drops broadcasts, pass the IP the launcher showed with
   `--dsi-ip`.

---

## 5. PC tools reference

All commands run from DSiRPC's folder, with the virtual environment's Python
(`.venv\Scripts\python.exe`; `Setup.bat` makes it) or, in a release download,
`python\python.exe`.

### `dsirpc.py` (DSiRPC itself)

One program, three ways to run it. Whichever way, it's the engine
(`app/engine.py`): the state hub (`core/hub.py`, the one thing talking to the
DSi), the Discord Rich Presence as a hub listener
(`rpc/presence_connector.py`) and, when it's open, the overlay window
(`overlay/app.py`).

| Mode | Started by | What |
|---|---|---|
| `tray` | `DSiRPC.bat` (pythonw, no console), Start with Windows | A tray icon; see below |
| `setup` | `Setup.bat` | The setup wizard; see below |
| `run` (default) | `python dsirpc.py` | In the console until Ctrl+C (or SIGTERM), logging what Discord shows; `--overlay` opens the window on the main thread, and closing it stops DSiRPC |

| Flag | Default | Meaning |
|---|---|---|
| `--overlay` | off | Also open the overlay window (run mode) |
| `--no-discord` | off | Show nothing on Discord |
| `--no-ra` | off | No RetroAchievements at all: no achievements, no downloads, nothing sent |
| `--dry-run` | off | Log the presence instead of sending it, and send nothing to RetroAchievements (no session, pings or unlocks) |
| `--client-id ID` | from `dsirpc.cfg` | Discord application ID for every game |
| `--interval S` | `5`, or `2` with the overlay | Seconds between reads. Discord accepts about one update per 5 s. |
| `--file ram_dump.bin` | - | Use a 4 MB RAM dump (for example from melonDS) instead of the DSi. With `--dry-run` (and no overlay) it prints the presence once and exits |
| `--game CODE` | - | With `--file`: the dump's game code, when it isn't Platinum (to try another game's presence) |
| `--demo`, `--name N` | off | The overlay's made-up scenes instead of the DSi (no Discord) |
| `--scale N`, `--chroma RRGGBB` | from `dsirpc.cfg` | Overlay window size and chroma key colour |
| `--dsi-ip IP` | auto | The IP the launcher showed. Skips waiting for a hello (needed only if your network drops broadcasts) |
| `--port N` | `4244` | UDP port. The DSi always uses 4244, so leave it |
| `-v` | off | Debug detail in the log |

It logs to `logs\dsirpc.log` (about 3 MB at most, in three files), and to
the console in run mode. Only one copy can run: a second one can't get UDP
port 4244 and says so (the tray with a message box). The same goes for the
tools below while DSiRPC runs.

The hub reads every 5 s while only Discord needs the data, and every 2 s
(with the battlers every 0.3 s in a battle, `DsiSource.fast_battles`) while
the overlay window is open. In between, about once a second
(`interval` in `[ra]`), it checks the running game's achievements, which
reads only the few values the set needs (usually one request). `logs\state.json` says what's running, refreshed
at least every 30 s, so setup can see the game while DSiRPC holds the port.
Changes to `dsirpc.cfg` (from setup, say) are picked up while it runs.

**The tray** (`app/tray.py`, pystray). The menu shows what's running, what
Discord shows and the RetroAchievements state (signed in or not, the game's
progress, or why there's no set), then **Discord presence**, **Console
icon** (a submenu with every picture in `Assets/Consoles`, plus "None", for
Discord's small image; section 6), **Overlay window** (also a left click on
the icon) and **Start with Windows** (`app/startup.py`: a
`DSiRPC` value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
that runs `pythonw dsirpc.py tray`; it shows in Task Manager's Startup apps),
then **Setup...** (opens setup in a console), **Open log**, **Open DSiRPC
folder** and **Quit**. The Discord and overlay choices are saved in
`dsirpc.cfg` (`[app]`). The icon is drawn in code (`make_icon()`): a little
DSi with a dot that's green while the game answers, amber while DSiRPC waits,
red when Discord can't be reached or there's no application ID. Windows
notifications say when the DSi connects, goes quiet and switches games, and
when an achievement unlocks.

**Setup** (`app/setup_wizard.py`). Every question shows the current value,
and Enter keeps it, so it's safe to run again:

1. Python packages: the version, each package in `requirements.txt`
   (offers `pip install -r requirements.txt` for missing ones) and the
   rcheevos library.
2. Discord: how to make an application, the application ID for Platinum
   (and the fallback), and one for other games (`[discord_apps] default`).
   IDs are checked to be 17-20 digits.
3. RetroAchievements (optional): signs in with your username and password
   (`login2`; the password is read without echo and only the token is
   kept), then asks whether to show what you play on your profile
   (`profile`) and, after explaining the limits, whether to send unlocks
   (`submit_unlocks`, off by default).
4. Your game files (signed in only): a folder of `.nds` files (`roms`).
5. Achievement sets: RALibretro's folder (`racache`, and whether to copy
   sets from it on its own, `auto_import`). Then, for the game the DSi runs
   now (it listens 10 s, or reads `logs\state.json` if DSiRPC holds the
   port) and any game code you type, it lists the possible sets: the one for
   your game file, RetroAchievements games whose title matches the game's
   (its header's, or GameTDB's for the game code),
   and RALibretro's cached sets; you can also search RetroAchievements by
   name. The one you pick is saved as `ra/<code>.json`.
6. Start with Windows.

The result is saved to `dsirpc.cfg`.

However it's started, DSiRPC behaves the same way:

- It waits for a hello from the DSi for as long as it takes.
- It connects to Discord only once there's something to show. If Discord
  isn't running, or is closed later, it keeps retrying and logs the error
  once.
- It only sends to Discord when the presence actually changes.
- After about 30 s without data (game closed, DSi off), it clears the
  presence, disconnects from Discord and goes back to waiting for a hello
  (unless `--dsi-ip` was given), so a new IP from the router is picked up.
- The timer shows the save's playtime. If that jumps by more than a minute
  (a soft reset, or loading another save), the timer is reset.
- Stopping it clears the presence before it exits.
- On any game other than Platinum it shows the simpler presence from
  section 6 instead, switching back and forth as the DSi's hellos report a
  different game.

The tools below are for testing and development; they're in `tools/` and
run from the repo root (`python tools\dsi_status.py`).

### `tools/dsi_status.py` (everything, human-readable)

Prints the trainer, badges, Pokédex, location, the three position sources,
raw facing, and the full party (with moves, nature, item, shiny and status).
It also prints the battle, the music ID and the DS clock. It shows values
that are still guesses too, which makes it the tool for checking whether a
new field holds up while playing.

| Flag | Meaning |
|---|---|
| `--watch S` | Re-read every S seconds |
| `--json` | Print the parsed dictionary as JSON |
| `--file ram_dump.bin` | Parse a RAM dump (offline testing) |
| `--dsi-ip`, `--port`, `--timeout` | As above |

A read of everything is about 3.3 KB, which took 0.7 s on hardware.

### The overlay window (`dsirpc.py --overlay`, the tray menu, `tools/dsirpc_overlay.py`)

A pygame window that draws a 256x192 canvas every frame and scales it up by
a whole number (nearest neighbour), for OBS Window Capture or a screen
share. It draws from the engine's state hub (`OverlayWindow` in
`overlay/app.py`), so it never talks to the DSi itself, and it runs next to
the Rich Presence. In the tray it runs on its own thread; closing it turns
the menu's checkmark off. `tools/dsirpc_overlay.py` is the old standalone
command (`dsirpc.py --overlay --no-discord`; `--discord` adds the presence).
Its keys are in the README ([Stream overlay window](../README.md#stream-overlay-window)),
its options in [DEVELOPMENT.md](DEVELOPMENT.md#7-command-line). The sprites
come from `Assets/`; a sprite that isn't there (a release download only has
`Assets/Consoles`) is downloaded from GitHub Pages on the loader thread the
first time it's needed and kept (`overlay/sprites.py`).
During a battle the hub reads only the battlers, about three times a
second, instead of the whole state every 2 s (see `DsiSource` in the module
table), so HP and moves show up quickly.

- **Party view:** location and playtime, six slots (animated sprite, name,
  gender, level, HP bar sliding to its new value, status tag, a sparkle for
  shinies), and a footer with your trainer facing and walking the way you do,
  badges and Pokédex counts.
- **Battle view:** shown while `battle.active`, with a bar-wipe transition.
  The background (`overlay/backdrop.py`) is drawn in code: the sky follows the
  DS clock (morning, day, evening, night with stars), with drifting clouds,
  hills and swaying grass. Caves, buildings and snowy areas get their own
  look, guessed from the location name, and the save's weather ID adds rain,
  storms, snow, sand, hail, ash or fog. Both Pokémon stand on their platform
  at the spot `process_diorama.py` uses (x=80, bottom y=126 of its canvas),
  foes facing left (the overworld GIFs face right, so they're mirrored). In
  a double battle both sides show two: the foe's first Pokémon on the right
  and yours on the left, as in the game, with two smaller HP boxes for yours
  (no HP numbers). A damaging move's target is whichever Pokémon on the
  other side loses HP; a move that hits both (Surf and the like) lands on
  both. They slide in at the start and on a switch. Each
  move either side uses shows as "X used MOVE!" with an animation in the
  move's type style (`overlay/effects.py`: flames, bubbles, leaves,
  lightning, ice shards, rocks, rings, wisps, claw streaks, hit sparks;
  status moves glow around the user), physical moves with a lunge; the
  target blinks and shakes when its HP drops, and a fainted one sinks into
  its platform. Moves are worked out from PP: a move whose PP went down
  since the last read was just used. The game takes the PP when a move
  starts but the HP only after its animation, often a read or two later, so
  a damaging move is held until its target's HP drops and then plays
  together with the hit. Status moves play right away; a damaging move whose
  target loses no HP within `MISS_AFTER_S` (5 s, in read time) plays anyway
  (a miss, Protect, a Substitute), and one aimed at a Pokémon that was
  replaced in between plays before the switch message. Things seen in the
  same read play one after another (`MOVE_GAP_MS` apart), and the HP box
  holds the old value until the hit lands. Held moves play in the order they
  happened: by the read they were seen in, and within one read a Pokémon
  that fainted goes first (it can't move after being knocked out), then
  higher move priority (`platinum_data.MOVE_PRIORITY`), then higher speed
  (with its stat stage and paralysis), then yours. A held damaging move is
  also over once a later move has been seen or either side has fainted or
  left, and its faint message follows its hit. The game's own last-move record (`B+0x527C`, so far
  checked on hardware for your side only) is only a backup, for moves PP can't show (Struggle,
  moves called by Metronome), and only after it has matched the PP twice.
  The message box shows the intro (from the battle music, the same kinds as
  in section 6), moves, switches and faints for a few seconds, and otherwise
  your Pokémon's moves, coloured by type with PP, the last one used
  highlighted and a tab on each damaging move with its type multiplier
  against the foe (the first foe in doubles) when it isn't 1: `X4`, `X2`,
  `X1/2`, `X1/4`, `X0`. That uses the foe's types and the decomp's type
  chart (`platinum_data.TYPE_CHART`, with Foresight lifting the Ghost
  immunities); abilities such as Levitate aren't counted. Stat changes and
  some conditions show as chips under each HP box (the box grows a row):
  `ATK↑2` in red, `SPE↓1` in blue, and `CNF`, `LOVE`, `SEED`, `CURSE`,
  `SUB`, `NGHT`. Conditions also get a looping marker on the Pokémon
  (`overlay/markers.py`): Z's for sleep, sparks for paralysis, bubbles for
  poison, flames for a burn, ice crystals and a blue tint when frozen,
  circling stars when confused, hearts when infatuated, sprouts for Leech
  Seed and a purple flame for a curse. In doubles, chips on your side make
  your boxes taller, and the upper one can then cover part of the foes'
  platform. Wild vs trainer comes from the parser's `wild` flag (see
  section 9), falling back to the music.
- **Other games:** a card with the game's title, its RetroAchievements rich
  presence (or a note that there's no set file), and its code, RA game ID
  and achievement count (`draw_other()`).
- **Waiting view:** while the hub is offline.
- **Banners:** for the hub's events (DSi connected or lost, another game,
  shiny encounter, level-up, fainted, badge, new Pokédex catch).

Sprites come from `Assets/` and are converted in memory (`overlay/sprites.py`):
the 2x GIFs are halved to native pixels and un-mirrored where needed, and
the trainer sheets are halved and split by direction. Foe sprites use the
`Pokemon-Overworld` GIFs (the same animated front sprites without a
diorama). Cutting the diorama out of `Pokemon-Battle-NormalLarge` is only a
fallback, because GIF palette quantization changes the grass colours for
some sprites. Text uses a pixel font drawn in code (`overlay/font.py`), and
the palette is `THEME` in `overlay/ui.py`.

### `core/dsirpc_client.py` (raw memory reads)

```
.venv\Scripts\python.exe core\dsirpc_client.py --read 0x02000BBC:8 0x02101D40:4 --repeat 10 --interval 0.5
```

The default read is `0x02000BBC:8`, the SDK marker in Platinum's code. It
should print `21 06 C0 DE DE C0 06 21`, which proves the reads come from real
game memory. `-v` also prints hellos and timeouts. Large reads are split
automatically.

Link check (close the other PC tools first, they share the port):

```
.venv\Scripts\python.exe core\dsirpc_client.py --stats 60
```

It sends a small read every 0.25 s for 60 s and prints how many came back
and how fast, next to the DSi's own counters from the hellos: how many of
those requests the game side answered (`req`), how many frames it drained
in total (`rx`, other devices' broadcasts included) and how far apart the
hellos were. Requests the DSi never answered were dropped inside its wifi
chip (unicast frames lost over the air are resent by the wifi itself), which
happens when the in-game side can't drain the chip as fast as frames arrive.
With CMD53 sending it also splits the `vb=` values: every 10th hello still
goes out with CMD52, so the hello after it shows that slow tick (about 76);
the others show what everything else costs.

### `tools/frame_check.py` (per-frame capture check)

```
.venv\Scripts\python.exe tools\frame_check.py
```

Step 1 of RetroAchievements support: checks whether the per-frame capture
(see [section 7](#7-wire-protocol)) sees every frame. It says whether the
ARM9 half is there and its VBlank hook is in (`a9=` in the hellos), how many
records the ARM9 and the ARM7 read, and judges the ARM9's records on their
own; `--arm7-only` turns the ARM9 off for a run, to compare. On Platinum it watches
the game's own VBlank counter (`gSystem.vblankCounter`, `0x021BF6A8`) for
20 s. The game adds one to it after waiting for a VBlank, so it can go up by
at most one per frame: +1 (counted) and 0 (not counted: a 30 fps screen like
the overworld, or lag) are both normal, and an emulator sees the same. A jump
of 2 or more means the reads before it were late: by one frame, a race with
the game's own code at the start of VBlank or the ARM9's data cache; by more,
only the cache. It prints the counter's rate, the late reads and how late
they were. Play normally while it runs. `--seconds N` runs longer, and
`--save NAME` saves every record to `logs\NAME.csv` and the report to
`logs\NAME.txt` for a closer look (the `logs` folder is at the repo root,
and git ignores it). On another
game, pass a VBlank counter with `--watch ADDR:4`, or look for one with
`--find-counter ADDR:LEN` (it reads the range twice, 2 s apart, at about
10 KB/s, so keep the range small). Any extra `--watch` values are reported as
"changed on N frames".

### `tools/ra_tool.py` (RetroAchievements set files)

```
.venv\Scripts\python.exe tools\ra_tool.py add C:\RALibretro\RACache\Data\12711.json
```

Manages the RetroAchievements set files in `ra/` by hand (setup and DSiRPC
itself usually take care of them). A set file is the game data an RA
emulator downloads while you're logged in; RALibretro keeps it as
`RACache\Data\<RA game ID>.json` after you load the game once. Only `hash`
talks to RetroAchievements (one `gameid` request, no login).

| Command | What it does |
|---|---|
| `add FILE` | Checks the file and copies it to `ra/<game code>.json`. The code is the game the DSi is running, or `--code CPUE`. `--force` replaces an existing file. |
| `list` | The set files in `ra/` |
| `info CODE` | Title, RA game ID, achievement and leaderboard counts, icon and box art URLs, and whether the rich presence script parses |
| `rp CODE` | Evaluates the rich presence once against the DSi (`--every 5` keeps going, `--file dump.bin` uses a RAM dump) and prints the text and how many values it read |
| `hash FILE` | A `.nds` file's game code and RetroAchievements hash, and which RA game that hash is |

`ra/games.txt` can also map a code to a file kept under its RA ID: a line
`IRBO 123` makes `IRBO` use `ra/123.json`. `add` without `--code`, and `rp`,
need the DSi's port, so quit DSiRPC first.

### `tools/hello_listener.py`

Prints hello packets (UDP 4244). This is the first thing to run when you
suspect the connection. See [section 7](#7-wire-protocol) for what the
numbers mean.

### Python modules

| Module | What it does |
|---|---|
| `core/dsirpc_client.py` | `DSiClient`: the UDP protocol client. It learns the DSi's IP from hellos, splits and batches reads, and retries. `game` is the running game from the hellos (code, ROM version, header CRC; `None` with older builds), `set_watch()` and `fetch_frames()` drive the per-frame capture, and `listen()` takes in hellos while nothing else is being sent. `AchReport` logs the console checker's reports (section 7). |
| `core/dsi_memory.py` | `DsiRam`: behaves like the 4 MB dump the parser expects (length and slicing), but fetches only the bytes that are read, in 64-byte blocks, batched per `prefetch()`. `connect()` waits up to 15 s for the DSi (used by `tools/dsi_status.py`; the hub uses `DSiClient` directly and waits indefinitely). `SparseRam` does the same with exact byte ranges (ranges under 16 bytes apart merged), for the scattered values of an achievement set. |
| `core/parser.py` | `PlatinumParser.parse()`: two prefetch batches (fixed addresses first, then everything hanging off the pointers), then decode |
| `core/platinum_data.py` | Name tables by game ID: species, moves, items, natures, 593 maps (in-game location name + map header name), badges, trainer sprites, music IDs, weather IDs (`WEATHER`), and each move's type, category and base PP (`MOVE_INFO`). Generated from the pret/pokeplatinum decompilation. |
| `core/charmap.py` | Gen IV text decoding with `PokeGen4Charmap.txt` |
| `rpc/discord_client.py` | pypresence wrapper. `update()` takes `activity_type`, `party_size` and `name` (the game's name instead of the application's, pypresence 4.6+; older versions leave it out) and returns whether Discord accepted it. `close()` clears the activity and disconnects, and cleans up properly even if Discord was closed in the meantime. Repeated identical errors are logged once. |
| `utils/config.py` | `Config`: reads `dsirpc.cfg` (or the old `PokemonPlatinumRPC.cfg` while there's no `dsirpc.cfg`): `[connection]`, `[discord_apps]`, `[app]` (discord, overlay, overlay_scale, chroma, console_icon), `[ra]` (username, token, roms, profile, achievements, submit_unlocks, interval, racache, auto_import). `client_id_for(code, platinum)` picks the Discord application for a game (`[discord_apps]`, then its `default` for other games, then `discord_client_id`). `save()` writes every setting back, with comments. |
| `rpc/platinum_presence.py` | Platinum's presence (section 6): `build_presence()`, the sprite URLs, `playtime_start()` for the timer |
| `rpc/generic_presence.py` | The presence for any game without its own parser (section 6): `from_state()` / `build_presence()` lay it out, `cover_url()` finds GameTDB box art (checked once per game), `console_icons()` / `console_icon()` the pictures in `Assets/Consoles` |
| `core/other_game.py` | `OtherGame`: a game without its own parser while it runs. Returns the hub's state for it (`{'kind': 'other', 'title', 'ra_set', 'rich_presence', 'progress', ...}`) from the game's `RaGame`, and tells whether the DSi is still there (the RA reads, or the hellos) |
| `core/ra_game.py` | `RaGame`: a game's RetroAchievements side while it runs (Platinum too). Reads the header title (`match_titles` holds the GameTDB titles `RALink` used when there's none), finds the set (`ra/`, then `RALink`, then the RA cache), runs rcheevos with the rich presence and the achievements, `tick()` once a second, turns triggered achievements into `achievement` events, sends them through the link when allowed, and pings. `RaSettings` holds the `[ra]` choices |
| `core/ra_link.py` | `RALink`: the connection to RetroAchievements, on its own thread. `prepare()` (game ID by ROM hash, set file or title; download; session), `ping()`, `award()` (with the pending file and retries), `candidates()` and `download()` for setup. For offline play: `set_for_code()` (a game's set by code, downloaded if needed), `known_unlocks()` (from `startsession` and sent unlocks, kept in `ra/cache/unlocked.json`), `award_offline()`; `queue_offline()` keeps unlocks for when you're signed in |
| `core/ra_api.py` | `RAClient`: the `dorequest.php` requests (`login2`, `gameid`, `achievementsets`, `systemgames`, `startsession`, `ping`, `awardachievement`), encoded byte for byte like rcheevos, with DSiRPC's User-Agent |
| `core/ra_hash.py` | `nds_hash()`: RetroAchievements' hash of a DS game file (port of rcheevos' `rc_hash_nintendo_ds`), `RomIndex`: which file in a folder is which game code (`ra/cache/roms.json`) |
| `core/ra_set.py` | Loads a RetroAchievements set file (both of RA's formats) and finds one by game code in `ra/` |
| `core/game_titles.py` | DS game titles by game code from GameTDB's list (`dstdb.txt`, downloaded into `ra/cache/` and refreshed monthly): `titles(code, cache_dir)` gives the code's title, the same game's US and European titles, then `core/games.py`'s name, for title matching when the header can't be read |
| `core/ra_cache.py` | Finds sets in an RA emulator's cache: `data_dir()` (the emulator's folder, `RACache` or `RACache\Data`), `scan()` (DS/DSi sets only, cached by file time), `read_header()` (title and code from the header copy at `0x023FFE00`), `candidates()` / `auto_pick()` (title matching, below), `import_set()` |
| `core/ra_presence.py` | `RichPresenceReader`: evaluates a set's rich presence script against the DSi's memory. Each read fetches what the script used last time in one batch; anything new is fetched on the spot. Addresses past main RAM read as 0. |
| `core/rcheevos.py` | ctypes binding for rcheevos (RetroAchievements' rule engine, `third_party/rcheevos/`): the runtime with rich presence and achievements (`rc_runtime_*`), and `compile_offline()`, the console's program for offline play (DSiRPC's `dsirpc_offline.c` in the library) |
| `core/hub.py` | `StateHub`: polls a source on its own thread, keeps the latest `Snapshot` (state, `online`, status text), calls listeners with events worked out by `diff_events()` (online/offline, another game, battle start/end, shiny encounter, level-up, fainted, badge, Pokédex catch, map and party changes). A state is Platinum's parsed dict or another game's (`is_other()`). Sources: `DsiSource` (follows the DSi from game to game: the Platinum parser on `CPUE`, `OtherGame` on anything else, and a `RaGame` for every game, ticked between parses; its events come in through `take_events()`), `FileSource` (`game=` for another game's dump). A source that returns the very same state object as last time means "nothing new" (an achievement check between parses), so `Snapshot.updated` only moves on real reads. In a battle, `DsiSource` reads only the battlers (the BattleMon fields the parser decodes, 108 bytes a battler, plus the last moves, the music and the battle pointer: two requests in a single battle) every 0.3 s and carries the rest over from the last full read. It goes back to a full read when a battler stops decoding, the music or pointer changes, five quick reads in a row get no reply, or 60 s have passed. |
| `core/games.py` | Which game is running and which per-game features apply. `is_platinum()`: the Platinum parser (and so Platinum's presence, the overlay's party and battle views and `tools/dsi_status.py`) only runs on `CPUE`, or on an older rpcprobe build that doesn't report the game. `name()` for status lines. |
| `core/demo.py` | `DemoSource`: made-up states in the parser's format, looping through overworld, battles, a shiny, a level-up and an offline stretch |
| `rpc/presence_connector.py` | `DiscordConnector`: the Rich Presence as a hub listener, for every game. Connects only while there's something to show, switches Discord application when the game needs another, sends only changes (at most about every 5 s), clears on offline, `set_enabled(False)` and `close()`; `status` is the tray's "Discord: ..." line |
| `app/engine.py` | `Engine`: builds the source, hub and connector from the settings, switches the read interval with the overlay, runs the overlay window (`run_overlay_here()`, or `set_overlay()` on its own thread), writes `logs/state.json`, reloads `dsirpc.cfg` when it changes, and answers the launcher's offline sync (`ConsoleSync`; section 6, "Offline play"). `setup_logging()`, `PortInUse` |
| `core/offline.py` | Offline play's files and messages: the unlock file (`read_unlocks()`, `count_unlocks()`), the sets (`build_set()` with `rcheevos.compile_offline()`, `read_set()`, `state_size()`), the sync request and answer (section 7) |
| `core/console_sync.py` | `ConsoleSync`: UDP and TCP port 4245 on its own thread, answering the launcher's sync with the engine's sets and passing on the unlocks |
| `app/tray.py`, `app/setup_wizard.py`, `app/startup.py` | The tray icon, setup and Start with Windows (above) |
| `overlay/` | The overlay window: `app.py` (`OverlayWindow`: window and keys), `scenes.py` (views, banners, animation, move detection), `effects.py` (move animations), `markers.py` (condition markers), `backdrop.py` (battle backgrounds and weather), `ui.py` (palette, panels, HP bars, move buttons), `sprites.py` (asset conversion), `font.py` (pixel fonts) |

---

## 6. Discord Rich Presence behaviour

Nothing is shown while the game isn't running. Section 5 covers when the
presence appears and when it's taken down.

### In the overworld (activity type: Playing)

| Field | Content | Example |
|---|---|---|
| Line 1 | `Exploring <location>` | Exploring Route 209 |
| Line 2 | Badges and Pokédex caught | Badges: 3 \| Pokédex: 18 |
| Party | Non-fainted / party size (eggs excluded) | (6 of 6) |
| Large image | Your trainer (Dawn or Lucas, from the save) walking, facing the way you face | `Trainer-Overworld/Dawn-Right.gif` |
| Large hover | `<name> in <specific map>` | Vivia in Route 209 Gate To Hearthome City |
| Small image | Lead Pokémon's overworld sprite, shiny-aware | `Shiny-Pokemon-Overworld/77.gif` |
| Small hover | Lead's name, species, level, HP | Lead: Blucifer (Ponyta), Lv 36, 84/84 HP |
| Timer | Counts up from the save's playtime | 14:03:13 |

### In battle (activity type: Competing)

Wild battles are recognised by the foe's OT ID (the parser's `wild` flag,
section 9), whatever the music says; for the rest, the battle kind comes
from the music ID:

| Music | Line 1 | Large hover prefix |
|---|---|---|
| `0x45C` wild | Encountering a wild Pokémon | A wild |
| `0x45D` gym | Battling Gym Leader `<name>` | `<name>`'s |
| `0x464` rival | Battling rival `<name>` | `<name>`'s |
| `0x462` Cynthia | Battling Champion Cynthia | Cynthia's |
| `0x470` Elite Four | Battling Elite Four `<name>` | `<name>`'s |
| `0x45F` trainer | In a trainer battle | The trainer's |
| anything else | In a battle | The foe's |

`<name>` comes from the trainer value at battle `+0x3C6`, which is actually
the trainer **class** (see section 9). For rival battles (class `0x3F`) it
is the name you gave your rival in the intro, read from the save
(`S+0x27FC`), so a renamed rival shows up under their real name. The class
can read something else for a moment (it once dropped the name while
Maylene sent out Lucario), so `core.parser.TrainerMemory` keeps the name
read most often during a battle; the hub uses it.
`tools/dsi_status.py` shows the raw value per read, with the class in hex.

| Field | Content | Example |
|---|---|---|
| Line 2 | `<your mon> is fighting <foe>`; in doubles `<mon> and <mon 2> are fighting <foe> and <foe 2>` | Blucifer is fighting Buizel |
| Large image | Foe's front sprite on the battle diorama, shiny-aware | `Pokemon-Battle-NormalLarge/418.gif` |
| Large hover | Owner, species, level, HP | Barry's Buizel (Lv 23, 41/59 HP) |
| Small image | Your Pokémon's back sprite, shiny-aware | `Shiny-Battle-BackSmall/77.gif` |
| Small hover | Trainer name, mon, level, HP (both of yours in doubles, cut at Discord's 128 characters) | Vivia's Blucifer (Lv 36, 52/84 HP) |

Discord hides the party fraction while the type is Competing.

"In battle" means two things: the battle pointer is valid, **and** both your
first battler and the foe's first battler decode as real Pokémon (species
1-493, level 1-100, 0 ≤ HP ≤ max HP). The pointer isn't cleared after a
battle, so the sanity check is what separates a live battle from leftovers.

### Any other game

Any game other than Platinum shows what DSiRPC can know without a parser for
it (`core/other_game.py` reads it, `rpc/generic_presence.py` lays it out):

| Field | Content |
|---|---|
| Name | The game's title (sent as the activity's name; Discord shows it instead of the application's name where it supports that) |
| Line 1 (and 2) | The RetroAchievements rich presence text, split over both lines at a separator if it's long; without a set file, the title |
| Large image | The box art from GameTDB (`art.gametdb.com/ds/coverS/<region>/<code>.png`), or the RA icon if there's none (or the console picture if there's neither) |
| Large hover | The title, with "RetroAchievements: 12 of 132 unlocked" (signed in) or "RetroAchievements: 132 achievements" |
| Small image | The console picked in the tray's **Console icon** (`console_icon` in `[app]`; a picture in `Assets/Consoles`, served by GitHub Pages like the sprites), hovering its name ("Nintendo DSi XL"). With "None", the RA game icon, hovering the RetroAchievements line |
| Timer | Counts up from when the game was first seen this session |

The title comes from the set file, else `core/games.py`'s names, else the
title in the game's header (like `MARIOKART DS`), else the game code. Which
Discord application is used: `[discord_apps]` in `dsirpc.cfg` by game code,
else its `default`, else `discord_client_id` (`--client-id` overrides all of
them). Without a rich presence to read, the presence stays up while hellos
keep coming (within 15 s) and is cleared like Platinum's after about 30 s
without them.

**Finding the set.** `ra/<code>.json` (or a `ra/games.txt` mapping) first.
Signed in, RetroAchievements next (`core/ra_link.py`): by the hash of your
game file when there's a `roms` folder, else by the set file's game ID, else
by the game's title against RetroAchievements' list of DS and DSi games
(`systemgames`, kept a week in `ra/cache/`), with the rules below; the set
is downloaded into `ra/<code>.json` (again when that copy is over a day
old). Without an account, or when RetroAchievements has nothing, and with
`racache` set, DSiRPC looks in the emulator's cache once per session
(`core/ra_cache.py`). The DSi can't give the RA game ID (RA
identifies DS games by a hash of the whole ROM), so the game's title is
matched against the sets' titles. That's the title in the game's header
copy at `0x023FFE00` when it's there: it is under emulators, but not under
nds-bootstrap on a DSi or 3DS (nds-bootstrap keeps the header at
`0x027FFE00`, past the 4 MB rpcprobe reads, and with the DSi's bigger RAM
that isn't a mirror of `0x023FFE00`). Without it, the titles come from
GameTDB's list by the game code the hellos give (`core/game_titles.py`:
`CPUE` is "Pokemon: Platinum Version"), then the same game's US and European
titles, then `core/games.py`'s name, each tried until one matches clearly.
Titles are compared letters and digits only, accents dropped: 3 if they're the same (`MARIOKART DS` and "Mario Kart DS"), 2 if
the set's title starts with it (`POKEMON PL` and "Pokémon Platinum
Version"), 1 if its letters appear in order. A set is copied to `ra/` on its
own only with a score of 2 or more that no other set shares, and never a
hack, homebrew or subset (RA titles with `~...~` or `[Subset`). Anything
less clear is left to setup, which lists the candidates.

### RetroAchievements

Every game, Platinum included, gets a `RaGame` (`core/ra_game.py`) while it
runs. With a set, rcheevos (`core/rcheevos.py`) holds the set's rich
presence script and its achievements: the official ones (flag 3) of the core
and bonus sets, minus the ones RetroAchievements says you already have, and
minus any that read absolute addresses past main RAM (the ARM9's data TCM at
`0x1000000` and up, which the DSi side can't read; achievements behind a
pointer are kept, and a pointer that lands outside main RAM reads 0).

**Checking.** About once a second (`interval`), `tick()` reads every value
the set read last time in one batch (`SparseRam`, usually one request),
runs one rcheevos frame and gets the rich presence text. For rcheevos a
"frame" is one read: "changed since the last frame" means since the last
read, and a hit count of 60 frames needs 60 reads. Achievements about
states that last work as on an emulator; ones about moments shorter than a
read can unlock late, never, or (when a condition that must not happen is
missed) when they shouldn't. When the DSi goes quiet for 30 s, the hit
counts start over, as on a reset.

**Signing in.** Setup's `login2` with your password returns a token, saved
as `token` in `[ra]`. Every other request sends the user name and token,
like RA emulators. Requests are form POSTs to
`https://retroachievements.org/dorequest.php`, encoded exactly as rcheevos
encodes them (checked byte for byte against rcheevos 12.5's request
builders), with the User-Agent `DSiRPC/0.3.0 (Windows <version>)
rcheevos/12.5`: RetroAchievements sees what DSiRPC is, and only counts its
unlocks as softcore.

**A session.** When a game's set is known, `startsession` (`g` the game ID,
`h=0` and `m` the hash when there's a game file, `l` the rcheevos version)
returns the unlocks you already have. Then `ping` every 2 minutes (the first
after 30 s, and only while the game is being read) with the rich presence
text in `m`, which is what your profile shows (`profile`; without it the
pings carry no text). Neither happens with `profile` and `submit_unlocks`
both off.

**Unlocks.** A triggered achievement is taken out of the runtime, logged
(`logs/achievements.log`, tab-separated: time, game, ID, title, points, sent
or not, progress), shown (Windows notification, overlay banner) and, with
`submit_unlocks` on and signed in, sent with `awardachievement` (`a`, `h=0`,
`m` when there's a hash, and `v`, the MD5 of the achievement ID, user name
and hardcore flag; with `o`, the seconds since the unlock, when it's sent
10 s or more late). Each unlock is written to `ra/cache/pending_unlocks.json`
first and taken off when RetroAchievements answers; without an answer it's
retried after 0, 1, 2, 4 ... up to 120 s (as rcheevos' client does), and
the file is sent again the next time DSiRPC starts with the same account.
"User already has this achievement" counts as sent.

**Offline play.** When the launcher syncs (section 7), the engine sends it a
set for the game being started (from `ra/`, or downloaded by its code) and
for every other game in `ra/`, built by `core/offline.py`: the official
core and bonus achievements, minus the ones you're known to have (from
`startsession` and sent unlocks, `ra/cache/unlocked.json`) and the ones
past main RAM. rcheevos parses them, as it does for DSiRPC itself, and
DSiRPC's addition to the library (`third_party/rcheevos/dsirpc_offline.c`)
writes out what it parsed as the program the console's checker runs
(section 8). Left out: achievements rcheevos can't parse, those that need
floating point (the console's ARM7 has none), and, if the set and its state
don't fit in the 252 KB the console sets aside (256 KB less 4 KB for
reading `RPCUNLK.BIN`), the biggest ones. Each set
goes only if the console's copy is missing or has another stamp. The console
saves every unlock, including the ones made while DSiRPC was watching, so
the ones DSiRPC already knows you have (`unlocked.json`) are only counted in
the log (`... unlock(s) from the console DSiRPC already had`). The rest
are logged (`(offline play)` in `achievements.log`), announced in one
notification and, with `submit_unlocks` on, sent like any other unlock, with
`o` set from the console's time of the unlock (a time more than a day ahead
or two years behind is taken as now). Signed out, they wait in
`pending_unlocks.json` for the next account that signs in.

---

## 7. Wire protocol

The in-game traffic is UDP on port 4244, in both directions and from the
same source port. Multi-byte fields are **big endian**. The launcher's sync
for offline play is separate, on port 4245, and little endian (the last
subsection).

### Hello (DSi -> broadcast, once per second)

Sent to 255.255.255.255, so every PC on the network gets it and nothing has
to be configured.

ASCII text:

```
DSiRPC hello #N gpio=XXXX rev=XX ioen=XX last=X gc=XXXX v=XX hc=XXXX rx=N req=N arp=N eap=N rxm=N e53=N txm=N t53=N rep=N a9=N vb=N
```

| Field | Meaning |
|---|---|
| `#N` | Packet counter |
| `gpio` | `0x04004C04` when the chip was probed. `0000` is expected; bit 8 (`0100`) would mean old DS mode. |
| `rev`, `ioen` | SDIO CCCR responses from the chip probe. `11` and `02` are normal; `ioen=00` means the chip was reset. |
| `last` | Result of the previous send: 0 OK, 1 TX overflow, other values are SDIO errors |
| `gc` | The running game's 4-letter code, from its header (`CPUE` = Platinum US, `IRBO` = Black US); `?` for unreadable characters. Read once, on the first VBlank. Older builds don't send `gc`, `v` or `hc`. |
| `v` | The game's ROM version (hex) |
| `hc` | The game's header CRC (hex), which tells apart dumps and hacks that share a game code |
| `rx` | Packets drained from the chip (any kind) |
| `req` | Memory requests answered |
| `arp` | ARP replies sent |
| `eap` | EAPOL frames seen, meaning the router renewed its keys. Watch this if hellos die at regular intervals. |
| `rxm` | How received frames are read from the chip: `53` = CMD53 block transfers (one SDIO command per frame), `52` = one CMD52 per byte (the `RPCPROBE_RX_CMD53` switch is off, or CMD53 failed three times on this console and it switched itself back). |
| `e53` | CMD53 reads that failed: an SDIO error or timeout, or data that didn't match the frame's header. A few right at the start followed by `rxm=52` means CMD53 doesn't work on this console. |
| `txm` | How frames are sent: `53` = CMD53 block writes (replies, ARP replies and 9 hellos in 10; every 10th hello always goes out with CMD52 so the PC keeps hearing from the DSi), `52` = CMD52 for everything (`RPCPROBE_TX_CMD53` off, CMD53 writes failed three times, or the PC had to re-send the same request twice in a row, which means CMD53 replies weren't arriving). |
| `t53` | CMD53 writes that failed (SDIO error or timeout). |
| `rep` | Requests the PC sent again with the same sequence number, meaning it never got the reply. |
| `a9` | The ARM9 half of the per-frame capture. `1`: rpcprobe found it in the ARM9 cardengine, so captured values are read by the ARM9 (through its cache). `2`: found, and its VBlank hook is in (it goes in when a capture starts). `3` to `5`: the game replaced its VBlank handler and the hook was put back (`a9` is 1 + hooks put in; after four, the ARM7 reads by itself). `0`: an ARM9 cardengine without it (DLDI or GSDD variant, or an older build), so the ARM7 reads main RAM itself. Older builds don't send `a9`. |
| `vb` | Longest VBlank tick of the in-game side since the previous hello, in scanlines (about 64 µs each; a whole frame is 263). A tick that sends a 256-byte frame with CMD52 (roughly 19 µs per SDIO command) takes about 76 lines, 4.8 ms, and play was smooth at that on hardware. With CMD53 sending (`txm=53`) it should be far lower, except in the hello right after each 10th one, which covers a CMD52 hello tick. Values approaching a whole frame mean rpcprobe is holding up the game's own ARM7 work long enough to stutter; lower `RPCPROBE_RX_BYTES_PER_VBLANK` in `rpcprobe_build.h`. |

### Memory request (PC -> DSi)

```
'R' | seq u16 | count u8 | count x ( addr u32 | len u8 )
```

### Memory response (DSi -> PC)

```
'D' | seq u16 | count u8 | status u8 | data...
```

`data` is the requested ranges back to back, in request order, and is only
there when `status` is 0. The reply goes to whoever asked (IP, port and MAC
taken from the request).

| Status | Meaning |
|---|---|
| 0 | OK |
| 1 | Malformed, more than 16 ranges, or more than 192 bytes in total |
| 2 | A range falls outside main RAM (`0x02000000`-`0x023FFFFF`). This protects the ARM7, which has no MMU. |
| 3 | `'F'` with no watch list (none set yet, or stopped with an empty `'W'`) |

Limits: 16 ranges and 192 bytes per request. The DSi reads at most one
incoming packet per VBlank (60 per second) and serves requests inside the
VBlank interrupt. The home network's broadcast traffic shares that queue, so
a single request takes roughly 15-400 ms. The PC client retries up to 3
times, with a 1 s timeout each.

The DSi also answers ARP requests for its own IP. It sends a gratuitous ARP
when it starts serving, so the PC can address it directly.

### Per-frame capture (PC -> DSi)

A memory request only samples as often as a reply comes back, so a value
that changes for a single frame can be missed. For values that have to be
seen every frame (RetroAchievements definitions are checked once a frame),
the PC sends a watch list once, the DSi reads it at the start of every VBlank
into a 2 KB ring, and the PC drains the ring:

```
'W' | seq u16 | count u8 | count x ( addr u32 | size u8 )     set the watch list
'F' | seq u16 | 0 u8 | from u16                                fetch records
```

Both are answered with the same `'D'` header as a memory request (`count`,
`status`; data only when `status` is 0). A watch is 1, 2 or 4 bytes inside
main RAM, at most 8 of them; `count` 0 stops the capture. Adding `0x80` to
`count` has the ARM7 read every value itself even when the ARM9 half is there
(for comparing, `tools/frame_check.py --arm7-only`). Any `'W'` empties the ring and
starts the record numbering again at 0.

Who reads the values: the game's writes sit in the ARM9's data cache for a
while before they reach main RAM (measured on Platinum: a frame late on about
a third of frames in menus and battles, several frames during loading), so
the ARM7 reading main RAM sees them late. The ARM9 reads through its cache.
When it reads matters too: a game can change a value right as VBlank starts
(Platinum's VBlank counter is one), and a read made a little later lands
sometimes before that change and sometimes after it. So the ARM9 takes a
snapshot at the very start of every VBlank interrupt, from a hook in front of
the game's own VBlank handler (entry 0 of the game's interrupt table, the
table nds-bootstrap already hooks for IPC sync), before that handler runs.
The hook goes in only when a capture starts: rpcprobe writes the list into a
288-byte block in the ARM9 cardengine (`common/include/dsirpc_watch_block.h`)
and rings the ARM9 with IPC sync value 3, nds-bootstrap's own do-nothing
doorbell. It only rings when its last sync value was 0 or 3, so it never
replaces one of nds-bootstrap's commands (screen swap, colour LUT, reset,
in-game menu) that the ARM9 hasn't read yet; the ARM9 checks its hook on any
IPC sync interrupt. Each snapshot goes into one of four numbered slots, and
rpcprobe records them in order, one per VBlank, starting one snapshot behind
the newest (the ARM9's VBlank and its own start at almost the same moment, so
the newest may not be there yet). ARM9 values are therefore from the start of
that VBlank or the one before, never one twice or one skipped. When there's no snapshot to record (the hook isn't in yet, or the game
had interrupts off for a while), rpcprobe reads main RAM itself and marks the
record; if that lasts, it rings again, since the game may have replaced its
VBlank handler. Each re-hook is a fresh hook that keeps calling the handler
it was put in front of, so a game that puts back a handler it saved earlier
still gets the right one; after four, rpcprobe reads by itself. Right after
nds-bootstrap's in-game menu, its last sync value stays 9 (the menu's), so
rpcprobe can't ring until nds-bootstrap's next card read sets it back to 3;
until then a hook that's missing stays missing and rpcprobe reads by itself. A soft reset
(nds-bootstrap's `reset()`) makes all four available again, since the reloaded
game can't be holding any of them.

`from` is the number (mod 65536) of the first record wanted: 0 after a `'W'`,
then the one after the last record received. The reply's `count` is the
number of records, and its data is:

```
first u16 | lost u16 | recSize u8 | count x ( tick u16 | vcount u16 | values )
```

`first` is the number of the first record returned (ask for
`first + count` next), and `lost` is how many records from `from` on had
already been overwritten. In a record, `tick` is the DSi's own sample number,
`vcount` the scanline the values were read on (bits 0-8; 192 is the start of
VBlank) with bit 15 set when the ARM7 read them rather than the ARM9, and
`values` each watch's bytes as they are in memory (little endian), in list
order. The ring holds `2048 / recSize` records: 256 frames (about 4 s) with
one 4-byte watch. Nothing is written to the game; the list and the ring are
rpcprobe's own memory.

### Offline play: the launcher's sync (TCP/UDP 4245)

Whenever the launcher is connected (after connecting, and when a game is
picked), it looks for DSiRPC and syncs. `core/offline.py` (PC) and
`launcher/source/sync.c` (console) are the two sides; everything here is
**little endian**.

1. The launcher broadcasts `DSiRPC sync?` + u8 version (1) to UDP 4245,
   every 0.5 s for 1.5 s. DSiRPC answers `DSiRPC sync!` + u8 version + u16
   TCP port.
2. The launcher connects over TCP and sends:

   ```
   "DRSQ" | version u16 | n u16 | game code[4] | unlock bytes u32 | reserved u32
   n x ( code[4] | stamp u32 )        the sets it has
   RPCUNLK.BIN as it is               (or nothing, if it isn't valid)
   ```

   The game code is the one being started, or four zero bytes.
3. DSiRPC answers:

   ```
   "DRSA" | version u16 | status u16 | taken u16 | n u16 | reserved u32
   n x ( code[4] | size u32 | the .DRS file )
   ```

   `status` 0 is OK, 1 that the request couldn't be read. `taken` is how
   many valid unlock slots it got, repeats included. The sets are the ones
   the console doesn't have or has another stamp of, the started game's
   first.
4. The launcher zeroes the unlock slots if `taken` matches its own count
   (otherwise they stay for the next sync), writes each set to
   `sets/CODE.TMP` and renames it to `CODE.DRS`, then hangs up. DSiRPC waits
   for that before closing, so the TCP wait after closing (TIME_WAIT) is on
   the console's side.

**`RPCUNLK.BIN`** is 4096 bytes: 256 slots of 16 bytes. Slot 0 is the
header: `"DRUL"`, u16 version (1), u16 slot size (16), u16 slot count (256),
6 bytes reserved. Each other slot is one unlock:

```
achievement ID u32 (0: empty) | game code[4] | when u32 | seq u16 | check u16
```

`when` is seconds since 2000-01-01 by the console's clock (local time).
`check` is `0x5AA5` plus the first seven u16s, so a slot that was only
partly written is skipped. The in-game side (`rpcprobe/probe_ach.c`) writes
each unlock into the slot after the last one in use (a half-written slot
counts as used), one 16-byte write per unlock; it never has to make or grow
the file. Its `seq` is the slot number, and its `when` is the launcher's
clock (`RPCHAND.TXT`'s `time=`) plus the VBlanks since the game started, so
time asleep isn't counted (0 if there was no `time=`; DSiRPC then uses the
time it gets them). The game's unlocks already in the file when it starts
aren't checked again, so a session never saves the same achievement twice.
The console saves every unlock, online too, so DSiRPC leaves out the ones it
already knows about (`engine._offline_unlocks()`, `RALink.known_unlocks()`).

**`CODE.DRS`** (a set, version 2) has a 64-byte header: `"DRSE"`, u16
version (2), u16 header size (64), game code[4], u32 RetroAchievements game
ID, u32 stamp (CRC-32 of the program), u16 achievement count, u16 flags (0),
u32 program size, u32 state size (the RAM the checker needs for it), then
32 bytes of zeros. The set and its state have to fit in 252 KB
(`offline.ACH_MEMORY`: nds-bootstrap's 256 KB less the 4 KB the console
reads `RPCUNLK.BIN` into). The program follows: rcheevos' parse of the
achievements, as the checker runs them. Its layout is described at the top
of nds-bootstrap's `rpcprobe/probe_ach_vm.c`: the memory values to read
(plain ones and rcheevos' "modified" ones, the AddSource / AddAddress /
Remember chains), then each achievement's groups with their conditions in
the order rcheevos evaluates them, 16 bytes each. The launcher only reads the
code and the stamp, which are in the same place in every version. (Version 1
had the MemAddr text instead of a program.)

### The checker's report (DSi -> broadcast, after each hello)

While a set is loaded (or failed to load), the VBlank after each hello also
broadcasts, on UDP 4244:

```
DSiRPC ach n=<achievements> t=<unlocked> p=<passes> l=<lines> s=<saved> x=<not saved> w=<waiting> ids=<id,id,...>
```

`n` is how many achievements the checker runs, or why it isn't running: -1
`RPCSET.BIN` isn't a version 2 set, -2 it's another game's set, -3 it's too
big, -4 its program doesn't add up, -5 it's damaged (CRC). `t` counts the
achievements it has unlocked since the game started, `ids` are the latest
(up to 8), `p` is how many passes over every achievement it finished since
the last report (so, a second), and `l` the most scanlines it took in one
VBlank (a frame has 263). `s` is how many of its unlocks it saved to
`RPCUNLK.BIN`, `x` how many it couldn't (no file, file full, too many at
once, a failed write) and `w` how many of the game's unlocks were already
waiting in the file when it started. `DSiClient` (`AchReport`) logs the
checker starting, each of its unlocks (`Console: its checker unlocked
achievement ...`), the saves (`Console: saved N unlock(s) to its SD card for
DSiRPC`, or a warning for `x`) and once a minute its speed. Older DSiRPC
versions ignore the packet, and older consoles' packets have no `s`, `x` or
`w`.

---

## 8. DSi side: what was changed in nds-bootstrap

`nds-bootstrap/` is upstream nds-bootstrap at commit `f5f9ea48` plus the
changes below. The full list, and how to move to a newer upstream version,
is in [nds-bootstrap/DSIRPC_CHANGES.md](../nds-bootstrap/DSIRPC_CHANGES.md).
All paths below are under `nds-bootstrap/retail/`.

| File | Change |
|---|---|
| `cardenginei/arm9/source/cardengine.c`, `cardenginei/arm9/source/misc.c`, `cardenginei/arm9/source/dsirpc_watch.c`, `common/include/dsirpc_watch_block.h` | The ARM9 half of the per-frame capture: a hook in front of the game's VBlank handler snapshots the watched values at the start of every VBlank, and `myIrqHandlerIPC` calls `dsirpcWatchService()`, which puts the hook in when rpcprobe rings (see [section 7](#7-wire-protocol)); `reset()` (`misc.c`) frees the hooks for the reloaded game on a soft reset. Only in the plain `cardenginei_arm9`; the DLDI, GSDD and TWLSDK variants compile it out. 952 bytes; 888 bytes of that cardengine are still free. |
| `cardenginei/arm7/source/cardengine.c` | Includes `rpcprobe/probe_hook.h` and calls `Probe_VBlankTick(ndsHeader, readOngoing ? NULL : &saveMutex)` from `myIrqHandlerVBlank` (the header tells the hellos which game is running), and `Probe_HaltTick(&saveMutex)` at the end of `runCardEngineCheckHalt()`, the swiHalt hook, where the checker's unlocks are saved (not in the `ALTERNATIVE`/`TWLSDK` variants). Also four fixes to upstream's debug-only code. |
| `cardenginei/arm7/Makefile` | `source/rpcprobe` added to `SOURCES`; `-Os` to fit the ARM7 region. `-DDEBUG` is **off**. |
| `common/source/my_fat.c`, `common/source/my_sd.c` | Debug-only fixes so a clean `-DDEBUG` build compiles with GCC 14: a guarded `#include "nocashMessage.h"`, and `(u32)` casts on pointers passed to `dbg_hexa`. Normal builds are byte-identical. |
| `cardenginei/arm7/source/rpcprobe/` | All DSiRPC ARM7 code (next table) |
| `bootloaderi/source/arm7/main.arm7.c` | `DSIRPC_KEEP_DSI_WIFI 1`: skips the switch to DS-mode Wi-Fi so the launcher's association survives. `romLocationAdjust()` keeps the ROM cache and ROM-in-RAM loading out of the achievement checker's memory, and the ROM-in-RAM size limit is 256 KB smaller to match |
| `common/include/locations.h` | `DSIRPC_ACH_LOCATION` (`0x0CFB0000`) and `DSIRPC_ACH_SIZE` (256 KB): the achievement checker's memory, in the ROM cache's area at the top of the DSi's 16 MB (the middle of the 3DS's 32 MB) |
| `bootloaderi/source/arm7/patch_common.c` | `DSIRPC_PLATINUM_NO_WIRELESS_SEARCH 1`: for `CPUE` Rev 1 only, and only if the expected instructions are found. It patches `CommManager_InitializeSearchParty` to return immediately and `CommManager_GetAvailableConnections` to return 0 (`0x02037D48`, `0x02037DA0`). This removes the communication error after Continue. |

### `rpcprobe/` files

| File | Role |
|---|---|
| `probe_hook.c/.h` | The VBlank state machine: load files, restore DSi mode if needed, probe the chip, run (or fail). It sends hellos and services requests, and on the first tick reads the game's code, ROM version and header CRC from its header for the hellos. `Probe_HaltTick()` saves the checker's unlocks. |
| `twl_wifi.c/.h` | Minimal Atheros SDIO access: chip probe with CMD52, sending and receiving a packet with one CMD53 block transfer each (or CMD52 byte by byte if CMD53 is off or has failed for that direction) |
| `probe_req.c/.h` | Parses Ethernet/ARP/IPv4/UDP, answers `'R'` requests and ARP (and hands `'W'`/`'F'` to `probe_watch.c`), counts EAPOL |
| `probe_watch.c/.h` | Per-frame capture: the watch list (up to 8 values), a record per VBlank into a 2 KB ring, and the `'W'`/`'F'` handlers. Finds the ARM9 half's block (by its magic, in the ARM9 cardengine's region), records the ARM9's snapshot each VBlank, and reads main RAM itself when there's none. |
| `probe_net.c/.h` | Builds LLC/SNAP + IPv4 + UDP frames for the (broadcast) hellos |
| `rpcprobe_config.c/.h` | Reads `RPCHAND.TXT` (`time=` dates offline unlocks); defines the UDP port (4244) |
| `probe_ach.c/.h` | Offline play's achievement checker: loads `RPCSET.BIN` and `RPCUNLK.BIN` on the first VBlank, checks the set's CRC, runs it a slice each VBlank, saves each unlock into `RPCUNLK.BIN` and keeps the latest for the report (below) |
| `probe_ach_vm.c/.h` | The checker's interpreter: a port of rcheevos 12.5's evaluation, without floating point, for the program DSiRPC builds. Plain C; the same file is tested against rcheevos on a PC |
| `rpcprobe_build.h` | `RPCPROBE_REQUESTS` (1 = answer memory requests, 0 = hellos only), `RPCPROBE_RX_CMD53` / `RPCPROBE_TX_CMD53` (1 = CMD53 for receiving / sending, 0 = CMD52 only), `RPCPROBE_HELLO_CMD52_EVERY`, the per-VBlank receive limits, and the checker's `RPCPROBE_ACH` (0 = off), `RPCPROBE_ACH_LINES_PER_VBLANK`, `RPCPROBE_ACH_SKIP_AFTER_LINES` and `RPCPROBE_ACH_SAVE_FALLBACK` |
| `DEBUGGING.md`, `TWL_RX_NOTES.md` | Debugging guide (hello fields, RAM viewer byte, debug builds) and chip notes |

### The achievement checker (`probe_ach.c`)

For offline play the console checks the game's achievements itself, with
or without Wi-Fi. DSiRPC has already had rcheevos parse them (section 6), so
the console only runs the result:

- **Loading.** On the game's first VBlank (the only time the VBlank may
  touch the SD card), `RPCSET.BIN` is read into `DSIRPC_ACH_LOCATION`, the
  256 KB the bootloader keeps the ROM cache out of: the set, then the
  checker's state (every memory value with its last change, every
  condition's hit count). It's only used if its game code is the running
  game's. `RPCUNLK.BIN` is read into the last 4 KB (sets are built to leave
  them free) to find where the next unlock goes and which of the game's
  achievements already wait there; those aren't checked again. Over the
  next few VBlanks the set's CRC-32 is checked, a slice at a time; then it
  runs.
- **Running.** `probe_ach_vm.c` follows rcheevos' `rc_runtime_do_frame`: a
  pass reads every memory value (pointers and AddSource chains included),
  then evaluates every achievement, with rcheevos' rules for hit counts,
  ResetIf, PauseIf, AndNext/OrNext, AddHits, Measured, alt groups, and an
  achievement having to be false once before it can trigger. A pass is
  rcheevos' "frame".
- **Time.** It all happens in the VBlank interrupt, so the checker gets
  `RPCPROBE_ACH_LINES_PER_VBLANK` (16) scanlines, about 1 ms, after the rest
  of the tick, and skips its turn if the tick already took
  `RPCPROBE_ACH_SKIP_AFTER_LINES` (40). It can stop after any 32 memory
  values or conditions and carry on next VBlank, so a big set takes a few
  VBlanks per pass instead of one long one. Platinum's set (101
  achievements, 2,635 conditions, 1,733 memory values) is about 80 KB plus
  26 KB of state.
- **Checking it.** The interpreter is plain C. On a PC it ran side by side
  with rcheevos on the same memory for thousands of frames, on five real
  sets (with a Platinum RAM dump) and on tens of thousands of random
  achievements using every condition type, size and operator, stopping at
  random points: every achievement's state and every condition's hit count
  matched after every frame. With Wi-Fi, its report (section 7) shows on
  hardware what it unlocks and how long it takes.

- **Saving.** Each unlock goes into a small queue (7 places) with its time:
  `RPCHAND.TXT`'s `time=` plus the VBlanks counted since (59.8261 a second).
  The SD card can't be touched from the VBlank interrupt later on (rules
  below), so the queue is written out from nds-bootstrap's swiHalt hook
  instead: `runCardEngineCheckHalt()` runs whenever the game's ARM7 idles,
  outside interrupts, and serves the ARM9's ROM reads there under
  `saveMutex`. `Probe_HaltTick()` takes the same lock with `tryLockMutex()`
  (so never while a save or ROM read is under way) and writes one 16-byte
  slot (section 7). For a game whose swiHalt nds-bootstrap couldn't hook,
  the VBlank does it after two seconds without a halt, under the same lock
  and only while no non-blocking ROM read is in flight (`readOngoing`).
  Without `RPCUNLK.BIN` (the game wasn't started from the launcher), or
  with 255 unlocks already waiting, unlocks are counted (`x` in the report)
  but not saved.

The original hand-rolled DS-mode Wi-Fi + WPA2 driver (from before the
DSi-mode handoff) has been removed. It was never committed to any repository,
so the only copy is in the backup made before the cleanup. How it worked is
described in [HISTORY.md](HISTORY.md).

### Rules the ARM7 code must follow

- **Only touch the SD card from the VBlank on the very first VBlank.** The
  game reads its save from the SD card in thread context. Any SD access from
  the VBlank interrupt later on (a log line, a file read) can land in the
  middle of that and hang or corrupt things. This caused the white screen
  and the party-menu crash. The checker's unlocks are written from the
  swiHalt hook instead, holding nds-bootstrap's `saveMutex` (above).
- **Stay small.** The cardengine ARM7 binary has a fixed-size region
  (61 KB in total; 60,012 of 62,464 bytes are used with the per-frame capture
  and the achievement checker), so every addition counts. Anything big
  goes in main RAM, like the checker's set and state.
- **Stay quick.** Everything runs inside the VBlank interrupt. That's why
  the receive path handles at most one packet per VBlank.

---

## 9. Memory map (Platinum USA Rev 1)

Addresses are hardware addresses (main RAM starts at `0x02000000`).
RetroAchievements addresses are the hardware address minus `0x02000000`.

This map was checked against a melonDS RAM dump, the pret/pokeplatinum
decompilation and live hardware reads. It supersedes the memory-map section
in [HISTORY.md](HISTORY.md), which is out of date (it says party battle stats
are unencrypted and has the wrong playtime offset). More verified fields that
aren't read yet are in [research.md](research.md).

### Save block: `S = [0x02101D40]`

| Offset | Field | Type |
|---|---|---|
| `S+0x7C` | Trainer name | 8 x u16, Gen IV charset, `0xFFFF` ends it |
| `S+0x8C` | Trainer ID | u16 |
| `S+0x8E` | Secret ID | u16 |
| `S+0x90` | Money | u32 |
| `S+0x94` | Character | u8, 0 = Lucas, 1 = Dawn |
| `S+0x96` | Badges | u8 bitmask: Coal, Forest, Cobble, Fen, Relic, Mine, Icicle, Beacon (bits 0-7) |
| `S+0x9C` | Coins | u16 |
| `S+0x9E` | Playtime | u16 hours, u8 minutes (`+0xA0`), u8 seconds (`+0xA1`) |
| `S+0xAC` | Party capacity | u32, always 6 |
| `S+0xB0` | Party count | u32 |
| `S+0xB4` | Party Pokémon 1-6 | 236 bytes each (encrypted, see below) |
| `S+0x1294` | Player location | s32 x5: map ID, warp ID, x, z, facing (0 up, 1 down, 2 left, 3 right) |
| `S+0x12A8` | Entrance location (the RA notes call it "previous map") | same layout |
| `S+0x12FA` | Weather | u16, IDs in `platinum_data.WEATHER` |
| `S+0x133C` | Pokédex magic | `0xBEEFCAFE` |
| `S+0x1340` | Pokédex caught | 493 bits, bit n-1 = national #n |
| `S+0x1380` | Pokédex seen | same layout |
| `S+0x1656` | Has Pokédex | u8 |
| `S+0x27FC` | Rival name | 8 x u16, same encoding as the trainer name |

The save block is SaveData (a 0x14-byte header) followed by the save pages
(system 0x64, player 0x34, party 0x598, then the bag, and so on), which is
why these offsets line up with the decompilation. A `.sav` file offset plus
0x14 gives the RAM offset.

### Party Pokémon (236 bytes)

| Offset | Content |
|---|---|
| `0x00` | PID (u32) |
| `0x04` | Flags: bit 0 = party data currently decrypted, bit 1 = box data currently decrypted, bit 2 = checksum failed |
| `0x06` | Checksum (u16) |
| `0x08-0x87` | Four 32-byte blocks (A/B/C/D), encrypted and shuffled |
| `0x88-0xEB` | Battle stats, encrypted |

Decryption uses the Gen IV stream cipher over u16 words:
`x = (0x41C64E6D * x + 0x6073) mod 2^32`, then `word ^= x >> 16`. The box
data is seeded with the checksum and the battle stats with the PID. Skip
either part if its "currently decrypted" flag is set, because the game
unlocks them while editing. The block order (`ABCD`, `ABDC`, ...) is indexed
by `((PID & 0x3E000) >> 13) % 24`. A correct decrypt sums (over the 64 box
words) to the checksum; the scripts report a mismatch as a probably torn read.

| Where | Field |
|---|---|
| A `+0x00` / `+0x02` / `+0x04` / `+0x06` | species, held item, OT ID, OT secret ID |
| B `+0x00` | moves (4 x u16) |
| B `+0x10` | IVs (u32), bit 30 = egg |
| B `+0x18` | bit 1 = female, bit 2 = genderless |
| C `+0x00` | nickname (11 x u16) |
| stats `0x88` / `0x8C` / `0x8E` / `0x90` | status, level, HP, max HP |

Other derived values: nature = `PID % 25`; the Pokémon is shiny when
`(OT ID ^ OT SID ^ PID_hi ^ PID_lo) < 8`.

### Battle: `B = [0x021BFB0C]`

The pointer stays set after a battle ends, so check the data too (see
section 6).

| Offset | Field |
|---|---|
| `B+0x3C6` | Trainer class of the opponent (u16 as read, falling back to the low byte when the u16 isn't a known class; values match the decomp's trainer classes, e.g. `0x3E` Roark, `0x3F` rival, `0x45` Cynthia). Names are in `platinum_data.TRAINER_SPRITES`. |
| `B+0x4F40` | 4 x BattleMon (0xC0 each, unencrypted): yours, foe, your 2nd, foe's 2nd |
| `B+0x527C` | Last move used by each battler, 4 x u16 in the same order (the decomp's `BattleContext.movePrevByBattler`). Worked out from the struct layout. Checked on hardware for your side (0 until your first move, then Fire Blast right after it was used); the foe's entry hasn't been seen change yet. See research.md section 11. The parser returns it as each battler's `last_move`. |

Within a BattleMon: species `+0x00`, moves `+0x0C`, form in the low 5 bits of
`+0x26` with shiny at bit 5, current PP `+0x2C` (4 x u8), PP Ups `+0x30`
(4 x u8; max PP = base + base / 5 x PP Ups), level `+0x34`, nickname
`+0x36`, HP `+0x4C` (s32), max HP `+0x50`, status `+0x6C`, held item `+0x78`,
gender `+0x7E` (low nibble: 0 male, 1 female), speed `+0x06` with its stat
stage at `+0x1B` (statBoosts[3], 0-12, 6 = unchanged), and the OT ID at
`+0x74` (u32). Wild Pokémon are made with the player's own trainer ID
(TID and SID as one u32, `S+0x8C`) and a trainer's Pokémon get a random
one, so a foe with the player's ID means a wild battle (`battle.wild`;
the trainer is then `None`). Also decoded, from the decomp's layout and not
yet checked on hardware: types `+0x24`/`+0x25` (IDs in `platinum_data.TYPES`
order; the same twice for a single type), stat stages `+0x18` (8 x s8, 0-12,
6 = unchanged, in `platinum_data.STAT_STAGES` order), `statusVolatile`
`+0x70` (confusion bits 0-2, infatuation 16-19, Substitute 24, Nightmare
27, Curse 28, Foresight 29) and `moveEffectsMask` `+0x80` (Leech Seed bit
2). The parser returns them as `types`, `stages` (only the changed ones,
-6..+6) and `conditions`.

### Fixed addresses

| Address | Field | Notes |
|---|---|---|
| `0x02000BBC` | SDK marker `21 06 C0 DE DE C0 06 21` | Read test |
| `0x021BEB04` | Music ID (u16) | Battle kinds in section 6, more in `platinum_data.MUSIC` |
| `0x021C04E3` | Text box open (u8 = 2) | From the RA notes |
| `0x021C5CCC` | Position x, y (height), z | fx32; the tile is the upper u16. Reads 0 in some indoor maps. |
| `0x021C5CE4` | "Stable" x / z | fx32; matches the saved location |
| `0x021BF5D8` | DS clock | u32 year (2 digits), month, day, weekday (0 = Sunday), hour, minute |

### Facing, using the RetroAchievements pointer convention

`P = [0x02101D2C]`. The facing is the u16 at
`(P & 0xFFFF) + 0x2A0884 + 0x02000000`, in the same 0-3 order as the saved
facing. It is the low half of the player object's 32-bit facing value
(there are no action bits in it). The presence falls back to the saved facing
if it ever reads something else. The same value can be reached without the
heap-layout assumption through the FieldSystem pointer chain described in
[research.md](research.md).

**The RA "+XXXXXX for 16bit" notes** mean: read the pointer, keep its low 16
bits, then add the note's number. This was confirmed with map ID, weather and
badges. It only works while the pointer's upper half is `0x0227`, which has
held in the dump and on hardware so far. Offsets listed as "for 24bit" are
ordinary pointer + offset.

### Where the facts come from

`docs/memory-map/` holds the RetroAchievements code-notes export (game 11732)
and ProjectPokemon's breakpoints page. The name tables and struct layouts come
from pret/pokeplatinum. One RA note is wrong: Pokédex caught is at `+0x1340`,
not `+0x12AC`.

---

## 10. Sprite assets pipeline

Everything is under `Assets/`, named by national dex number (`1.gif`-`493.gif`,
plus PokéAPI's extra IDs such as `10001.gif`; those are PokéAPI Pokémon IDs
for alternate forms, which DSiRPC doesn't use yet).

| Folder | Used for | Made by |
|---|---|---|
| `Pokemon-Battle-NormalLarge` | Foe in battle (large) | `process_diorama.py` on the raw sprites: 160x160 canvas, `BattleBackgroundNormal.png`, sprite at 1x, mirrored, bottom at y=126 |
| `Shiny-Battle-NormalLarge` | Shiny foe | same |
| `Pokemon-Battle-BackSmall` | Your battler (small) | `process_sprites.py` (margin 6): square canvas, mirrored, 2x nearest-neighbour |
| `Shiny-Battle-BackSmall` | Your shiny battler | same |
| `Pokemon-Overworld` | Lead Pokémon (small, overworld) | `process_sprites.py` (margin 4) |
| `Shiny-Pokemon-Overworld` | Shiny lead | same |
| `Trainer-Overworld` | Your trainer (large, overworld) | `process_trainer.py`, below |
| `Consoles` | Discord's small image for games without their own presence (the tray's **Console icon**): `DSiXL.png`, `New-Nintendo-3ds.jpg` | Added by hand; any picture added here (and pushed) shows up in the menu, named by `CONSOLE_NAMES` in `rpc/generic_presence.py` or its file name |

All scripts work on the current folder. `process_sprites.py` writes to
`processed_sprites/`, and `process_diorama.py` overwrites in place, so keep the
raw originals somewhere else first. They need Pillow. The source files for the
backgrounds are in `art-source/`.

**Note:** the NormalLarge `process_sprites.py` is *not* part of that folder's
pipeline. The dioramas are made from the raw sprites; running
`process_sprites.py` first doubles the size and flips the sprite back.

### Trainer sprites

`Trainer-Overworld/process_trainer.py` turns `NPC_198_Lucas.png` and
`NPC_201_Dawn.png` into `Lucas-Down/Left/Right/Up.gif` and the Dawn versions.
The sheets are 256x256 grids of 64x64 cells: **rows** are directions (down,
left, right, up) and **columns** are the 4 walk frames. Each frame is pasted
at 1x onto `BattleBackgroundNormal.png`, centred, with the cell's bottom at
y=126 like the Pokémon dioramas. They aren't mirrored, so left stays left.
150 ms per frame, looping. Rerun it after changing the background or the
sheets. GIFs have no partial transparency, so any half-transparent pixels in
the background become solid.

### URL format

```
https://vampyrevk.github.io/DSiRPC/Assets/<Folder>/<id>.gif?raw=true
```

Folder names are case-sensitive on GitHub Pages.

---

## 11. Debugging and troubleshooting

### Quick checks, in order

Quit DSiRPC (tray menu > Quit) first: these all need its UDP port.

1. `tools/hello_listener.py`: do hellos arrive? If not, it's the
   connection, not the parser.
2. `core/dsirpc_client.py`: does the SDK marker read back correctly?
3. `tools/dsi_status.py --watch 2`: are the parsed values sensible?
4. `dsirpc.py --dry-run`: what would be sent to Discord? `logs\dsirpc.log`
   has the same from the tray.

### Symptoms

| Symptom | Likely cause / fix |
|---|---|
| No hellos at all | Launcher not in DSi mode, SELECT pressed instead of START, stock nds-bootstrap launched (or a build without `DSIRPC_KEEP_DSI_WIFI`, which drops the connection), `RPCHAND.TXT` missing, the firewall blocking UDP 4244, or a network that drops broadcasts (try `--dsi-ip` with the launcher's IP) |
| Hellos arrive but reads time out | Look at the counters. `rx=0`: nothing is being received. `rx` rises but `req=0`: requests aren't recognised. `arp=0`: check `arp -a` for the DSi's IP. Also make sure no other tool holds port 4244. |
| Reads take several seconds, `Read failed: no reply` now and then, the overlay lags | Run the link check (`core\dsirpc_client.py --stats 60`, section 5). If requests "never reached the game side", the DSi's wifi chip is dropping frames because the in-game side drains it too slowly for the network's broadcast traffic. Each dropped request costs the PC a one-second timeout, and a full read is about 20 requests. Check `rxm=` in the hellos (section 7): `53` drains many frames per VBlank, `52` only one frame and 128 bytes. If it's `52` with `e53=` above 0, CMD53 failed on this console and switched itself off. If the link check says replies "never arrived" instead, look at `txm=`, `t53=` and `rep=` (sending); `RPCPROBE_TX_CMD53 0` in `rpcprobe_build.h` goes back to CMD52 sending. In battles the overlay's hub reads only the battlers either way. |
| Hellos stop at regular intervals | WPA group-key renewal. If `eap` rises right before, check the router's group-key interval. |
| "A communication error has occurred" after Continue | Stock nds-bootstrap, or not the USA Rev 1 ROM, so the patch didn't apply |
| White screen when booting the game | SD access from VBlank (a debug build, or new code touching the SD card after the first VBlank) |
| Black screen or crash when opening the party menu | A debug build is still active, often through stale object files (section 3.1) |
| First pause-menu open has graphical glitches | Known issue, still to be fixed |
| The game stutters | rpcprobe runs inside the ARM7's VBlank interrupt and drains every frame the Wi-Fi chip receives, one SDIO command per byte. Big broadcast frames from other devices used to be drained in one go, several milliseconds at a time. They're now drained 128 bytes per VBlank. Check the `vb=` field in the hellos (section 7). Also compare with DSiRPC stopped: if the stutter only happens while it polls, the replies are the cost. The DS refreshes at about 59.83 Hz, which is normal and not the cause. |
| Wrong game boots | Started our nds-bootstrap from the menu (launcher's Y): it boots what `sd:/_nds/nds-bootstrap.ini` names, the last game TWiLight or the launcher set up. Use START in the launcher |
| The launcher shows IP `0.0.0.0` | An older launcher (DHCP hadn't answered yet); the current one waits for an IPv4 address and retries |
| "This game has no save file yet" | Start the game once from TWiLight Menu++, which makes the save, then use the launcher |
| "Where is our nds-bootstrap?" | Our build isn't next to the launcher as `nds-bootstrap-dsirpc.nds` (or there are several `nds-bootstrap*.nds` there): pick it, or move it there |
| Picking a game goes back to TWiLight, or the screen stays black | Starting nds-bootstrap directly didn't work on this console (launcher/CHAINLOAD.md); Y in the launcher still exits connected the two-step way |
| Two activities in Discord | Vencord CustomRPC (or another presence tool) is still on |
| Presence stays up for a while after closing the game | Expected: DSiRPC waits for about 30 s without data before clearing it |
| "DSiRPC is already running" | Another DSiRPC (look in the tray, by the clock) or a tool from `tools/` holds UDP 4244 |
| The tray icon's dot is red | Discord isn't running, or there's no application ID (run Setup); the menu's "Discord: ..." line says which |
| Another game shows only its name | No set yet. The tray's RetroAchievements line says why (no clear title match, no connection, ...): run Setup while the game runs and pick its set (section 6, "Finding the set") |
| An achievement didn't unlock (or unlocked early) | It's checked once a second, not every frame (section 6, "RetroAchievements"). `logs\achievements.log` lists every unlock and whether it was sent |
| Unlocks say "not sent" | Sending is off (setup, step 3), you're not signed in, or it's a `--dry-run`. Ones that failed to send wait in `ra\cache\pending_unlocks.json` |
| Blank image in Discord | Asset not pushed yet, wrong folder case, or a missing ID |
| "checksum mismatch" in `tools/dsi_status.py` | The read overlapped the game editing that Pokémon; the next read is usually fine |

### Debug builds, RAM viewer and log messages

See [DEBUGGING.md](../nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/DEBUGGING.md).
**Only use debug builds for short startup checks.** nds-bootstrap's debug
logging writes to the SD card from interrupts during gameplay, which has
crashed the game. Clean debug builds compile (the GCC 14 errors in
upstream's debug-only code in `my_fat.c` and `my_sd.c` are fixed, see
section 8).

---

## 12. Known limitations and next steps

- **DS mode only.** rpcprobe lives in the ARM7 cardengine nds-bootstrap
  loads for games running in DS mode (`cardenginei_arm7`). A DSi-enhanced
  game (Pokémon Black and White, and later) running in DSi mode loads
  `cardenginei_arm7_twlsdk` instead, a 33 KB region without rpcprobe, and its
  own ARM7 code drives the DSi Wi-Fi chip there. Set those games to DS mode
  in TWiLight Menu++'s per-game settings. The per-frame capture (the ARM9's
  VBlank-start snapshot) passed on hardware on 2026-10-05: not one late read
  in menus, the overworld, battles, boot or across a soft reset.
- **Achievements are checked once a second, not every frame.** A set can
  read far more values than the per-frame capture's 8, so it's read as a
  whole every second instead (section 6, "RetroAchievements"). The capture
  could later cover the timing-sensitive values of a set. Addresses past main
  RAM (the ARM9's data TCM) can't be read at all. Sending unlocks is opt-in
  and always softcore; RetroAchievements doesn't officially support original
  hardware. No leaderboards.
- **Graphical glitches in Platinum** (for example, the first pause-menu open)
  still need fixing.
- **One-app launch is new.** START in the launcher now starts our
  nds-bootstrap directly (hbmenu's bootstub + nds-bootloader, correct
  `argv[0]`, the ini rewritten for the picked game; see
  [launcher/CHAINLOAD.md](../launcher/CHAINLOAD.md)). It still has to be
  confirmed on hardware; Y keeps the two-step way. TWiLight's per-game
  settings other than the save slot aren't applied to a game picked there.
- **Offline play is in progress.** The launcher plays without Wi-Fi, keeps
  the sets on the SD card and syncs the unlock file with DSiRPC (on hardware
  since 2026-10-07), and the in-game checker runs the set (section 8; it
  matched rcheevos exactly on PC tests, and runs on hardware since
  2026-10-08: Platinum's 101 achievements at about 1.4 passes a second).
  Saving its unlocks into `RPCUNLK.BIN` from the swiHalt hook is new and
  needs a hardware test. Unlock times don't count time asleep (the console's
  clock is only read by the launcher). The checker reads main RAM from the ARM7, so it can see values a
  frame or more late, like DSiRPC's own reads; and with a big set one pass
  takes a few frames, so a hit count of 60 takes longer than a second.
- **Group-key renewals aren't handled in game.** Nothing runs the WPA2 group
  handshake after the launcher exits. So far it hasn't caused problems; the
  `eap` counter is the early warning.
- **Platinum's own Wi-Fi is disabled** in our build (DS-mode Wi-Fi can't
  reach the network anyway).
- **nds-bootstrap's in-game menu:** closing it crashed in an early build,
  before the DSi-mode rework, and it hasn't been retested since.
- **USA Rev 1 only.** Other revisions and regions need their own patch
  addresses and memory map.
- **Latency.** With CMD52 byte-at-a-time SDIO, receiving is capped at
  `RPCPROBE_RX_BYTES_PER_VBLANK` (128) bytes and one frame per VBlank so the
  game doesn't stutter, about 7.7 KB/s, which a busy home network's
  broadcast traffic can exceed; the wifi chip then drops frames, requests
  included, and a full read that used to take about 0.7 s can take 10 s or
  more (seen in a 2026-09-26 gym battle). The in-game side now reads
  received frames with CMD53 block transfers instead (one command per
  frame, up to 8 frames a VBlank; see
  [TWL_RX_NOTES.md](../nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/TWL_RX_NOTES.md)),
  falling back to CMD52 by itself if CMD53 fails. On hardware (2026-09-27)
  that took a 60 s link check to no lost requests and a 16 ms median reply.
  Sending uses CMD53 too (on hardware: no replies lost, median 15 ms);
  `rxm=` and `txm=` in the hellos say what's in use.
- **Live position** reads 0 in some indoor maps. The presence doesn't use it.
- **Not read yet:** bag contents, PC boxes, event flags, running/biking
  state, NPC positions, and map artwork (the planned area icons). IVs and
  EVs are in the decrypted party data but not decoded yet. Leads and
  offsets are in research.md.
- **State hub:** `core/hub.py` drives everything (Discord, the overlay
  window, the tray's status). Still to come: encounter and shiny counters, a
  Nuzlocke mode, and browser-source panels for OBS. Only one process can own
  UDP 4244, so all of it has to hang off the hub.
- **Windows first.** The tray, Start with Windows and the `.bat` files are
  Windows-only; `dsirpc.py` in a console works elsewhere (with a Linux or
  macOS build of rcheevos for rich presence).

---

## 13. Repository layout

| Path | What |
|---|---|
| `README.md` | Installing and using DSiRPC |
| `docs/DEVELOPMENT.md` | Running from the source code, building, the command line and tools, releases |
| `packaging/` | The Windows download: `build_release.py` and the `README.txt`, license list and release notes it includes |
| `Setup.bat`, `DSiRPC.bat` | Setup, and DSiRPC in the tray |
| `dsirpc.py`, `app/` | DSiRPC: the command line, and the engine, tray, setup and Start with Windows |
| `ra/` | RetroAchievements set files, and `ra/cache/` (RetroAchievements' game lists, the game-file index, unlocks waiting to be sent, the unlocks you have); all gitignored |
| `third_party/rcheevos/` | Prebuilt rcheevos (RetroAchievements' rule engine), MIT, with DSiRPC's `dsirpc_offline.c` (offline play's set compiler) built in |
| `overlay/` | The stream overlay window |
| `core/`, `rpc/`, `utils/` | Python modules (section 5) |
| `tools/` | Testing tools (`dsi_status.py`, `ra_tool.py`, `frame_check.py`, `hello_listener.py`, `dsirpc_overlay.py`) and `charmap/` (hex-editor tables generated from the Gen IV charmap) |
| `Assets/` | Sprites served by GitHub Pages, plus the scripts that made them |
| `art-source/` | Affinity (`.af`) source files for the sprite backgrounds |
| `launcher/` | The DSi-mode launcher (`source/`: connecting, the file browser, the ini, starting nds-bootstrap, the sync for offline play) and `loader/` (the bootstub and nds-bootloader it starts nds-bootstrap with, GPLv2+) |
| `nds-bootstrap/` | Our modified nds-bootstrap (section 8) |
| `docs/DOCUMENTATION.md` | This file |
| `docs/research.md` | Verified research notes beyond this map, plus leads |
| `docs/HISTORY.md` | The original project log (history; parts are outdated) |
| `docs/memory-map/` | RetroAchievements code notes and ProjectPokemon breakpoints |
| `spikes/` | Stages 1-3, the early experiments |
| `dsirpc.cfg.sample` | Every setting, by hand (setup writes the real `dsirpc.cfg`, which is gitignored) |
| `logs/` | `dsirpc.log`, `achievements.log`, `state.json`, and `tools/frame_check.py --save` outputs (gitignored) |
| `.github/workflows/build.yml` | GitHub Action: builds both `.nds` files and the Windows download, publishes a release for `v*` tags |

---

## 14. History and credits

The short version of how it got here:

1. Stages 1-2 proved DSi-to-PC UDP with standalone homebrew.
2. A hand-rolled DS-mode Wi-Fi + WPA2 driver inside nds-bootstrap followed.
   It compiled but was replaced before it ever worked on hardware.
3. The approach was then turned around: the DSi-mode launcher connects with
   the console's own saved settings and hands the live connection to the
   game. Getting that to survive meant keeping the board in DSi mode,
   keeping SD access out of the VBlank interrupt, and patching Platinum's
   wireless search.
4. Stage 5 added memory requests.
5. The PC side grew from a raw-read client into the parser, the status tool
   and the Rich Presence, merged with the earlier melonDS-RPC-Suite.

The dated details are in [HISTORY.md](HISTORY.md).

Built on:

- **nds-bootstrap** (DS-Homebrew; GPLv3) as the in-game host
- **BlocksDS** and **DSWiFi** (MIT) for the launcher's DSi-mode connection
- **pret/pokeplatinum** for struct layouts, the save layout and name tables
- **RetroAchievements** code notes (game 11732) and **ProjectPokemon**'s
  breakpoints page for addresses
- **pypresence** for Discord IPC
- **PokéAPI** for the Pokémon sprites
- CREDIT to (PurpleZaffre) for the overworld assets.
