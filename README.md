# DSiRPC

#### Discord Rich Presence for games played on a real, modded Nintendo DSi or 3DS.
While you play, the console reads the game's memory and sends it over Wi-Fi
to your PC, which shows what you're doing as your Discord status.

**Pokémon Platinum (USA, Rev 1)** gets the full presence: where you are, your
party, your badges, and who you're battling, with animated sprites.
**Pokémon Black and White (USA)** get their own presence and overlay views
too. **Any other DS game** shows its name, box art and a picture of your
console, plus its [RetroAchievements](https://retroachievements.org/) rich
presence ("Racing in Figure-8 Circuit") when it has one. Every game's
achievements are checked while you play, even offline, and an optional
overlay window shows your party and battles (or any other game's progress)
for streaming.

| Overworld (Playing) | Battle (Competing) |
|---|---|
| "Exploring Route 209", badges and Pokédex count, your trainer walking in the direction you face, your lead Pokémon, party fraction | "Battling rival Barry", "Blucifer is fighting Buizel", foe and your Pokémon as sprites (shiny-aware), HP on hover |

**Using DSiRPC:** [What you need](#what-you-need) ·
[Install](#install) · [Playing](#playing) · [The tray icon](#the-tray-icon) ·
[RetroAchievements](#retroachievements) · [Playing offline](#playing-offline) ·
[Stream overlay window](#stream-overlay-window) ·
[Troubleshooting](#troubleshooting) ·
[Updating and removing](#updating-and-removing) · [Known issues](#known-issues)\
**For developers:** [Running from the source code](#running-from-the-source-code) ·
[Building the console files](#building-the-console-files) · [Tests](#tests) ·
[Testing options](#testing-options) · [Releases](#releases)\
**How it works:** [The pieces](#the-pieces) ·
[Why the console only serves memory](#why-the-console-only-serves-memory) ·
[Achievements on the console](#achievements-on-the-console) ·
[DS mode, and the Wi-Fi](#ds-mode-and-the-wi-fi) · [Roadmap](#roadmap) ·
[Credits](#credits) · [License](#license)

## Using DSiRPC

### What you need

- A **DSi or 3DS with [TWiLight Menu++](https://github.com/DS-Homebrew/TWiLightMenu)**
  installed, and your games as `.nds` files on its SD card.
- The console's **Wi-Fi set up** for the same network as your PC. On a DSi, a
  WPA2 network has to be saved in connection 4, 5 or 6 (System Settings >
  Internet > Connection Settings > Advanced Setup).
- A **64-bit Windows 10 or 11 PC**, or a **Mac with Apple silicon** (M1 or
  later, macOS 12+), with the **Discord** desktop app.

### Install

1. Download **`DSiRPC-<version>-windows.zip`** from the
   [Releases page](https://github.com/VampyreVK/DSiRPC/releases/latest). It
   has everything: DSiRPC with its own copy of Python (nothing to install),
   the two files for your SD card, and a `README.txt` with these steps.
2. **On the PC:** unzip it somewhere you can write to (Documents, the
   Desktop; not Program Files). If Windows says it "protected your PC",
   right-click the zip > Properties > tick **Unblock**, and unzip it again.
3. Double-click **`Setup.bat`** and answer its questions; Enter takes the
   suggested answer. If the download comes with a Discord application, press
   Enter there too. Signing in to RetroAchievements is optional.
4. Double-click **`DSiRPC.bat`**. DSiRPC's icon appears in the taskbar's
   notification area, by the clock. When Windows asks about the firewall,
   allow access on **private networks**, or DSiRPC never hears from the
   console.
5. **On the SD card:** copy the `DSiRPC` folder from the zip's `SD card`
   folder to the root of the card, so you have `sd:/DSiRPC/dsirpc-launcher.nds`
   and `sd:/DSiRPC/nds-bootstrap-dsirpc.nds`. Keep the two together.

#### On a Mac

Download **`DSiRPC-<version>-macos.zip`** instead and drag **DSiRPC.app**
into Applications. It isn't signed with an Apple developer account, so open
it the first time with right-click > **Open** (or System Settings > Privacy &
Security > **Open Anyway**). Its icon appears in the menu bar, and setup
opens in Terminal the first time (the same questions as `Setup.bat`). Allow
it on the **local network** when macOS asks, or it never hears from the
console. The SD card files are the same as above. Its settings, log and
achievement sets are in `~/Library/Application Support/DSiRPC`. The zip's
`README.txt` has the details.

### Playing

1. **PC:** start DSiRPC (`DSiRPC.bat`), or turn on **Start with Windows** in
   its menu so it's always there. Turn off any other Rich Presence plugin
   (like Vencord's CustomRPC), or Discord shows two activities.
2. **Console:** open `DSiRPC/dsirpc-launcher.nds` from TWiLight Menu++. It
   connects to Wi-Fi in DSi mode (it tries up to 3 times by itself) and shows
   the console's IP address. If it says it's running in DS mode, set it to
   DSi mode in TWiLight Menu++'s per-game settings. Away from your PC? Press
   **B** while it connects to [play offline](#playing-offline).
3. Press **START** and pick your game: **A** opens a folder or picks the game,
   **B** goes up a folder (the browser opens in `roms/nds`, or in the
   `DSiRPC` folder if there's no `roms/nds`). The launcher starts it, still
   connected.
   (**SELECT** disconnects and goes back instead.)
4. Within about 15 seconds, Discord shows what you're playing, and the tray
   icon's dot turns green.

A game you've never started from TWiLight Menu++ has no save file yet; the
launcher says so. Start it once from TWiLight Menu++, then use the launcher.

When you close the game, DSiRPC clears the presence after about 30 seconds and
waits for the console again, so switching games or restarting needs nothing
on the PC.

nds-bootstrap's in-game menu (**L + Down + SELECT** by default) says
**nds-bootstrap-DSiRPC** at the bottom when the game runs on DSiRPC's
nds-bootstrap, and just "nds-bootstrap" on TWiLight Menu++'s own.

### The tray icon

Right-click it for the menu:

| Item | What |
|---|---|
| The first lines | What's running, what Discord shows, and your RetroAchievements progress |
| **Discord presence** | Show the game on Discord, or not |
| **Console icon** | The picture Discord shows for games without their own presence: DSi XL, New 3DS, or none |
| **Overlay window** | The stream overlay (a left click on the icon toggles it too) |
| **Start with Windows** | Start DSiRPC in the tray when you sign in (**Open at Login** on a Mac) |
| **Setup...** | Runs setup again, to change an answer (in Terminal on a Mac) |
| **Open log** / **Open DSiRPC folder** | `logs\dsirpc.log`, and the folder DSiRPC is in (on a Mac, the folder with its settings) |
| **Quit** | Stops DSiRPC |

The dot is green while the game answers, amber while DSiRPC waits for the
console, and red if Discord can't be reached (or there's no Discord
application yet). On a Mac the icon is in the menu bar, with the same menu;
a click opens it.

### RetroAchievements

DSiRPC checks a game's achievements against the console's memory with
[rcheevos](https://github.com/RetroAchievements/rcheevos), RetroAchievements'
own library. When you unlock one you get a notification and a banner in the
overlay window, and it's added to `logs\achievements.log`.

Each game's achievements and rich presence come in a *set*, kept in the `ra`
folder. Sets come from:

- **RetroAchievements itself**, once you've signed in with `Setup.bat` (only a
  login token is saved, never your password). DSiRPC works out which game is
  running and downloads its set by itself. Setup can also take a folder of
  your game files (for example the ones you play in RALibretro): with it,
  DSiRPC knows the exact game and version, the way RA emulators do. Without
  it, DSiRPC goes by the game's title, and setup can pick a set for a game it
  can't tell (search by name).
- **RALibretro's cache**: RALibretro keeps the set of every game you've
  played in it, and DSiRPC can copy them from there, without an account.

Signed in, DSiRPC also shows what you're playing on your RetroAchievements
profile, and Discord's hover text shows your progress ("12 of 132
unlocked"). **Sending your unlocks to RetroAchievements is a separate choice
in setup**, off unless you turn it on, and always softcore:

- Not every achievement is checked every frame like on an emulator (how
  it's done is under [Achievements on the console](#achievements-on-the-console)).
  Achievements about things that last (a flag set, a cup won) work the same
  either way; ones about split-second moments, when they aren't checked
  every frame, can unlock late, not at all or, rarely, when they shouldn't.
- RetroAchievements doesn't officially support playing on original hardware.
  DSiRPC tells it honestly what it is, so it only ever counts these unlocks
  as softcore.

Unlocks that can't be sent right away (no internet) are kept and sent later.

A game started from the DSiRPC launcher is also checked by the console
itself (it's what makes [offline play](#playing-offline) work). DSiRPC then
leaves the achievements the console checks to it, and checks only the rest.
When DSiRPC hears the console unlock an achievement, that counts right away,
like its own unlocks (the log says `by the console's checker`), and DSiRPC
tells the console about the ones it unlocked itself, so nds-bootstrap's
in-game menu shows those too.

### Playing offline

Away from your PC (or your Wi-Fi), the launcher still starts your games: press
**B** while it connects, or **START** when it says it couldn't connect. Wi-Fi
stays off and the game runs as usual, just without Discord or the overlay.
Your achievements still count: the console checks them itself, Wi-Fi or not.

Whenever the launcher is connected and DSiRPC is running, it syncs with it,
once when it connects and again when you start a game (**B** skips that):

- DSiRPC sends it the [achievement sets](#retroachievements) you have, and
  downloads the set of the game you're starting if it can. The launcher keeps
  them in `sd:/DSiRPC/sets`, each with only the achievements you haven't
  unlocked yet, already turned into what the console runs (DSiRPC does that
  with rcheevos, RetroAchievements' own library).
- The launcher hands DSiRPC the achievements unlocked while playing offline,
  and DSiRPC sends them to RetroAchievements (if sending unlocks is on in
  setup), with the time you unlocked them, and tells you in a notification.

Each unlock is saved to the SD card (`sd:/RPCUNLK.BIN`) right away, with
when it happened, read from the console's clock (so a nap with the lid
closed doesn't make an unlock look older than it is). The next time the
launcher finds DSiRPC it hands them over, and DSiRPC sends the ones it
didn't already have. This works for games started from the launcher, which
puts the set and the unlock file on the SD card. With Wi-Fi and DSiRPC
running, the console also reports to DSiRPC's log (`Console: its checker
unlocked achievement ...`, `Console: saved 1 unlock(s) to its SD card for
DSiRPC`), next to DSiRPC's own unlocks, so the two can be compared.

nds-bootstrap's in-game menu shows them, on a DSi and on a 3DS. When you
open it, it says how many new achievements there are since you last looked,
with their names, and how many of the game's you've earned. Its
**Achievements** item lists them all: the ones you've earned first, newest
first with the date and time (in lime if this console earned it and DSiRPC
hasn't had it yet, with NEW on the new ones), then the ones still to get,
with the highlighted one's description at the bottom. Up/Down move, L/R
turn the page, B goes back. The list comes with the set at each sync, so it
includes what you'd already earned on RetroAchievements.

On a DSi, an LED shows new unlocks too: the one picked by TWiLight Menu++'s
**ROM read LED** setting (`ROMREAD_LED` in `nds-bootstrap.ini`: the Wi-Fi,
power or camera LED) pulses while there are achievements from this game you
haven't seen yet (the power LED pulses purple). Opening the in-game menu
counts as seeing them. It's also a quick way to tell the console's checker
is working without DSiRPC. With DSiRPC's nds-bootstrap that LED no longer
flashes for ROM reads; set the setting to None to turn the achievement LED
off. A 3DS has no LED for this (TWiLight Menu++ has no LED setting there);
the in-game menu shows the new unlocks instead.

### Stream overlay window

The overlay window (tray menu > **Overlay window**) shows your party, and
switches to a battle view when a battle starts, in a pixel-art style inspired
by the DS games. The battle background follows the DS clock, the location
and the weather; Pokémon slide in, flash when hit and sink when they faint;
every move gets its "X used MOVE!" line and an animation that fits it (a
fist for punches, jaws for fangs, a wave for Surf, a quake that shakes the
screen, ...) in its type's colours; stat changes and conditions show on the
HP boxes and Pokémon; and the bottom box shows your moves with PP and how
effective each one is. Banners pop up for shiny encounters, level-ups,
fainting, new badges and achievements.

Pokémon Black and White (US) get a view of their own, in the games' look:
the party in the party screen's panels, an achievements panel with your
latest unlock and the next one to earn, your trainer, money and the Unova
badges, the season, and battles in the games' own style (their HUD, a
background with Black and White's detail, the field's weather, the game's
clock for day and night, and Gym Leaders, the Elite Four and the Champion
named and making their entrance). The view dresses for Unova's seasons
(petals, sun rays, falling leaves, snow piling up), shows your Repel steps
and the trainers and items left where you are, your badges as polished as
on your trainer card, and panels of their own in the Battle Subway, the
Battle Institute and the Elite Four's rooms; catches get a "Gotcha!".
Discord shows the foe standing on the same turf as the battle view and
your trainer walking on the place's turf. (If the game's memory doesn't
look right, for example another region's version, they get the game card.)

Every other game gets a game card in the same style: its name and how long
you've been playing, what you're doing in it (its RetroAchievements rich
presence), a progress bar for its achievements with your latest unlock and
one still to earn side by side, and how many achievements and points you
have. While the console isn't connected, the window says what to do and
shows the last game you played.

It draws at the DS's 256x192 and scales up by a whole number, so the pixels
stay crisp. Add it to OBS with **Window Capture**, or share the window on
Discord. Keys **1**-**6** change its size, and **V** opens the party screen
(all six Pokémon with their moves, PP, nature and held item; the window's
title says when it's showing) and goes back again: to the battle during a
battle, otherwise to the main view. A battle starting or ending always goes
back to its own view. For OBS's Chroma Key filter, set `chroma` (a colour
like `00FF00`) in `dsirpc.cfg`. The sprites are downloaded the first time
they're needed, then kept.

### Troubleshooting

| Problem | Try |
|---|---|
| Nothing on Discord | Right-click the tray icon: its first lines say what DSiRPC sees. The PC and the console must be on the same network, and the firewall must allow DSiRPC on private networks (Windows Security > Firewall > Allow an app: `python.exe` and `pythonw.exe` in DSiRPC's `python` folder). |
| The tray dot is red | Discord isn't running, or there's no Discord application yet: run setup. |
| The launcher can't connect | Check the console's Wi-Fi settings (on a DSi, WPA2 needs connection 4, 5 or 6). |
| DSiRPC says "Starting" the game, but it never connects, and the in-game menu has no achievements | Use the launcher from the same release as `nds-bootstrap-dsirpc.nds`: older launchers left DSi-enhanced games (like Pokémon Black and White) in DSi mode, where DSiRPC doesn't run. The in-game menu should say **nds-bootstrap-DSiRPC**. |
| The in-game menu says just "nds-bootstrap" | That's TWiLight Menu++'s own nds-bootstrap: start the game from the DSiRPC launcher. |
| Discord stopped after the DSi's lid was closed | That's on purpose: the console turns its Wi-Fi off when the lid closes, because a DSi that sleeps while connected switches itself off. Achievements are still checked and saved. Start the game from the launcher again to reconnect. |
| The launcher says "DSiRPC wasn't found" or "can't be reached" | DSiRPC isn't running, or the firewall blocks it (the same fix as "Nothing on Discord"; the sync uses port 4245). The game still starts; unlocks wait on the SD card until the next sync. |
| "This game has no save file yet" | Start the game once from TWiLight Menu++, then use the launcher again. |
| Two activities on Discord | Another Rich Presence tool (like Vencord's CustomRPC) is still on. |
| A game shows only its name | It has no achievement set yet; the tray menu's RetroAchievements line says why. Run setup while the game runs to pick its set. |
| The in-game menu says "no set loaded" or "another game's" | Start the game with **START** in the launcher (not **Y**, and not from TWiLight Menu++): that's what puts its set on the SD card. |

More, including what the console sends and how to read it, is in
[docs/DOCUMENTATION.md, section 11](docs/DOCUMENTATION.md#11-debugging-and-troubleshooting).
The log is `logs\dsirpc.log` in DSiRPC's folder.

### Updating and removing

To update, unzip the new release over your DSiRPC folder (replace the files
when asked): your settings (`dsirpc.cfg`) and achievement sets stay. Copy the
new SD card files over the old ones too: the two go together. To remove
DSiRPC, turn off **Start with Windows**, quit it, and delete its folder.

### Known issues

- Games' own Wi-Fi features don't work while playing through DSiRPC (the
  console's Wi-Fi is DSiRPC's while you play).
- DSi-enhanced games (Pokémon Black and White, and later) run in DS mode
  when started from the launcher, so their DSi-only extras are off
  ([why](#ds-mode-and-the-wi-fi)).
- On a DSi, closing the lid turns the console's Wi-Fi off until a game is
  started from the launcher again (a DSi that sleeps while connected
  switches itself off). Achievements are still checked and saved for the
  next sync.
- Achievements about split-second moments can unlock late or not at all
  when they can't be checked every frame (see
  [RetroAchievements](#retroachievements)).

## For developers

Everything here is in more detail in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
(running, building, tools, releases) and the technical reference,
[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md). The console side is a
modified [nds-bootstrap](nds-bootstrap/DSIRPC_CHANGES.md) (GPLv3) and the
launcher in [launcher/](launcher/README.md); the PC side is Python, in
`app/`, `core/`, `overlay/` and `rpc/`.

### Running from the source code

On Windows, **Setup.bat** makes a Python environment in `.venv`, installs
`requirements.txt` and runs the setup wizard; **DSiRPC.bat** then starts
DSiRPC in the tray. To run it in a console instead, logging what Discord
shows (Ctrl+C stops it):

```
.venv\Scripts\python.exe dsirpc.py
```

`dsirpc.py --overlay` adds the overlay window, and `dsirpc.py --demo` plays
made-up scenes in it without a console. Every option is in
[DEVELOPMENT.md, section 7](docs/DEVELOPMENT.md#7-command-line).

### Building the console files

Both build in Docker. nds-bootstrap (the output is
`nds-bootstrap\retail\bin\nds-bootstrap-nightly.nds`; rename it
`nds-bootstrap-dsirpc.nds`):

```
docker run --rm -v "C:\Projects\DSiRPC\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 bash -c "sed -i '/security/d' /etc/apt/sources.list && apt-get update && apt-get install -y gcc && gcc lzss.c -o /usr/local/bin/lzss && make nightly"
```

The launcher (the output is `launcher\dsirpc-launcher.nds`):

```
docker run --rm -v "C:\Projects\DSiRPC\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
```

Both go in `sd:/DSiRPC/`, side by side ([DEVELOPMENT.md, section 4](docs/DEVELOPMENT.md#4-building-the-console-files)).

### Tests

[tests/](tests/README.md) checks what decides whether an achievement is
missed: the console's checker, per-frame capture and idle-time write-back
(built for the PC with the sanitizers on) against rcheevos frame by frame,
the launcher's settings for nds-bootstrap, and DSiRPC's side (the offline
formats, the launcher's sync, the protocol client, the Black/White parser,
the hub) against a fake DSi. GitHub runs them on every change to that code
([tests.yml](.github/workflows/tests.yml)). Locally:

```
python -m pip install -r tests/requirements.txt
```
```
python -m pytest
```

The C parts need Linux (or WSL) and gcc; the rest runs anywhere with the
rcheevos library ([tests/README.md](tests/README.md)).

### Testing options

For testing achievements without your real progress getting in the way,
DSiRPC takes these flags. Quit it in the tray first, then run it from its
folder in a command prompt: `python\python.exe dsirpc.py` in a release
download, `.venv\Scripts\python.exe dsirpc.py` from the source code (add
`tray` to run it in the tray). The flags combine.

| Flag | What it does |
|---|---|
| `--dry-run` | Sends nothing anywhere: the Discord presence is logged instead, and nothing goes to RetroAchievements. DSiRPC acts as if your account had nothing unlocked (like `--blank-ra`), and unlocks waiting on the console stay there (the launcher says so). |
| `--blank-ra` | Acts as if your RetroAchievements account had nothing unlocked: every achievement is checked, the console gets whole sets, and every unlock is sent (RetroAchievements answers that you already had the ones you had). What's really unlocked stays recorded in `ra\cache\unlocked.json`. |
| `--clear-ra` | At the console's first sync, throws away the unlocks waiting on it (nothing is sent) and sends it every set again. Later syncs in the same run are normal. |

For example, `python\python.exe dsirpc.py --blank-ra` while you collect
test unlocks, then `python\python.exe dsirpc.py --clear-ra` once to put the
console back to your real state (add `--blank-ra` to give it whole sets
instead).

### Releases

[`build.yml`](.github/workflows/build.yml) builds both console files, the
Windows download and the macOS app on GitHub, from the same commit: on every
push to `main` that changes DSiRPC's files, on pull requests, and from the
Actions tab. Pushing a tag that starts with `v` (for example `v0.4.0`) also
publishes a release with all four
([DEVELOPMENT.md, section 9](docs/DEVELOPMENT.md#9-builds-and-releases)).

## How it works

### The pieces

```
Console: dsirpc-launcher.nds     connects to Wi-Fi in DSi mode, then starts the
        |                        game you pick with our nds-bootstrap, still connected
        v
our nds-bootstrap  --boots-->  the game
  a small memory server in its ARM7 code
    answers "read N bytes at X"  <--- UDP 4244 --->  PC: DSiRPC (tray)
    broadcasts a hello every second                     reads and decodes the game's state,
  the achievement checker, for offline play             checks achievements
                                                          |                  |
                                                          v                  v
                                                  Discord Rich Presence   overlay window
```

The launcher also syncs with DSiRPC on port 4245 (UDP to find it, then TCP),
for [offline play](#playing-offline): sets one way, unlocks the other.

### Why the console only serves memory

The console side stays simple: it only answers "give me these bytes" (and,
for offline play, runs the achievement program DSiRPC prepares). Everything
else (decrypting the party, working out the location, deciding what Discord
shows) happens on the PC, so new features never need a console update. The
code that does run on the console lives in the game's second processor, the
ARM7, alongside nds-bootstrap's own, and does its work in a short turn each
frame and in time the game leaves free, so games run at their usual speed
(Pokémon Black's battle loads take as long as without it).

### Achievements on the console

RetroAchievements' rules are checked once a frame on an emulator, and many
compare a value with the frame before, count frames, or reset on a single
slip, so a checker that looks only now and then misses them. The console
checks each game's set itself, in two lanes: the achievements that need it
(a move that only counts on the exact frame it happens, a challenge that one
slip resets) every frame, from values the ARM7 reads at the start of every
frame; the rest in passes, many times a second. Small sets are checked every
frame whole, big ones as many as fit. DSiRPC builds both lanes from the set
with rcheevos, so the console checks exactly what RetroAchievements would,
and the tests compare the two frame by frame.

The checking runs in the ARM7's idle time (when the game's second processor
waits for its next job), never in the time the game needs. The game itself
runs on the other processor, the ARM9, whose cache holds its latest writes
back from memory for a while; DSiRPC's part of nds-bootstrap has it write
them out whenever the game is idle, so the ARM7 always reads the frame's
values, not last frame's. DSiRPC itself checks every frame as many of the
rest as fit in the eight values the console can record each frame, and the
others about once a second.

### DS mode, and the Wi-Fi

nds-bootstrap runs a game in DS mode or DSi mode, with a different engine for
each, and DSiRPC's part (the memory server, the checker, the in-game menu's
achievements) is only in the DS-mode one. So the launcher starts DSi-enhanced
games in DS mode, whatever TWiLight Menu++ last chose; DSi-exclusive games
can only run in DSi mode. The console's Wi-Fi stays in DSi mode throughout,
so the connection the launcher makes (WPA2 included) carries on into the
game; that's also why games' own Wi-Fi features don't work.

The full technical reference, from the protocol to the memory maps, is
[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md); what was changed in
nds-bootstrap is in [nds-bootstrap/DSIRPC_CHANGES.md](nds-bootstrap/DSIRPC_CHANGES.md),
and the story of how it got here in [docs/HISTORY.md](docs/HISTORY.md).

### Roadmap

- [x] One app on the console: the launcher connects and starts the game.
- [x] A Windows download that needs nothing installed, and a macOS app.
- [x] RetroAchievements: achievements (softcore unlocks are opt-in), sets
      downloaded by themselves, rich presence on the RA profile.
- [x] Achievements while [playing offline](#playing-offline): the launcher
      keeps the sets on the SD card and syncs unlocks with DSiRPC, and the
      console checks them in game, saves its unlocks to the SD card, pulses
      an LED (DSi) and lists them in nds-bootstrap's in-game menu (works on
      hardware since 2026-10-08). Unlock times now come from the console's
      clock, which is new and not tried on hardware yet.
- [x] Achievements checked every frame, for the timing-sensitive ones: on the
      console (a set's frame lane, in the ARM7's idle time) and by DSiRPC
      (what fits in the console's per-frame record). Runs on hardware
      (Pokémon Platinum and Black), and the tests check it against rcheevos
      frame by frame.
- [x] Pokémon Black and White (US): their own overlay views and Discord
      presence, and battle loads as fast as without DSiRPC.
- [x] Fix graphical glitches in Pokémon Platinum (for example, the first time
      the pause menu opens).
- [ ] Full presence for more games and versions: for now every DS game gets
      its name, box art and RetroAchievements rich presence (and the
      overlay's game card), and only Platinum USA Rev 1 and Black and White
      (US) get the full presence and their own overlay views. Ordinary
      trainers' names in Black and White's battles are still to come.
- [ ] Location artwork for the big image, and more overworld states (running,
      biking, surfing, browsing the PC). Leads are in [docs/research.md](docs/research.md).
- [ ] Handle WPA2 group-key renewal in game, if your router ever disconnects
      the console on a schedule.
- [ ] More for the overlay: encounter and shiny counters, a Nuzlocke mode,
      browser-source panels for OBS.

## Credits

- Pokémon sprites from [PokeAPI](https://pokeapi.co/)
  ([sprites repository](https://github.com/PokeAPI/sprites)).
- More sprites used from [spriters-resource.com](https://www.spriters-resource.com/ds_dsi/pokemonblackwhite/)
- Overworld assets by [PurpleZaffre](https://eeveeexpo.com/threads/3667/).
- [nds-bootstrap](https://github.com/DS-Homebrew/nds-bootstrap) by DS-Homebrew
  (GPLv3), which hosts the in-game side.
- [BlocksDS](https://github.com/blocksds/sdk) and DSWiFi (MIT) for the launcher
  and the DSi-mode Wi-Fi code; devkitPro's
  [nds-bootloader](https://github.com/devkitPro/nds-bootloader) and
  [NDS Homebrew Menu](https://github.com/devkitPro/nds-hb-menu)'s bootstub
  (GPLv2+) for starting the game from it.
- [pret/pokeplatinum](https://github.com/pret/pokeplatinum) for struct
  layouts, the save layout and the name tables.
- [RetroAchievements](https://retroachievements.org/) code notes (game 11732)
  and [ProjectPokemon](https://projectpokemon.org/)'s notable breakpoints for
  memory addresses.
- [pypresence](https://github.com/qwertyquerty/pypresence) for Discord IPC,
  [pystray](https://github.com/moses-palmer/pystray) for the tray icon,
  [pygame-ce](https://github.com/pygame-community/pygame-ce) for the overlay.
- [rcheevos](https://github.com/RetroAchievements/rcheevos) (MIT) and
  RetroAchievements' set authors for other games' rich presence;
  [GameTDB](https://www.gametdb.com/) for box art and game titles.

## License

DSiRPC's own code is MIT licensed (see [LICENSE](LICENSE)). The
`nds-bootstrap/` folder is GPLv3 (see [nds-bootstrap/LICENSE](nds-bootstrap/LICENSE)).
`launcher/loader/` (devkitPro's nds-bootloader and NDS Homebrew Menu's
bootstub) is GPLv2 or later, and so is the built `dsirpc-launcher.nds`,
which includes it. The Windows download's `licenses` folder lists everything
it bundles.

Pokémon is © Nintendo / Creatures Inc. / GAME FREAK inc. This is an
unofficial fan project and isn't affiliated with or endorsed by them.
