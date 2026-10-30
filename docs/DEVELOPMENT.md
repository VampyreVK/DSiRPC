# Developing DSiRPC

Running DSiRPC from the source code, building the two console files, the
command line and tools, and how releases are made. For using DSiRPC, see the
[README](../README.md); for how everything works inside, see
[DOCUMENTATION.md](DOCUMENTATION.md).

## Contents

1. [Repository layout](#1-repository-layout)
2. [Requirements](#2-requirements)
3. [Running from the source code](#3-running-from-the-source-code)
4. [Building the console files](#4-building-the-console-files)
5. [Discord applications](#5-discord-applications)
6. [Sprites (GitHub Pages)](#6-sprites-github-pages)
7. [Command line](#7-command-line)
8. [Tools](#8-tools)
9. [Builds and releases](#9-builds-and-releases)
10. [Tests](#10-tests)

## 1. Repository layout

| Path | What |
|---|---|
| `Setup.bat`, `DSiRPC.bat` | First-time setup, and DSiRPC in the tray (Windows). They use a release's bundled Python (`python\`) if there is one, else the `.venv` Setup.bat makes |
| `dsirpc.py` | DSiRPC itself: `setup`, `tray`, or running in a console (see [Command line](#7-command-line)) |
| `app/` | The parts `dsirpc.py` puts together: the engine (hub + Discord + overlay), the tray icon, the setup wizard, Start with Windows |
| `overlay/` | The stream overlay window (pygame-ce) |
| `core/` | DSi protocol client (`dsirpc_client.py`), RAM reader (`dsi_memory.py`), Platinum parser (`parser.py`), name tables (`platinum_data.py`), text decoding (`charmap.py`), state hub (`hub.py`), other games (`other_game.py`), RetroAchievements: sets (`ra_set.py`, `ra_cache.py`), achievements and rich presence (`ra_game.py`, `ra_presence.py`, `rcheevos.py`), the server (`ra_api.py`, `ra_link.py`), ROM hashes (`ra_hash.py`), game titles (`game_titles.py`), offline play (`offline.py`, `console_sync.py`), save backups (`saves.py`, `save_session.py`), demo data (`demo.py`) |
| `rpc/`, `utils/` | Discord: Platinum's and other games' presence, the hub connector, the pypresence wrapper; the config reader |
| `ra/` | RetroAchievements set files (gitignored, see [ra/README.md](../ra/README.md)) |
| `third_party/rcheevos/` | RetroAchievements' rule engine (MIT), prebuilt for Windows x64, with DSiRPC's offline set compiler (`dsirpc_offline.c`) built in; how to rebuild it is in its README |
| `tools/` | Developer and testing tools (see [Tools](#8-tools)), and the charmap table generator (`tools/charmap/`) |
| `tests/`, `pytest.ini` | The tests: the console's checker, capture and idle-time write-back built for the PC against rcheevos, and the PC side against a fake DSi (see [Tests](#10-tests)) |
| `Assets/` | Sprites served by GitHub Pages for Discord and the overlay, plus the scripts that made them |
| `launcher/` | The DSi-mode launcher: connects to Wi-Fi, then starts our nds-bootstrap with the game you pick ([launcher/README.md](../launcher/README.md)) |
| `nds-bootstrap/` | Modified nds-bootstrap (GPLv3) with the in-game memory server. See [nds-bootstrap/DSIRPC_CHANGES.md](../nds-bootstrap/DSIRPC_CHANGES.md) |
| `packaging/` | The Windows download: `build_release.py`, and the `README.txt`, license list and release notes that go with it; `packaging/macos/`: the macOS app (below) |
| `docs/` | This file, [DOCUMENTATION.md](DOCUMENTATION.md) (technical reference), [research.md](research.md) (verified research notes), [HISTORY.md](HISTORY.md) (original project log), `memory-map/` (RetroAchievements and ProjectPokemon references) |
| `spikes/` | Early experiments (stages 1-3), kept for reference |
| `art-source/` | Affinity (`.af`) source files for the sprite backgrounds |
| `.github/workflows/build.yml` | The GitHub Action that builds everything and publishes releases (see [Builds and releases](#9-builds-and-releases)) |
| `.github/workflows/tests.yml` | The GitHub Action that runs the tests (see [Tests](#10-tests)) |

## 2. Requirements

- Everything in the README's [What you need](../README.md#what-you-need).
- [Python 3](https://www.python.org/downloads/) (3.9 or newer) to run DSiRPC
  from the source code.
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) to build
  the two console files. (Or take them from a release, or from the Action's
  artifacts.)
- For the full presence: Pokémon Platinum (USA, Rev 1) or Black and White
  (USA).

## 3. Running from the source code

All commands are for PowerShell, from the repo root (`C:\Projects\DSiRPC`).
Adjust the paths if you cloned somewhere else.

Double-click **Setup.bat** (or run it from a console). It makes a Python
environment in `.venv` (or repairs it if the folder moved), installs
`requirements.txt` (pypresence for Discord, pygame-ce and Pillow for the
overlay window, pystray for the tray icon), then runs the setup wizard
(`dsirpc.py setup`):

1. **Python packages**: checks them, and the rcheevos library.
2. **Discord application ID**: see [Discord applications](#5-discord-applications).
3. **RetroAchievements** (optional): signing in, showing what you play on
   your RA profile, and whether to send your unlocks.
4. **Your game files** (optional): a folder of `.nds` files, so
   RetroAchievements knows exactly which game you play.
5. **Achievement sets**: RALibretro's folder, and a set for the game the
   console is running right now or any game code you type, from
   RetroAchievements or RALibretro's cache.
6. **Save backups**: the folder for the launcher's save backups, and how
   many older versions of each save to keep.
7. **Start with Windows**: starts DSiRPC in the tray when you sign in.

Everything goes in `dsirpc.cfg` (gitignored, and with RetroAchievements
signed in it holds your login token, so keep it to yourself;
`dsirpc.cfg.sample` shows every setting). Run Setup.bat again whenever you
want to change something; a running DSiRPC picks up the changes. Then
**DSiRPC.bat** starts it in the tray.

Allow Python through the Windows firewall on private networks, or the DSi's
UDP packets never reach DSiRPC. The tray runs as `pythonw.exe` and the
console as `python.exe` (both in `.venv\Scripts`), so Windows may ask once
for each; allow both.

## 4. Building the console files

On Windows, **`BuildConsole.bat`** runs both builds below (Docker Desktop
running) and puts the files in the checkout's `SD card\DSiRPC`, where DSiRPC
run from the checkout offers them to the launcher as an update. Give it a
DSiRPC folder (`BuildConsole.bat "C:\...\DSiRPC"`) to copy them there too.

### nds-bootstrap (the in-game memory server)

```
docker run --rm -v "C:\Projects\DSiRPC\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 bash -c "sed -i '/security/d' /etc/apt/sources.list && apt-get update && apt-get install -y gcc && gcc lzss.c -o /usr/local/bin/lzss && make nightly"
```

The output is `nds-bootstrap\retail\bin\nds-bootstrap-nightly.nds`. Copy it to
the SD card as `sd:/DSiRPC/nds-bootstrap-dsirpc.nds`, away from TWiLight
Menu++'s own copy, so you always know which one you are launching (or let
the launcher take it: DSiRPC run from the source code offers its own builds
as updates). The build prints a few harmless `fatal: not a git repository`
lines; that's nds-bootstrap looking for its version tag, and the reason a
build only changes when its code does (the launcher's updates rely on it).

A test build with one of DSiRPC's pieces switched off, to find what slows a
game down on hardware, takes the switches in `DSIRPC_CFLAGS` (listed in
[nds-bootstrap/DSIRPC_CHANGES.md](../nds-bootstrap/DSIRPC_CHANGES.md): no
ARM9 half, no rpcprobe, no Wi-Fi side, no checker, stock DS-mode Wi-Fi):
add `-e DSIRPC_CFLAGS="-DDSIRPC_NO_ARM9_HOOK"` (for example) after
`docker run --rm`, and rename the output so it isn't mistaken for a normal
build. Make doesn't notice flag changes, so clean first
([DOCUMENTATION.md, section 3.1](DOCUMENTATION.md#31-build-gotcha-make-doesnt-notice-flag-changes)).

### Launcher

```
docker run --rm -v "C:\Projects\DSiRPC\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
```

The output is `launcher\dsirpc-launcher.nds` (the same command builds the
loader in `launcher/loader/` first). Copy it next to our nds-bootstrap, as
`sd:/DSiRPC/dsirpc-launcher.nds`: it looks for `nds-bootstrap-dsirpc.nds` in
its own folder. It must be started in **DSi mode**. Details are in
[launcher/README.md](../launcher/README.md).

Nothing else needs setting up on the SD card. The launcher writes its own
`RPCHAND.TXT` to the SD root on every run, the Wi-Fi password comes from the
console's saved settings, and the console broadcasts its hello packets, so it
never needs to know your PC's IP. For offline play it also makes
`RPCUNLK.BIN` and `RPCSET.BIN` in the SD root and a `sets` folder next to
itself, and finds DSiRPC with a broadcast on port 4245, or at the address
in its settings (`launcher.ini`)
([DOCUMENTATION.md, section 7](DOCUMENTATION.md#offline-play-the-launchers-sync-tcpudp-4245)).
The save sync keeps `saves.idx` next to it, and its updates `update.idx`.
Once a launcher with updates is on the SD card, DSiRPC run from the source
code offers it the builds above whenever they change
([DOCUMENTATION.md, section 7](DOCUMENTATION.md#console-updates-tcp-4245)),
so they don't need copying by hand.

## 5. Discord applications

DSiRPC shows every game through one Discord application. It sends each
game's name, which Discord shows after "Playing" / "Competing in" (the
application's own name only where Discord can't).

- **Release downloads** come with one: the Action writes the application ID
  in the repository variable `DISCORD_CLIENT_ID` (or, from when other games
  had their own, `DISCORD_DEFAULT_CLIENT_ID`) into the download's
  `defaults.cfg` (Settings > Secrets and variables > Actions > Variables).
  Application IDs aren't secret. Setup offers it as the default, and
  `dsirpc.cfg` can name another; an empty value there means "the default"
  (`utils/config.py`).
- **From the source code**, make your own: create an application in the
  [Discord Developer Portal](https://discord.com/developers/applications)
  (name it like "Nintendo DS") and give setup its **Application ID**
  (General Information page). `--client-id` overrides it for one run.

A `dsirpc.cfg` from when Platinum and the other games each had an
application (`[discord_apps]`) still works: its Platinum application is the
one, or, without it, its other games' default.

## 6. Sprites (GitHub Pages)

Discord loads every image from `https://vampyrevk.github.io/DSiRPC/Assets/...`,
so the `Assets/` folder has to stay at the repo root and be published with
GitHub Pages (Settings > Pages). `.nojekyll` makes Pages serve the files as
they are. New or changed sprites show up in Discord once they are pushed. How
each folder is made is described in
[DOCUMENTATION.md, section 10](DOCUMENTATION.md#10-sprite-assets-pipeline).

The overlay window uses the same files: from `Assets/` in a clone, and in a
release download (which only has `Assets/Consoles`) it downloads each one from
GitHub Pages the first time it's needed and keeps it in `Assets/`
(`overlay/sprites.py`). The console pictures in `Assets/Consoles` (the tray's
**Console icon**) work the same way as the sprites: any picture pushed there
shows up in the menu, and it's in the next release download.

## 7. Command line

With `.venv\Scripts\python.exe` (from the source code) or `python\python.exe`
(a release download), from DSiRPC's folder:

| How | What |
|---|---|
| `dsirpc.py tray` | The tray icon (what `DSiRPC.bat` runs, with pythonw) |
| `dsirpc.py setup` | Setup (what `Setup.bat` runs), safe to run again |
| `dsirpc.py` | DSiRPC in a console until Ctrl+C, logging what Discord shows |
| `dsirpc.py --overlay` | ...with the overlay window; closing it stops DSiRPC |
| `--dry-run` | Prints the presence instead of sending it to Discord, and sends nothing to RetroAchievements; acts as if nothing were unlocked and leaves the console's waiting unlocks on it |
| `--blank-ra` | Acts as if your RetroAchievements account had nothing unlocked (every achievement checked, whole sets for the console), still sending unlocks |
| `--clear-ra` | At the console's first sync, throws its waiting unlocks away (unsent) and sends it every set again |
| `--no-discord` | Nothing on Discord (for the overlay alone) |
| `--no-ra` | No RetroAchievements: no achievements, no downloads, nothing sent |
| `--file ram_dump.bin` | A RAM dump instead of the DSi; add `--game AMCE` for a dump of another game |
| `--dsi-ip`, `--interval`, `--client-id` | The DSi's IP (if your network drops broadcasts), seconds between reads (default 5, or 2 with the overlay), a Discord application ID for every game |
| `--demo` | The overlay with made-up scenes (battles, a shiny, a level-up, another game's card), for styling without the DSi; **N** skips to the next scene |
| `--name Vivi` | With `--demo`: the trainer name to show |
| `--scale 4` | Overlay size as a multiple of 256x192 (default 3, or `overlay_scale` in `dsirpc.cfg`) |
| `--chroma 00FF00` | Fill the overlay's background with a key colour, for OBS's Chroma Key filter (`chroma` in `dsirpc.cfg`) |

To test achievements without your real progress getting in the way, quit
DSiRPC in the tray, then run it with `--blank-ra` while you collect test
unlocks (add `tray` to run it in the tray), and with `--clear-ra` once
afterwards to put the console back to your real state (add `--blank-ra` to
give it whole sets instead). The flags combine.

The log is `logs\dsirpc.log`. Only one DSiRPC can run at a time, and the
tools below can't run next to it: they all need UDP port 4244. The overlay's
colours are all in `THEME` at the top of `overlay/ui.py`; Platinum's party
and battle views are in `overlay/scenes.py`, and the card every other game
gets is `overlay/gamecard.py`. Every option is
described in [DOCUMENTATION.md, section 5](DOCUMENTATION.md#5-pc-tools-reference).

## 8. Tools

For testing and development, run from the repo root:

| Tool | Use |
|---|---|
| `tools/dsi_status.py` | Everything readable from Platinum, in plain text. `--watch 5` refreshes, `--json` for raw data |
| `tools/ra_tool.py` | RetroAchievements set files by hand: `add`, `list`, `info`, `rp`, and `hash` (a game file's RA hash, and which RA game it is) |
| `tools/dsirpc_overlay.py` | The overlay window on its own (`dsirpc.py --overlay --no-discord`); `--discord` adds the presence, `--demo` plays made-up scenes |
| `tools/frame_check.py` | Checks that the per-frame capture sees every frame. On Platinum it needs no options |
| `tools/hello_listener.py` | Prints the DSi's hello packets. The first thing to run if nothing works |
| `tools/render_launcher.py` | Draws the launcher's modern look with its own code on the PC (the test host in `tests/c/ui`; gcc on Linux or WSL) and writes the README's pictures, `docs/images/launcher-*.svg`. Run it after changing the screens |
| `tools/make_music.py` | Makes the launcher's menu music: reads the two M8 songs (`launcher/music/*.m8s`, with `tools/m8s.py`) and writes them as XM modules (`launcher/audio/*.xm`) with the voices of their browser preview. Run it after changing a song on the M8 |
| `tools/make_pixel_dsi.py` | Makes the pixel DSi's GIFs from `overlay/ui.py`'s: Discord's "Pixel DSi" console picture (`Assets/Consoles/Pixel.gif`) and the launcher's animated icon (`launcher/icon.gif`). Run it after changing the DSi; needs pygame and Pillow |
| `tools/arm7_model/arm7_model.py` | How many ARM7 cycles the console's achievement checker takes a pass, and where they go (`--profile`), from a set in `ra/`; `--compare` a changed copy of the checker. Needs Docker (devkitARM) and `pip install unicorn`; see its [README](../tools/arm7_model/README.md) |
| `core/dsirpc_client.py` | Raw memory reads, e.g. `--read 0x02000BBC:8` (should print `21 06 C0 DE DE C0 06 21`), and `--watch` to print whatever changes in some ranges while you play |

## 9. Builds and releases

[`.github/workflows/build.yml`](../.github/workflows/build.yml) builds four
things on GitHub:

| Job | Output |
|---|---|
| `nds-bootstrap` | `nds-bootstrap-dsirpc.nds`, with the same Docker image as above |
| `launcher` | `dsirpc-launcher.nds`, with the same Docker image as above |
| `windows` | `DSiRPC-<version>-windows.zip`, the Windows download (`packaging/build_release.py`, below), on a Windows runner |
| `macos` | `DSiRPC-<version>-macos.zip`, the macOS app (`packaging/macos/build_app.py`, below), on an Apple silicon runner |

It runs when a push to any branch changes DSiRPC's files, on pull requests,
and on demand (Actions tab > **Build DSiRPC** > **Run workflow**); a newer
push to the same branch cancels the build still running for the one before
(never a tag's). Each run keeps the outputs as artifacts: `nds-bootstrap-dsirpc` and `dsirpc-launcher`, which
GitHub downloads as zips, and the two downloads' own zips
(`DSiRPC-<version>-windows.zip`, `DSiRPC-<version>-macos.zip`), uploaded as
they are (`archive: false`), so they download as one zip, not a zip in a zip.

To publish a release, push a tag that starts with `v`:

```
git tag v0.4.0
```
```
git push origin v0.4.0
```

The release is named after the tag. Its notes start with
`packaging/RELEASE_NOTES.md` (how to install), followed by notes generated
from the commits, and it has the Windows and macOS zips and both `.nds` files attached.

### The Windows download

`packaging/build_release.py` makes the zip: one `DSiRPC` folder with

- DSiRPC's files (`dsirpc.py`, `app/`, `core/`, `overlay/`, `rpc/`, `utils/`,
  `tools/`, `third_party/rcheevos/`, `Assets/Consoles/`, the two `.bat` files);
- `python/`: Python's embeddable package for Windows x64 (`PYTHON_VERSION` in
  the script), its `._pth` file set up to find `Lib\site-packages` and
  DSiRPC's folder, and the packages from `requirements.txt` installed there as
  Windows wheels;
- `SD card/DSiRPC/` with both `.nds` files (for the first copy to the SD
  card, and the launcher's updates after that);
- `README.txt` (`packaging/README.txt`, the plain-text steps), `version.txt`,
  `licenses/` (`packaging/THIRD-PARTY.txt` and nds-bootstrap's GPLv3), and
  `defaults.cfg` when Discord application IDs are given.

It can run on any PC with Python and internet access, for example to try a
download before tagging:

```
python packaging\build_release.py --nds-dir <folder with both .nds files> --version test --check
```

`--check` (Windows only) starts the bundled Python once and imports
everything DSiRPC uses. The zip goes in `dist\`; `--discord-client-id` (or
the `DISCORD_CLIENT_ID` environment variable) writes `defaults.cfg`.

The zip holds no settings, sets or logs, so unzipping a newer one over an
older folder updates DSiRPC and keeps the user's `dsirpc.cfg`, `ra\` and
`logs\`.

### The macOS app

`packaging/macos/build_app.py` makes `DSiRPC.app` with PyInstaller
(`packaging/macos/DSiRPC.spec`; the two `.nds` files go inside it too, for
the launcher's updates) and zips it with the same `SD card` folder,
`licenses/` (plus `THIRD-PARTY-macOS.txt`) and its own `README.txt`. On a Mac
with Apple silicon, from the repo root:

```
python -m pip install -r requirements.txt pyinstaller certifi
```
```
python packaging/macos/build_app.py --nds-dir <folder with both .nds files> --version test
```

It builds `third_party/rcheevos/librcheevos.dylib` first if it isn't there
(rcheevos' tag `RCHEEVOS_TAG` from GitHub plus `dsirpc_offline.c`, with the
system's `cc`), writes `defaults.cfg` like the Windows build, and runs the
built app once with `selfcheck` (`packaging/macos/dsirpc_app.py`, the app's
entry point: it imports everything and loads rcheevos). The zip goes in
`dist/`.

How the app differs from the Windows download:

- It's a menu bar app (`LSUIElement`), started as `dsirpc.py tray`, with the
  icon set in `Assets/icons` (`adaptive.icns`).
- It writes nothing inside itself: `core/paths.py`'s `DATA` is
  `~/Library/Application Support/DSiRPC` there (dsirpc.cfg, logs, `ra/`, the
  downloaded sprites).
- macOS wants the menu bar and every window on the main thread, so the tray's
  overlay window is a process of its own (`overlay/remote.py`), and changes to
  the icon and menu go through `app/tray.py`'s `on_main`.
- Setup runs in Terminal (a `.command` file in the data folder runs the app
  with `setup`), by itself the first time; Open at Login is a launch agent
  (`app/startup.py`).
- It has no Developer ID signature (PyInstaller signs it ad hoc), so the first
  launch needs right-click > Open, and macOS may ask for Local Network access
  again after each update. HTTPS uses `certifi`'s certificates.

## 10. Tests

[`tests/`](../tests/README.md) checks what decides whether an achievement is
missed: nds-bootstrap's achievement checker, per-frame capture and idle-time
write-back (built for the PC with gcc, with AddressSanitizer and UBSan on)
against rcheevos frame by frame, the launcher's save sync, updates,
playtimes and modern look's screens (built for the PC), and DSiRPC's side
(the offline formats, the launcher's sync, the protocol client, the
Black/White parser, the hub) against a fake DSi on the loopback network.
From the repo root:

```
python -m pip install -r tests/requirements.txt
```
```
python -m pytest
```

The C parts need Linux (or WSL) and gcc, and the checker tests need the
rcheevos library; [tests/README.md](../tests/README.md) has the details.
[`.github/workflows/tests.yml`](../.github/workflows/tests.yml) runs them
all on GitHub whenever a push or pull request changes `core/`, `tools/`,
`tests/`, `third_party/` or `nds-bootstrap/retail/`, building rcheevos from
its tag first (cached), and once more for the checker library with
AddressSanitizer's runtime preloaded.
