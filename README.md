# DSiRPC

Discord Rich Presence for Pokémon Platinum, played on a real, modded Nintendo
DSi. The DSi reads the game's memory while you play and sends it over Wi-Fi to
your PC, which shows what you're doing on Discord: where you are, your party,
your badges, and who you're battling, with animated sprites.

> **The full presence is for Pokémon Platinum (USA, Rev 1).** Any other DS
> game shows its name and box art, plus its
> [RetroAchievements](https://retroachievements.org/) rich presence
> ("Racing in Figure-8 Circuit") if you have its set file (see
> [ra/README.md](ra/README.md)).

| Overworld (Playing) | Battle (Competing) |
|---|---|
| "Exploring Route 209", badges and Pokédex count, your trainer walking in the direction you face, your lead Pokémon, party fraction | "Battling rival Barry", "Blucifer is fighting Buizel", foe and your Pokémon as sprites (shiny-aware), HP on hover |

## TL;DR

Once everything is set up (see [Setup and build](#setup-and-build); on the PC
that's just **Setup.bat**), every play session is:

1. On the PC, double-click **DSiRPC.bat**. DSiRPC sits in the tray (by the
   clock) and waits for the DSi; with "Start with Windows" on, it's already
   there. Turn off any other Rich Presence plugin (like Vencord CustomRPC).
2. On the DSi, open `dsirpc-launcher.nds` **in DSi mode** and wait for `ASSOCIATED`.
3. Press **START**. This exits but keeps the Wi-Fi connected.
4. From your menu, launch **our** nds-bootstrap build, which boots the game.

Discord only shows something while the game is running. Right-click the tray
icon to turn the Discord presence or the overlay window on and off.

## How it works

```
DSi launcher (BlocksDS)          connects in DSi mode with the WPA2 settings saved
        |                        in DSi connection slots 4-6, writes RPCHAND.TXT
        | START (stays connected)
        v
our nds-bootstrap  --boots-->  Pokémon Platinum
  ARM7 VBlank hook (rpcprobe)
    answers "read N bytes at X"  <--- UDP 4244 --->  PC: dsirpc.py (tray or console)
    broadcasts a hello every second                     core/ state hub: reader, parser,
                                                        RetroAchievements rich presence
                                                          |                  |
                                                          v                  v
                                                  Discord Rich Presence   overlay window
```

The DSi side stays simple: it only answers "give me these bytes". Everything
else (decrypting the party, working out the location, deciding what Discord
shows) happens in Python on the PC, so new fields never need a DSi rebuild.
The full technical reference is [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md).

## Repository layout

| Path | What |
|---|---|
| `Setup.bat`, `DSiRPC.bat` | First-time setup, and DSiRPC in the tray (Windows) |
| `dsirpc.py` | DSiRPC itself: `setup`, `tray`, or running in a console (see [Running it](#running-it)) |
| `app/` | The parts `dsirpc.py` puts together: the engine (hub + Discord + overlay), the tray icon, the setup wizard, Start with Windows |
| `overlay/` | A pixel-art window with your party and battles, for OBS or a screen share (see [Stream overlay window](#stream-overlay-window)) |
| `core/` | DSi protocol client (`dsirpc_client.py`), RAM reader (`dsi_memory.py`), Platinum parser (`parser.py`), name tables (`platinum_data.py`), text decoding (`charmap.py`), state hub (`hub.py`), other games (`other_game.py`), RetroAchievements sets, cache and rich presence (`ra_set.py`, `ra_cache.py`, `ra_presence.py`, `rcheevos.py`), demo data (`demo.py`) |
| `rpc/`, `utils/` | Discord: Platinum's and other games' presence, the hub connector, the pypresence wrapper; the config reader |
| `ra/` | RetroAchievements set files for other games (gitignored, see [ra/README.md](ra/README.md)) |
| `third_party/rcheevos/` | RetroAchievements' rule engine (MIT), prebuilt, for rich presence |
| `tools/` | Developer and testing tools (see [Tools](#tools)), and the charmap table generator (`tools/charmap/`) |
| `Assets/` | Sprites served by GitHub Pages for Discord, plus the scripts that made them |
| `launcher/` | The DSi-mode launcher that connects to Wi-Fi before the game boots |
| `nds-bootstrap/` | Modified nds-bootstrap (GPLv3) with the in-game memory server. See [nds-bootstrap/DSIRPC_CHANGES.md](nds-bootstrap/DSIRPC_CHANGES.md) |
| `docs/` | [DOCUMENTATION.md](docs/DOCUMENTATION.md) (technical reference), [research.md](docs/research.md) (verified research notes), [HISTORY.md](docs/HISTORY.md) (original project log), `memory-map/` (RetroAchievements and ProjectPokemon references) |
| `spikes/` | Early experiments (stages 1-3), kept for reference |
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

### 1. DSiRPC on the PC

Double-click **Setup.bat** (or run it from a console). It makes the Python
environment in `.venv` (or repairs it if the folder moved), installs the
packages (pypresence for Discord, pygame-ce and Pillow for the overlay window,
pystray for the tray icon), then asks a few questions:

1. **Discord application ID**: see [step 4](#4-discord-application).
2. **RetroAchievements** (optional): RALibretro's folder, for other games'
   rich presence. It lists the DS/DSi sets you've played there.
3. **Set files**: for the game the DSi is running right now, and any game
   code you type, it copies the matching set into `ra/`.
4. **Start with Windows**: starts DSiRPC in the tray when you sign in.

Everything goes in `dsirpc.cfg` (gitignored; `dsirpc.cfg.sample` shows every
setting). Run Setup.bat again whenever you want to change something; a
running DSiRPC picks up the changes.

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
   "Playing" / "Competing in". For other games DSiRPC also sends the game's
   name, which Discord shows instead where it can; a second application
   named like "Nintendo DS" can be the default for them.
2. Give Setup.bat the **Application ID** (General Information page). It
   saves it in `dsirpc.cfg`. You can also pass `--client-id` instead.

### 5. Sprites (GitHub Pages)

Discord loads every image from `https://vampyrevk.github.io/DSiRPC/Assets/...`,
so the `Assets/` folder has to stay at the repo root and be published with
GitHub Pages (Settings > Pages). `.nojekyll`
makes Pages serve the files as they are. New or changed sprites show up in
Discord once they are pushed. How each folder is made is described in
[docs/DOCUMENTATION.md, section 10](docs/DOCUMENTATION.md#10-sprite-assets-pipeline).

### 6. Firewall

Allow Python through the Windows firewall on private networks, or the DSi's
UDP packets never reach DSiRPC. The tray runs as **pythonw** and the console
as **python**, so Windows may ask once for each; allow both.

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
   hello packet every second, and DSiRPC (started before or after the game)
   finds the DSi on its own. The tray icon's dot turns green and Discord
   shows the game. If nothing is found and your network blocks broadcasts,
   run DSiRPC with the IP the launcher showed, for example
   `.venv\Scripts\python.exe dsirpc.py --dsi-ip 192.168.1.50`.
4. **Stopping:** DSiRPC keeps running until you quit it (tray menu > Quit, or
   Ctrl+C in a console). When the game is closed it clears the presence after
   about 30 s and waits for the DSi again, so restarting the game (or Discord)
   needs nothing on the PC. Switching games works the same way.

### Running it

| How | What |
|---|---|
| `DSiRPC.bat` | The tray icon (`dsirpc.py tray`). Right-click it for the status, **Discord presence**, **Overlay window** (a left click toggles it too), **Start with Windows**, **Setup...**, **Open log** and **Quit**. The dot is green while the game answers, amber while it waits for the DSi, red if Discord can't be reached |
| `Setup.bat` | First-time setup (`dsirpc.py setup`), safe to run again |
| `dsirpc.py` | DSiRPC in a console until Ctrl+C, logging what Discord shows |
| `dsirpc.py --overlay` | ...with the overlay window; closing it stops DSiRPC |
| `--dry-run` | Prints the presence instead of sending it to Discord |
| `--no-discord` | Nothing on Discord (for the overlay alone) |
| `--file ram_dump.bin` | A RAM dump instead of the DSi; add `--game AMCE` for a dump of another game |
| `--dsi-ip`, `--interval`, `--client-id` | The DSi's IP, seconds between reads (default 5, or 2 with the overlay), a Discord application ID for every game |

The log is `logs\dsirpc.log`. Only one DSiRPC can run at a time, and the
tools below can't run next to it: they all need UDP port 4244.

### Tools

For testing and development, run from the repo root:

| Tool | Use |
|---|---|
| `tools/dsi_status.py` | Everything readable from Platinum, in plain text. `--watch 5` refreshes, `--json` for raw data |
| `tools/ra_tool.py` | RetroAchievements set files by hand: `add`, `list`, `info`, `rp` (local only: nothing is sent to RetroAchievements) |
| `tools/dsirpc_overlay.py` | The overlay window on its own (`dsirpc.py --overlay --no-discord`); `--discord` adds the presence, `--demo` plays made-up scenes |
| `tools/frame_check.py` | Checks that the per-frame capture sees every frame (step 1 of RetroAchievements support). On Platinum it needs no options |
| `tools/hello_listener.py` | Prints the DSi's hello packets. The first thing to run if nothing works |
| `core/dsirpc_client.py` | Raw memory reads, e.g. `--read 0x02000BBC:8` (should print `21 06 C0 DE DE C0 06 21`) |

## Stream overlay window

The overlay window (tray menu > **Overlay window**, or `dsirpc.py --overlay`)
shows your party, and switches to a battle view when a battle starts, in a pixel-art style inspired by the DS
games. The battle background follows the DS clock, the location (field,
cave, indoors, snow) and the weather; Pokémon slide in, lunge, flash when hit
and sink when they faint; every move either side uses gets its "X used MOVE!" line and a
type-coloured animation; stat changes show as arrows under the HP boxes and conditions
(sleep, paralysis, confusion, ...) as markers on the Pokémon; and the bottom box shows your
moves by type with PP, how effective each one is against the foe, and the last one used
highlighted. Banners pop up for shiny
encounters, level-ups, fainting and new badges. Other games get a card with
their name and RetroAchievements rich presence. It draws at the DS's
256x192 and scales up by a whole number, so the pixels stay crisp. Add it to
OBS with **Window Capture**, or share the window in Discord.

| Option (`dsirpc.py`) | Use |
|---|---|
| `--overlay` | Open the window (console mode) |
| `--demo` | Made-up scenes (battles, a shiny, a level-up) for styling without the DSi. **N** skips to the next scene |
| `--name Vivi` | With `--demo`: the trainer name to show |
| `--scale 4` | Window size as a multiple of 256x192 (default 3, or `overlay_scale` in `dsirpc.cfg`). Keys **1**-**6** change it live |
| `--chroma 00FF00` | Fill the background with a key colour, for OBS's Chroma Key filter (`chroma` in `dsirpc.cfg`) |

While the window is open DSiRPC reads every 2 s instead of 5, and a battle's
Pokémon a few times a second. **V** switches the view between automatic,
party only and battle only. The colours are all in `THEME` at the top of
`overlay/ui.py`.

## Known issues and roadmap

- [ ] Fix graphical glitches present in Pokémon Platinum (for example, the
      first time the pause menu opens).
- [ ] Launch our nds-bootstrap straight from the launcher, so it's one app
      instead of two (planned in [launcher/CHAINLOAD.md](launcher/CHAINLOAD.md)).
- [ ] Location artwork for the big image, and more overworld states (running,
      biking, surfing, browsing the PC). Leads are in [docs/research.md](docs/research.md).
- [ ] Handle WPA2 group-key renewal in game, if your router ever disconnects
      the DSi on a schedule.
- [ ] Support other games and versions: every DS game gets its name, box art
      and RetroAchievements rich presence; only Platinum USA Rev 1 gets the
      full presence and the overlay's party and battle views.
- [ ] RetroAchievements: softcore achievements, and rich presence on the RA
      site itself (next).
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
- [pypresence](https://github.com/qwertyquerty/pypresence) for Discord IPC,
  [pystray](https://github.com/moses-palmer/pystray) for the tray icon.
- [rcheevos](https://github.com/RetroAchievements/rcheevos) (MIT) and
  RetroAchievements' set authors for other games' rich presence;
  [GameTDB](https://www.gametdb.com/) for box art.

## License

DSiRPC's own code is MIT licensed (see [LICENSE](LICENSE)). The
`nds-bootstrap/` folder is GPLv3 (see [nds-bootstrap/LICENSE](nds-bootstrap/LICENSE)).
Pokémon is © Nintendo / Creatures Inc. / GAME FREAK inc. This is an
unofficial fan project and isn't affiliated with or endorsed by them.
