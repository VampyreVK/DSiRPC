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
   `.venv\Scripts\python.exe dsi_battle_rpc.py`

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
    sends a hello every second                          dsi_battle_rpc.py
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
| `dsi_battle_rpc.py` | The Rich Presence: reads the DSi every 5 s and updates Discord |
| `dsi_status.py` | Prints everything that can be read, in plain text (for testing) |
| `core/` | DSi protocol client (`dsirpc_client.py`), RAM reader (`dsi_memory.py`), game parser (`parser.py`), name tables (`platinum_data.py`), text decoding (`charmap.py`) |
| `rpc/`, `utils/` | Discord (pypresence) wrapper, config reader |
| `Assets/` | Sprites served by GitHub Pages for Discord, plus the scripts that made them |
| `launcher/` | The DSi-mode launcher that connects to Wi-Fi before the game boots |
| `nds-bootstrap/` | Modified nds-bootstrap (GPLv3) with the in-game memory server. See [nds-bootstrap/DSIRPC_CHANGES.md](nds-bootstrap/DSIRPC_CHANGES.md) |
| `docs/` | [DOCUMENTATION.md](docs/DOCUMENTATION.md) (technical reference), [research.md](docs/research.md) (verified research notes), [HISTORY.md](docs/HISTORY.md) (original project log), `memory-map/` (RetroAchievements and ProjectPokemon references) |
| `spikes/` | Early experiments (stages 1-3), kept for reference |
| `tools/charmap/` | Generates hex-editor tables (ImHex, Thingy `.tbl`) from the Gen IV charmap |
| `Affinity/` | Affinity source files for the sprite backgrounds |

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

### 1. Python environment

If you already have a `.venv` from before the folder moved, running the first
command again repairs it.

```
python -m venv .venv
```
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The sprite scripts in `Assets/` also need Pillow (`.venv\Scripts\python.exe -m pip install pillow`),
but you only need that if you regenerate sprites.

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

### 4. SD card config

Copy `RPCPROBE.CFG.example` to the **root of the SD card** as `RPCPROBE.CFG`
(exact name) and set `pc_ip=` to your PC's IPv4 address (`ipconfig`). The port
defaults to 4244. No Wi-Fi password goes in this file; the DSi's saved
settings are used. The launcher writes `RPCHAND.TXT` next to it on every run.

### 5. Discord application

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications)
   and name it **Pokémon Platinum**. The name is what Discord shows after
   "Playing" / "Competing in".
2. Copy `PokemonPlatinumRPC.cfg.sample` to `PokemonPlatinumRPC.cfg` and put the
   application ID in `discord_client_id`. This file is gitignored. You can
   also pass `--client-id` instead.

### 6. Sprites (GitHub Pages)

Discord loads every image from `https://vampyrevk.github.io/DSiRPC/Assets/...`,
so the `Assets/` folder has to stay at the repo root and be published with
GitHub Pages (Settings > Pages). `.nojekyll`
makes Pages serve the files as they are. New or changed sprites show up in
Discord once they are pushed. How each folder is made is described in
[docs/DOCUMENTATION.md, section 10](docs/DOCUMENTATION.md#10-sprite-assets-pipeline).

### 7. Firewall

Allow Python through the Windows firewall on private networks, or the DSi's
UDP packets never reach the scripts.

## Playing

1. **Launcher:** open it in DSi mode and wait for `ASSOCIATED`. It shows the
   DSi's IP and writes `RPCHAND.TXT`. **START** exits and stays connected;
   **SELECT** disconnects first.
2. **Game:** launch our nds-bootstrap build. It boots the game named in
   `sd:/_nds/nds-bootstrap.ini`, which TWiLight Menu++ rewrites whenever you
   launch something from its game list. If the wrong game boots, launch
   Platinum from TWiLight once, then use our build again.
3. **PC:** within about 15 seconds of the game starting, the DSi sends a hello
   packet every second. Run `dsi_battle_rpc.py`. It finds the DSi on its own.

Only one PC tool can use UDP port 4244 at a time.

| Tool | Use |
|---|---|
| `dsi_battle_rpc.py` | The Rich Presence. `--dry-run` prints instead of sending, `--file ram_dump.bin` uses a RAM dump instead of the DSi |
| `dsi_status.py` | Everything readable, in plain text. `--watch 5` refreshes, `--json` for raw data |
| `core/dsirpc_client.py` | Raw memory reads, e.g. `--read 0x02000BBC:8` (should print `21 06 C0 DE DE C0 06 21`) |
| `launcher/pc/hello_listener.py` | Prints the DSi's hello packets. The first thing to run if nothing works |

## Known issues and roadmap

- [ ] Fix graphical glitches present in Pokémon Platinum (for example, the
      first time the pause menu opens).
- [ ] Launch our nds-bootstrap straight from the launcher, so it's one app
      instead of two (planned in [launcher/CHAINLOAD.md](launcher/CHAINLOAD.md)).
- [ ] Location artwork for the big image, and more overworld states (running,
      biking, surfing, browsing the PC). Leads are in [docs/research.md](docs/research.md).
- [ ] Show the rival's real name in rival battles (read from the save) instead
      of the trainer-class name.
- [ ] Handle WPA2 group-key renewal in game, if your router ever disconnects
      the DSi on a schedule.
- [ ] Support other games and versions (only Platinum USA Rev 1 today).
- [ ] Make clean nds-bootstrap debug builds compile (see
      [DEBUGGING.md](nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/DEBUGGING.md)).
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
