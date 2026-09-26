# DSiRPC Technical Documentation

How DSiRPC works, in detail: the parts, the network protocol, what was
changed in nds-bootstrap, the Pokémon Platinum memory map, the sprite
pipeline and troubleshooting. For setup, build and everyday use, start with
the [README](../README.md).

## TL;DR

A custom build of nds-bootstrap runs a small memory server on the DSi's ARM7,
alongside the retail game. The launcher first connects the DSi to the WPA2
network saved in connection slots 4-6 and leaves the Wi-Fi chip connected.
nds-bootstrap then boots Platinum and keeps using that connection to answer
"read these addresses" requests from the PC over UDP. On the PC, Python reads
the game state (trainer, party, location, facing, battle), decrypts and
parses it, and pushes it to Discord as Rich Presence with animated sprites.
Only Pokémon Platinum (USA, Rev 1) is supported at the moment.

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
   settings, writes sd:/RPCHAND.TXT (IP, MAC, gateway),
   START = exit without disconnecting
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
                                                                 dsi_status.py / dsirpc.py
                                                                        |
                                                                        v
                                                                 Discord (pypresence, IPC)
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

See the [README](../README.md#requirements). In short: a modded DSi with
TWiLight Menu++, a WPA2 network saved in DSi connection slot 4, 5 or 6,
Pokémon Platinum USA Rev 1, a Windows PC with Docker and Python 3 on the same
network, and the Discord desktop app.

---

## 3. Setup details

The build commands and first-time setup steps are in the
[README](../README.md#setup-and-build). This section covers the details.
Prebuilt `.nds` files come from the GitHub Action in
`.github/workflows/build.yml` (see the README's
[Prebuilt files and releases](../README.md#prebuilt-files-and-releases)).

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
| `dsirpc-launcher.nds` | Anywhere you can launch from | Must be started in **DSi mode** |
| Our `nds-bootstrap-nightly.nds` | Wherever you launch it from | Keep it separate from TWiLight's stock copy so the two don't get mixed up |
| `RPCHAND.TXT` | SD root | Written by the launcher every time; don't edit it |

That's all. There's no config file: the Wi-Fi settings come from the DSi's
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
end
```

The file needs an 8.3 name because nds-bootstrap's ARM7 file lookup only
matches short names.

### 3.3 PC side

- Python dependencies are in `requirements.txt` (pypresence).
- The Discord application ID goes in `PokemonPlatinumRPC.cfg`
  (`discord_client_id: '...'`, see the `.sample`), or pass `--client-id`.
  The bold "Playing/Competing in ..." name comes from the application's name
  in the Discord Developer Portal.
- Allow Python through the Windows firewall for UDP on private networks.

### 3.4 Sprites on GitHub Pages

Discord loads the images from `https://vampyrevk.github.io/DSiRPC/Assets/...`,
so new or changed assets only show up after they are committed and pushed.
Until then, Discord shows an empty image slot. `Assets/` must stay at the
repo root, and `.nojekyll` makes Pages serve the files as they are. See
[section 10](#10-sprite-assets-pipeline).

---

## 4. Every-session flow

1. **Launcher (DSi mode).** Wait for `ASSOCIATED`. The screen shows the IP,
   gateway, mask and MAC. Three test packets are broadcast on UDP 4242, which
   `spikes/stage1-listen/pc/listener.py` can pick up. The launcher writes
   `RPCHAND.TXT`.
2. **START.** Exits without disconnecting and returns to your menu. SELECT
   disconnects cleanly first; use it when you're not going to play.
3. **Launch our nds-bootstrap build.** It boots the game named in
   `sd:/_nds/nds-bootstrap.ini` (`NDS_PATH`). TWiLight rewrites that file
   whenever you launch something from its game list, so if you last launched
   a different game there, that game boots instead. Launch Platinum from
   TWiLight once to fix it.
4. **In game.** On the first VBlank the ARM7 side reads `RPCHAND.TXT`.
   A couple of seconds later it probes the chip and starts serving. It sends a
   gratuitous ARP so the PC learns its MAC, then broadcasts one hello packet
   per second.
   If the board was ever found in old DS mode, it waits 15 seconds for the
   game to finish booting before switching it back, which delays the first
   hello.
5. **PC.** Run `dsirpc.py` (or `dsi_status.py`). Both learn the DSi's IP
   from its first hello: `dsirpc.py` waits as long as it takes,
   `dsi_status.py` gives up after 15 s. On a network that drops broadcasts,
   pass the IP the launcher showed with `--dsi-ip`.

---

## 5. PC tools reference

All commands run from the repo root, using the virtual environment's Python
(`.venv\Scripts\python.exe`).

### `dsirpc.py` (the Rich Presence)

| Flag | Default | Meaning |
|---|---|---|
| `--client-id ID` | from `PokemonPlatinumRPC.cfg` | Discord application ID |
| `--interval S` | `5` | Seconds between reads. Discord accepts about one update per 5 s. |
| `--dry-run` | off | Print the presence instead of sending it |
| `--file ram_dump.bin` | - | Use a 4 MB RAM dump (for example from melonDS) instead of the DSi |
| `--dsi-ip IP` | auto | The IP the launcher showed. Skips waiting for a hello (needed only if your network drops broadcasts) |
| `--port N` | `4244` | UDP port. The DSi always uses 4244, so leave it |

It runs until you stop it (Ctrl+C, or SIGTERM from a service manager), so it
can be left running in the background:

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

### `dsi_status.py` (everything, human-readable)

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

### `dsirpc_overlay.py` (the stream overlay window)

A pygame window that draws a 256x192 canvas every frame and scales it up by
a whole number (nearest neighbour), for OBS Window Capture or a screen
share. It owns the state hub (`core/hub.py`), so it's the one process
talking to the DSi; `--discord` runs the Rich Presence inside it through
`rpc/presence_connector.py`, with the same rules as `dsirpc.py`. Options
and keys are in the README ([Stream overlay window](../README.md#stream-overlay-window)).

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
  at the spot `process_diorama.py` uses (x=80, bottom y=126 of its canvas);
  up to two foes are shown. They slide in at the start and on a switch. Each
  move either side uses shows as "X used MOVE!" with an animation in the
  move's type style (`overlay/effects.py`: flames, bubbles, leaves,
  lightning, ice shards, rocks, rings, wisps, claw streaks, hit sparks;
  status moves glow around the user), physical moves with a lunge; the
  target blinks and shakes when its HP drops, and a fainted one sinks into
  its platform. Moves are worked out from PP: a move whose PP went down
  since the last read was just used. Things seen in the same read play one
  after another (`MOVE_GAP_MS` apart), and the HP box holds the old value
  until the hit lands. The game's own last-move record (`B+0x527C`, so far
  checked on hardware for your side only) is only a backup, for moves PP can't show (Struggle,
  moves called by Metronome), and only after it has matched the PP twice.
  The message box shows the intro (from the battle music, the same kinds as
  in section 6), moves, switches and faints for a few seconds, and otherwise
  your Pokémon's moves, coloured by type with PP, the last one used
  highlighted. Wild vs trainer comes from the music first, since the trainer
  class read can be unknown.
- **Waiting view:** while the hub is offline.
- **Banners:** for the hub's events (DSi connected or lost, shiny encounter,
  level-up, fainted, badge, new Pokédex catch).

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

### `launcher/pc/hello_listener.py`

Prints hello packets (UDP 4244). This is the first thing to run when you
suspect the connection. See [section 7](#7-wire-protocol) for what the
numbers mean.

### Python modules

| Module | What it does |
|---|---|
| `core/dsirpc_client.py` | `DSiClient`: the UDP protocol client. It learns the DSi's IP from hellos, splits and batches reads, and retries. |
| `core/dsi_memory.py` | `DsiRam`: behaves like the 4 MB dump the parser expects (length and slicing), but fetches only the bytes that are read, in 64-byte blocks, batched per `prefetch()`. `connect()` waits up to 15 s for the DSi (used by `dsi_status.py`; `dsirpc.py` uses `DSiClient` directly and waits indefinitely). |
| `core/parser.py` | `PlatinumParser.parse()`: two prefetch batches (fixed addresses first, then everything hanging off the pointers), then decode |
| `core/platinum_data.py` | Name tables by game ID: species, moves, items, natures, 593 maps (in-game location name + map header name), badges, trainer sprites, music IDs, weather IDs (`WEATHER`), and each move's type, category and base PP (`MOVE_INFO`). Generated from the pret/pokeplatinum decompilation. |
| `core/charmap.py` | Gen IV text decoding with `PokeGen4Charmap.txt` |
| `rpc/discord_client.py` | pypresence wrapper. `update()` takes `activity_type` and `party_size` and returns whether Discord accepted it. `close()` clears the activity and disconnects, and cleans up properly even if Discord was closed in the meantime. Repeated identical errors are logged once. |
| `utils/config.py` | Reads `PokemonPlatinumRPC.cfg` |
| `core/hub.py` | `StateHub`: polls a source on its own thread, keeps the latest `Snapshot` (state, `online`, status text), calls listeners with events worked out by `diff_events()` (online/offline, battle start/end, shiny encounter, level-up, fainted, badge, Pokédex catch, map and party changes). Sources: `DsiSource`, `FileSource`. |
| `core/demo.py` | `DemoSource`: made-up states in the parser's format, looping through overworld, battles, a shiny, a level-up and an offline stretch |
| `rpc/presence_connector.py` | `DiscordConnector`: the Rich Presence as a hub listener, using `dsirpc.build_presence()` |
| `overlay/` | The overlay window: `app.py` (window and keys), `scenes.py` (views, banners, animation, move detection), `effects.py` (move animations), `backdrop.py` (battle backgrounds and weather), `ui.py` (palette, panels, HP bars, move buttons), `sprites.py` (asset conversion), `font.py` (pixel fonts) |

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

The battle kind comes from the music ID:

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
read most often during a battle; `dsirpc.py` and the hub both use it.
`dsi_status.py` shows the raw value per read, with the class in hex.

| Field | Content | Example |
|---|---|---|
| Line 2 | `<your mon> is fighting <foe>` (plus `and <foe 2>` in doubles) | Blucifer is fighting Buizel |
| Large image | Foe's front sprite on the battle diorama, shiny-aware | `Pokemon-Battle-NormalLarge/418.gif` |
| Large hover | Owner, species, level, HP | Barry's Buizel (Lv 23, 41/59 HP) |
| Small image | Your Pokémon's back sprite, shiny-aware | `Shiny-Battle-BackSmall/77.gif` |
| Small hover | Trainer name, mon, level, HP | Vivia's Blucifer (Lv 36, 52/84 HP) |

Discord hides the party fraction while the type is Competing.

"In battle" means two things: the battle pointer is valid, **and** both your
first battler and the foe's first battler decode as real Pokémon (species
1-493, level 1-100, 0 ≤ HP ≤ max HP). The pointer isn't cleared after a
battle, so the sanity check is what separates a live battle from leftovers.

---

## 7. Wire protocol

All traffic is UDP on port 4244, in both directions and from the same
source port. Multi-byte fields are **big endian**.

### Hello (DSi -> broadcast, once per second)

Sent to 255.255.255.255, so every PC on the network gets it and nothing has
to be configured.

ASCII text:

```
DSiRPC hello #N gpio=XXXX rev=XX ioen=XX last=X rx=N req=N arp=N eap=N vb=N
```

| Field | Meaning |
|---|---|
| `#N` | Packet counter |
| `gpio` | `0x04004C04` when the chip was probed. `0000` is expected; bit 8 (`0100`) would mean old DS mode. |
| `rev`, `ioen` | SDIO CCCR responses from the chip probe. `11` and `02` are normal; `ioen=00` means the chip was reset. |
| `last` | Result of the previous send: 0 OK, 1 TX overflow, other values are SDIO errors |
| `rx` | Packets drained from the chip (any kind) |
| `req` | Memory requests answered |
| `arp` | ARP replies sent |
| `eap` | EAPOL frames seen, meaning the router renewed its keys. Watch this if hellos die at regular intervals. |
| `vb` | Longest VBlank tick of the in-game side since the previous hello, in scanlines (about 64 µs each; a whole frame is 263). Single digits are normal. Values in the tens mean rpcprobe is taking enough ARM7 time to make the game stutter; lower `RPCPROBE_RX_BYTES_PER_VBLANK` in `rpcprobe_build.h`. |

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

Limits: 16 ranges and 192 bytes per request. The DSi reads at most one
incoming packet per VBlank (60 per second) and serves requests inside the
VBlank interrupt. The home network's broadcast traffic shares that queue, so
a single request takes roughly 15-400 ms. The PC client retries up to 3
times, with a 1 s timeout each.

The DSi also answers ARP requests for its own IP. It sends a gratuitous ARP
when it starts serving, so the PC can address it directly.

---

## 8. DSi side: what was changed in nds-bootstrap

`nds-bootstrap/` is upstream nds-bootstrap at commit `f5f9ea48` plus the
changes below. The full list, and how to move to a newer upstream version,
is in [nds-bootstrap/DSIRPC_CHANGES.md](../nds-bootstrap/DSIRPC_CHANGES.md).
All paths below are under `nds-bootstrap/retail/`.

| File | Change |
|---|---|
| `cardenginei/arm7/source/cardengine.c` | Includes `rpcprobe/probe_hook.h` and calls `Probe_VBlankTick()` from `myIrqHandlerVBlank` (not in the `ALTERNATIVE`/`TWLSDK` variants). Also four fixes to upstream's debug-only code. |
| `cardenginei/arm7/Makefile` | `source/rpcprobe` added to `SOURCES`; `-Os` to fit the ARM7 region. `-DDEBUG` is **off**. |
| `common/source/my_fat.c`, `common/source/my_sd.c` | Debug-only fixes so a clean `-DDEBUG` build compiles with GCC 14: a guarded `#include "nocashMessage.h"`, and `(u32)` casts on pointers passed to `dbg_hexa`. Normal builds are byte-identical. |
| `cardenginei/arm7/source/rpcprobe/` | All DSiRPC ARM7 code (next table) |
| `bootloaderi/source/arm7/main.arm7.c` | `DSIRPC_KEEP_DSI_WIFI 1`: skips the switch to DS-mode Wi-Fi so the launcher's association survives |
| `bootloaderi/source/arm7/patch_common.c` | `DSIRPC_PLATINUM_NO_WIRELESS_SEARCH 1`: for `CPUE` Rev 1 only, and only if the expected instructions are found. It patches `CommManager_InitializeSearchParty` to return immediately and `CommManager_GetAvailableConnections` to return 0 (`0x02037D48`, `0x02037DA0`). This removes the communication error after Continue. |

### `rpcprobe/` files

| File | Role |
|---|---|
| `probe_hook.c/.h` | The VBlank state machine: load files, restore DSi mode if needed, probe the chip, run (or fail). It sends hellos and services requests. |
| `twl_wifi.c/.h` | Minimal Atheros SDIO access, CMD52 only: chip probe, send one framed packet to the chip's mailbox, check for and read one received packet |
| `probe_req.c/.h` | Parses Ethernet/ARP/IPv4/UDP, answers `'R'` requests and ARP, counts EAPOL |
| `probe_net.c/.h` | Builds LLC/SNAP + IPv4 + UDP frames for the (broadcast) hellos |
| `rpcprobe_config.c/.h` | Reads `RPCHAND.TXT`; defines the UDP port (4244) |
| `rpcprobe_build.h` | `RPCPROBE_REQUESTS` (1 = answer memory requests, 0 = hellos only) |
| `DEBUGGING.md`, `TWL_RX_NOTES.md` | Debugging guide (hello fields, RAM viewer byte, debug builds) and chip notes |

The original hand-rolled DS-mode Wi-Fi + WPA2 driver (from before the
DSi-mode handoff) has been removed. It was never committed to any repository,
so the only copy is in the backup made before the cleanup. How it worked is
described in [HISTORY.md](HISTORY.md).

### Rules the ARM7 code must follow

- **Only touch the SD card on the very first VBlank.** The game reads its
  save from the SD card in thread context. Any SD access from the VBlank
  interrupt later on (a log line, a file read) can land in the middle of that
  and hang or corrupt things. This caused the white screen and the
  party-menu crash.
- **Stay small.** The cardengine ARM7 binary has a fixed-size region
  (61 KB in total, and only a few KB are free), so every addition counts.
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
gender `+0x7E` (low nibble: 0 male, 1 female).

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

1. `launcher/pc/hello_listener.py`: do hellos arrive? If not, it's the
   connection, not the parser.
2. `core/dsirpc_client.py`: does the SDK marker read back correctly?
3. `dsi_status.py --watch 2`: are the parsed values sensible?
4. `dsirpc.py --dry-run`: what would be sent to Discord?

### Symptoms

| Symptom | Likely cause / fix |
|---|---|
| No hellos at all | Launcher not in DSi mode, SELECT pressed instead of START, stock nds-bootstrap launched (or a build without `DSIRPC_KEEP_DSI_WIFI`, which drops the connection), `RPCHAND.TXT` missing, the firewall blocking UDP 4244, or a network that drops broadcasts (try `--dsi-ip` with the launcher's IP) |
| Hellos arrive but reads time out | Look at the counters. `rx=0`: nothing is being received. `rx` rises but `req=0`: requests aren't recognised. `arp=0`: check `arp -a` for the DSi's IP. Also make sure no other tool holds port 4244. |
| Hellos stop at regular intervals | WPA group-key renewal. If `eap` rises right before, check the router's group-key interval. |
| "A communication error has occurred" after Continue | Stock nds-bootstrap, or not the USA Rev 1 ROM, so the patch didn't apply |
| White screen when booting the game | SD access from VBlank (a debug build, or new code touching the SD card after the first VBlank) |
| Black screen or crash when opening the party menu | A debug build is still active, often through stale object files (section 3.1) |
| First pause-menu open has graphical glitches | Known issue, still to be fixed |
| The game stutters | rpcprobe runs inside the ARM7's VBlank interrupt and drains every frame the Wi-Fi chip receives, one SDIO command per byte. Big broadcast frames from other devices used to be drained in one go, several milliseconds at a time. They're now drained 128 bytes per VBlank. Check the `vb=` field in the hellos (section 7). Also compare with `dsirpc.py` stopped: if the stutter only happens while it polls, the replies are the cost. The DS refreshes at about 59.83 Hz, which is normal and not the cause. |
| Wrong game boots | `sd:/_nds/nds-bootstrap.ini` points at the last game TWiLight launched |
| Two activities in Discord | Vencord CustomRPC (or another presence tool) is still on |
| Presence stays up for a while after closing the game | Expected: `dsirpc.py` waits for about 30 s without data before clearing it |
| Blank image in Discord | Asset not pushed yet, wrong folder case, or a missing ID |
| "checksum mismatch" in `dsi_status.py` | The read overlapped the game editing that Pokémon; the next read is usually fine |

### Debug builds, RAM viewer and log messages

See [DEBUGGING.md](../nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/DEBUGGING.md).
**Only use debug builds for short startup checks.** nds-bootstrap's debug
logging writes to the SD card from interrupts during gameplay, which has
crashed the game. Clean debug builds compile (the GCC 14 errors in
upstream's debug-only code in `my_fat.c` and `my_sd.c` are fixed, see
section 8).

---

## 12. Known limitations and next steps

- **Graphical glitches in Platinum** (for example, the first pause-menu open)
  still need fixing.
- **Two-step launch.** START returns to the menu instead of launching our
  nds-bootstrap directly. The one-app chainload (hbmenu bootstub +
  nds-bootloader, correct `argv[0]`, optionally rewriting the ini) is
  researched in [launcher/CHAINLOAD.md](../launcher/CHAINLOAD.md) but not
  built.
- **Group-key renewals aren't handled in game.** Nothing runs the WPA2 group
  handshake after the launcher exits. So far it hasn't caused problems; the
  `eap` counter is the early warning.
- **Platinum's own Wi-Fi is disabled** in our build (DS-mode Wi-Fi can't
  reach the network anyway).
- **nds-bootstrap's in-game menu:** closing it crashed in an early build,
  before the DSi-mode rework, and it hasn't been retested since.
- **USA Rev 1 only.** Other revisions and regions need their own patch
  addresses and memory map.
- **Latency.** At most `RPCPROBE_RX_BYTES_PER_VBLANK` (128) received bytes
  per VBlank, with CMD52 byte-at-a-time SDIO, so the game doesn't stutter. A CMD53 block-transfer upgrade path is noted in
  [TWL_RX_NOTES.md](../nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/TWL_RX_NOTES.md),
  but at about 0.7 s per full read it isn't needed for Rich Presence.
- **Live position** reads 0 in some indoor maps. The presence doesn't use it.
- **Not read yet:** bag contents, PC boxes, event flags, running/biking
  state, NPC positions, and map artwork (the planned area icons). IVs and
  EVs are in the decrypted party data but not decoded yet. Leads and
  offsets are in research.md.
- **State hub:** `core/hub.py` exists and drives the overlay window.
  Still to come: encounter and shiny counters, a Nuzlocke mode, and
  browser-source panels for OBS. Only one process can own UDP 4244,
  so all of it has to hang off the hub.

---

## 13. Repository layout

| Path | What |
|---|---|
| `README.md` | Overview, setup, build and everyday use |
| `dsirpc.py`, `dsi_status.py` | The Rich Presence and the status tool |
| `dsirpc_overlay.py`, `overlay/` | The stream overlay window |
| `core/`, `rpc/`, `utils/` | Python modules (section 5) |
| `Assets/` | Sprites served by GitHub Pages, plus the scripts that made them |
| `art-source/` | Affinity (`.af`) source files for the sprite backgrounds |
| `launcher/` | The DSi-mode launcher (`source/main.c`), hello listener, chainload plan |
| `nds-bootstrap/` | Our modified nds-bootstrap (section 8) |
| `docs/DOCUMENTATION.md` | This file |
| `docs/research.md` | Verified research notes beyond this map, plus leads |
| `docs/HISTORY.md` | The original project log (history; parts are outdated) |
| `docs/memory-map/` | RetroAchievements code notes and ProjectPokemon breakpoints |
| `spikes/` | Stages 1-3, the early experiments |
| `tools/charmap/` | Hex-editor tables generated from the Gen IV charmap |
| `PokemonPlatinumRPC.cfg.sample` | Template for the Discord application ID (the real file is gitignored) |
| `.github/workflows/build.yml` | GitHub Action: builds both `.nds` files, publishes a release for `v*` tags |

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
