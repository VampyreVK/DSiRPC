# DSiRPC

Discord Rich Presence for Pokémon Platinum, played on a real, modded Nintendo
DSi. The DSi reads the game's memory while you play and sends it over Wi-Fi to
your PC, which shows what you're doing on Discord: where you are, your party,
your badges, and who you're battling, with animated sprites.

> **Only works with Pokémon Platinum (USA, Rev 1) at the moment.** The
> in-game patch and the memory map are specific to that version.

| Overworld (Playing) | Battle (Competing) |
|---|---|
| "Exploring Route 209", badges and Pokédex count, your trainer walking in the direction you face, your lead Pokémon, party fraction | "Battling rival Barry", "Blucifer is fighting Buizel", foe and your Pokémon as sprites (shiny-aware), HP on hover |

## TL;DR

Once everything is set up (see [Setup and build](#setup-and-build)), every play
session is:

1. On the DSi, open `dsirpc-launcher.nds` **in DSi mode** and wait for `ASSOCIATED`.
2. Press **START**. This exits but keeps the Wi-Fi connected.
3. From your menu, launch **our** nds-bootstrap build, which boots Platinum.
4. On the PC, turn off any other Rich Presence plugin (like Vencord CustomRPC), then run:
   `.venv\Scripts\python.exe dsirpc.py`
   You can also start it first and leave it running. It waits for the DSi,
   and Discord only shows something while the game is running.

To see everything the PC can read in plain text instead:
`.venv\Scripts\python.exe dsi_status.py --watch 5`

## How it works

```
DSi launcher (BlocksDS)          connects in DSi mode with the WPA2 settings saved
        |                        in DSi connection slots 4-6, writes RPCHAND.TXT
        | START (stays connected)
        v
our nds-bootstrap  --boots-->  Pokémon Platinum
  ARM7 VBlank hook (rpcprobe)
    answers "read N bytes at X"  <--- UDP 4244 --->  PC: core/ (reader + parser)
    broadcasts a hello every second                     dsirpc.py
                                                             |
                                                             v
                                                  Discord Rich Presence
```

The DSi side stays simple: it only answers "give me these bytes". Everything
else (decrypting the party, working out the location, deciding what Discord
shows) happens in Python on the PC, so new fields never need a DSi rebuild.
The full technical reference is [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md).

## Repository layout

| Path | What |
|---|---|
| `dsirpc.py` | The Rich Presence: reads the DSi every 5 s and updates Discord |
| `dsi_status.py` | Prints everything that can be read, in plain text (for testing) |
| `dsirpc_overlay.py`, `overlay/` | A pixel-art window with your party and battles, for OBS or a screen share (see [Stream overlay window](#stream-overlay-window)) |
| `core/` | DSi protocol client (`dsirpc_client.py`), RAM reader (`dsi_memory.py`), game parser (`parser.py`), name tables (`platinum_data.py`), text decoding (`charmap.py`), state hub (`hub.py`), demo data (`demo.py`) |
| `rpc/`, `utils/` | Discord (pypresence) wrapper and the hub's presence connector, config reader |
| `Assets/` | Sprites served by GitHub Pages for Discord, plus the scripts that made them |
| `launcher/` | The DSi-mode launcher that connects to Wi-Fi before the game boots |
| `nds-bootstrap/` | Modified nds-bootstrap (GPLv3) with the in-game memory server. See [nds-bootstrap/DSIRPC_CHANGES.md](nds-bootstrap/DSIRPC_CHANGES.md) |
| `docs/` | [DOCUMENTATION.md](docs/DOCUMENTATION.md) (technical reference), [research.md](docs/research.md) (verified research notes), [HISTORY.md](docs/HISTORY.md) (original project log), `memory-map/` (RetroAchievements and ProjectPokemon references) |
| `spikes/` | Early experiments (stages 1-3), kept for reference |
| `tools/charmap/` | Generates hex-editor tables (ImHex, Thingy `.tbl`) from the Gen IV charmap |
| `art-source/` | Affinity (`.af`) source files for the sprite backgrounds |
| `.github/workflows/` | GitHub Action that builds both `.nds` files and publishes releases (see [Prebuilt files and releases](#prebuilt-files-and-releases)) |

## Requirements

- A modded Nintendo DSi with TWiLight Menu++ and an SD card.
- A WPA2 network saved in DSi connection slot 4, 5 or 6 (System Settings >
  Internet > Advanced Setup).
- Pokémon Platinum (USA, Rev 1).
- A Windows PC with [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  (for building) and [Python 3](https://www.python.org/downloads/). The PC and
  the DSi must be on the same network.
- The Discord desktop app.

## Setup and build

All commands are for PowerShell, from the repo root (`C:\Projects\DSiRPC`).
Adjust the paths if you cloned somewhere else.

Steps 2 and 3 build the two DSi files. If you'd rather not build them, download
`nds-bootstrap-dsirpc.nds` and `dsirpc-launcher.nds` from the repo's Releases
page instead (see [Prebuilt files and releases](#prebuilt-files-and-releases)).

### 1. Python environment

If you already have a `.venv` from before the folder moved, running the first
command again repairs it.

```
python -m venv .venv
```
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs pypresence for Discord, and pygame-ce and Pillow for the overlay
window (the sprite scripts in `Assets/` use Pillow too).

### 2. nds-bootstrap (the in-game memory server)

```
docker run --rm -v "C:\Projects\DSiRPC\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 bash -c "sed -i '/security/d' /etc/apt/sources.list && apt-get update && apt-get install -y gcc && gcc lzss.c -o /usr/local/bin/lzss && make nightly"
```

The output is `nds-bootstrap\retail\bin\nds-bootstrap-nightly.nds`. Copy it to
your SD card, keeping it separate from TWiLight Menu++'s own copy (for example
`sd:/_nds/dsirpc/nds-bootstrap-dsirpc.nds`), so you always know which one you
are launching. The build prints a few harmless `fatal: not a git repository`
lines; that's nds-bootstrap looking for its version tag.

### 3. Launcher

```
docker run --rm -v "C:\Projects\DSiRPC\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
```

The output is `launcher\dsirpc-launcher.nds`. Copy it anywhere on the SD card.
It must be started in **DSi mode**.

Nothing else needs setting up on the SD card. The launcher writes its own
`RPCHAND.TXT` to the SD root on every run, the Wi-Fi password comes from the
DSi's saved settings, and the DSi broadcasts its hello packets, so it never
needs to know your PC's IP.

### 4. Discord application

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications)
   and name it **Pokémon Platinum**. The name is what Discord shows after
   "Playing" / "Competing in".
2. Copy `PokemonPlatinumRPC.cfg.sample` to `PokemonPlatinumRPC.cfg` and put the
   application ID in `discord_client_id`. This file is gitignored. You can
   also pass `--client-id` instead.

### 5. Sprites (GitHub Pages)

Discord loads every image from `https://vampyrevk.github.io/DSiRPC/Assets/...`,
so the `Assets/` folder has to stay at the repo root and be published with
GitHub Pages (Settings > Pages). `.nojekyll`
makes Pages serve the files as they are. New or changed sprites show up in
Discord once they are pushed. How each folder is made is described in
[docs/DOCUMENTATION.md, section 10](docs/DOCUMENTATION.md#10-sprite-assets-pipeline).

### 6. Firewall

Allow Python through the Windows firewall on private networks, or the DSi's
UDP packets never reach the scripts.

## Prebuilt files and releases

[`.github/workflows/build.yml`](.github/workflows/build.yml) builds both `.nds`
files on GitHub with the same Docker images as the commands above. It runs when
a push to `main` changes `nds-bootstrap/` or `launcher/`, on pull requests, and
on demand (Actions tab > **Build DSi files** > **Run workflow**). Each run keeps
the files as two artifacts, `nds-bootstrap-dsirpc` and `dsirpc-launcher`, which
GitHub downloads as zips.

To publish a release with both files attached, push a tag that starts with `v`:

```
git tag v0.1.0
```
```
git push origin v0.1.0
```

The release is named after the tag, gets notes generated from the commits, and
has `nds-bootstrap-dsirpc.nds` and `dsirpc-launcher.nds` attached.

## Playing

1. **Launcher:** open it in DSi mode and wait for `ASSOCIATED`. It shows the
   DSi's IP and writes `RPCHAND.TXT`. **START** exits and stays connected;
   **SELECT** disconnects first.
2. **Game:** launch our nds-bootstrap build. It boots the game named in
   `sd:/_nds/nds-bootstrap.ini`, which TWiLight Menu++ rewrites whenever you
   launch something from its game list. If the wrong game boots, launch
   Platinum from TWiLight once, then use our build again.
3. **PC:** within about 15 seconds of the game starting, the DSi broadcasts a
   hello packet every second. Run `dsirpc.py` (before or after starting the
   game). It finds the DSi on its own. If nothing is found and your network
   blocks broadcasts, pass the IP the launcher showed, for example
   `--dsi-ip 192.168.1.50`.
4. **Stopping:** `dsirpc.py` keeps running until you press Ctrl+C. When the
   game is closed it clears the presence after about 30 s and waits for the
   DSi again, so restarting the game (or Discord) needs nothing on the PC.

Only one PC tool can use UDP port 4244 at a time. To have the overlay window
and the Rich Presence together, run `dsirpc_overlay.py --discord` instead of
`dsirpc.py`.

| Tool | Use |
|---|---|
| `dsirpc.py` | The Rich Presence. `--dry-run` prints instead of sending, `--file ram_dump.bin` uses a RAM dump instead of the DSi |
| `dsi_status.py` | Everything readable, in plain text. `--watch 5` refreshes, `--json` for raw data |
| `dsirpc_overlay.py` | The stream overlay window. `--discord` also runs the Rich Presence, `--demo` plays made-up scenes |
| `core/dsirpc_client.py` | Raw memory reads, e.g. `--read 0x02000BBC:8` (should print `21 06 C0 DE DE C0 06 21`) |
| `launcher/pc/hello_listener.py` | Prints the DSi's hello packets. The first thing to run if nothing works |

## Stream overlay window

`dsirpc_overlay.py` opens a window that shows your party, and switches to a
battle view when a battle starts, in a pixel-art style inspired by the DS
games. The battle background follows the DS clock, the location (field,
cave, indoors, snow) and the weather; Pokémon slide in, lunge, flash when hit
and sink when they faint; and the bottom box shows your moves by type with PP. Banners pop up for shiny
encounters, level-ups, fainting and new badges. It draws at the DS's
256x192 and scales up by a whole number, so the pixels stay crisp. Add it to
OBS with **Window Capture**, or share the window in Discord.

```
.venv\Scripts\python.exe dsirpc_overlay.py --discord
```

| Option | Use |
|---|---|
| `--discord` | Also run the Rich Presence (don't run `dsirpc.py` at the same time) |
| `--demo` | Made-up scenes (battles, a shiny, a level-up) for styling without the DSi. **N** skips to the next scene |
| `--name Vivi` | With `--demo`: the trainer name to show |
| `--file ram_dump.bin` | Show a RAM dump |
| `--scale 4` | Window size as a multiple of 256x192 (default 3). Keys **1**-**6** change it live |
| `--chroma 00FF00` | Fill the background with a key colour, for OBS's Chroma Key filter |
| `--dsi-ip`, `--interval` | As for `dsirpc.py`; `--interval` is seconds between reads (default 2) |

**V** switches the view between automatic, party only and battle only. The
colours are all in `THEME` at the top of `overlay/ui.py`.

## Known issues and roadmap

- [ ] Fix graphical glitches present in Pokémon Platinum (for example, the
      first time the pause menu opens).
- [ ] Launch our nds-bootstrap straight from the launcher, so it's one app
      instead of two (planned in [launcher/CHAINLOAD.md](launcher/CHAINLOAD.md)).
- [ ] Location artwork for the big image, and more overworld states (running,
      biking, surfing, browsing the PC). Leads are in [docs/research.md](docs/research.md).
- [ ] Handle WPA2 group-key renewal in game, if your router ever disconnects
      the DSi on a schedule.
- [ ] Support other games and versions (only Platinum USA Rev 1 today).
- [ ] More for the state hub (`core/hub.py`, used by the overlay window):
      encounter and shiny counters, a Nuzlocke mode, browser-source panels
      for OBS.
- Platinum's own Wi-Fi features are disabled while playing through DSiRPC.

Troubleshooting is covered in [docs/DOCUMENTATION.md, section 11](docs/DOCUMENTATION.md#11-debugging-and-troubleshooting).

## Credits

- Pokémon sprites from [PokeAPI](https://pokeapi.co/)
  ([sprites repository](https://github.com/PokeAPI/sprites)).
- CREDIT to (PurpleZaffre) for the overworld assets.
- [nds-bootstrap](https://github.com/DS-Homebrew/nds-bootstrap) by DS-Homebrew
  (GPLv3), which hosts the in-game side.
- [BlocksDS](https://github.com/blocksds/sdk) and DSWiFi (MIT) for the launcher
  and the DSi-mode Wi-Fi code.
- [pret/pokeplatinum](https://github.com/pret/pokeplatinum) for struct
  layouts, the save layout and the name tables.
- [RetroAchievements](https://retroachievements.org/) code notes (game 11732)
  and [ProjectPokemon](https://projectpokemon.org/)'s notable breakpoints for
  memory addresses.
- [pypresence](https://github.com/qwertyquerty/pypresence) for Discord IPC.

## License

DSiRPC's own code is MIT licensed (see [LICENSE](LICENSE)). The
`nds-bootstrap/` folder is GPLv3 (see [nds-bootstrap/LICENSE](nds-bootstrap/LICENSE)).
Pokémon is © Nintendo / Creatures Inc. / GAME FREAK inc. This is an
unofficial fan project and isn't affiliated with or endorsed by them.
