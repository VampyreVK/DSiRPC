# DSiRPC

#### Discord Rich Presence for games played on a real, modded Nintendo DSi or 3DS.
While you play, the console reads the game's memory and sends it over Wi-Fi
to your PC, which shows what you're doing as your Discord status.

- **Pokémon Platinum (USA, Rev 1)** and **Pokémon Black and White (USA)** get
  the full presence: where you are, your party, your badges and who you're
  battling, with animated sprites.
- **Any other DS game** shows its name, box art and a picture of your
  console, plus its [RetroAchievements](https://retroachievements.org/) rich
  presence ("Racing in Figure-8 Circuit") when it has one.
- **Achievements** are checked while you play, even offline.
- **Save backups:** the launcher backs your saves up to the PC and can keep
  your consoles in sync.
- **A stream overlay window** shows your party and battles, or any other
  game's progress.

**Contents:** [What you need](#what-you-need) · [Install](#install) ·
[Playing](#playing) · [The tray icon](#the-tray-icon) ·
[RetroAchievements](#retroachievements) · [Playing offline](#playing-offline) ·
[Save backups](#save-backups) · [The launcher's settings](#the-launchers-settings) ·
[Stream overlay window](#stream-overlay-window) · [Troubleshooting](#troubleshooting) ·
[Updating and removing](#updating-and-removing) · [Known issues](#known-issues) ·
[How it works](#how-it-works) · [For developers](#for-developers) ·
[Roadmap](#roadmap) · [Credits](#credits) · [License](#license)

## What you need

- A **DSi or 3DS with [TWiLight Menu++](https://github.com/DS-Homebrew/TWiLightMenu)**
  installed, and your games as `.nds` files on its SD card.
- The console's **Wi-Fi set up** for the same network as your PC. On a DSi, a
  WPA2 network has to be saved in connection 4, 5 or 6 (System Settings >
  Internet > Connection Settings > Advanced Setup).
- A **64-bit Windows 10 or 11 PC**, or a **Mac with Apple silicon** (M1 or
  later, macOS 12+), with the **Discord** desktop app.

## Install

1. Download **`DSiRPC-<version>-windows.zip`** from the
   [Releases page](https://github.com/VampyreVK/DSiRPC/releases/latest). It
   has DSiRPC with its own copy of Python (nothing to install), the two files
   for your SD card, and a `README.txt` with these steps.
2. Unzip it somewhere you can write to (Documents, the Desktop; not Program
   Files). If Windows says it "protected your PC", right-click the zip >
   Properties > tick **Unblock**, and unzip it again.
3. Double-click **`Setup.bat`** and answer its questions. Enter takes the
   suggested answer; signing in to RetroAchievements is optional.
4. Double-click **`DSiRPC.bat`**. Its icon appears by the clock. When
   Windows asks about the firewall, allow **private networks**, or DSiRPC
   never hears from the console.
5. Copy the `DSiRPC` folder from the zip's `SD card` folder to the root of
   your SD card, so you have `sd:/DSiRPC/dsirpc-launcher.nds` and
   `sd:/DSiRPC/nds-bootstrap-dsirpc.nds`. Keep the two together.

### On a Mac

Download **`DSiRPC-<version>-macos.zip`** instead and drag **DSiRPC.app**
into Applications. It isn't signed with an Apple developer account, so open
it the first time with right-click > **Open** (or System Settings > Privacy &
Security > **Open Anyway**). Setup opens in Terminal the first time, and the
icon is in the menu bar. Allow DSiRPC on the **local network** when macOS
asks, or it never hears from the console. The SD card files are the same.
Its settings, log, achievement sets and save backups are in
`~/Library/Application Support/DSiRPC`.

## Playing

1. **PC:** start DSiRPC, or turn on **Start with Windows** in its menu so
   it's always there.
2. **Console:** open `DSiRPC/dsirpc-launcher.nds` from TWiLight Menu++. It
   connects to Wi-Fi (the DSi on the top screen turns its Wi-Fi sign green)
   and shows the console's IP address. (Away from your PC? Press **B** to
   [play offline](#playing-offline).)
3. Press **START** and pick your game: **A** opens a folder or picks the
   game, **B** goes up (it opens in `roms/nds`). **START** there starts the
   game you last started from the launcher, and **SELECT** goes back. The
   launcher starts it, still connected.
4. Within about 15 seconds, Discord shows what you're playing and the tray
   icon's dot turns green.

When you close the game, the presence clears after about 30 seconds and
DSiRPC waits for the console again, so switching games needs nothing on the
PC. Leaving the launcher without starting a game (**SELECT**, or **X** to
exit connected) clears DSiRPC's "connected" right away.

## The tray icon

Right-click it (on a Mac, click it in the menu bar) for the menu:

| Item | What |
|---|---|
| The first lines | What's running, what Discord shows, and your RetroAchievements progress |
| **Discord presence** | Show the game on Discord, or not |
| **Console icon** | The picture Discord shows for games without their own presence |
| **Overlay window** | The [stream overlay](#stream-overlay-window) (a left click on the icon toggles it too) |
| **Start with Windows** | Start DSiRPC when you sign in (**Open at Login** on a Mac) |
| **Setup...** | Run setup again, to change an answer |
| **Open log**, **Open DSiRPC folder**, **Open save backups** | The log, the folder with DSiRPC's settings, and the [save backups](#save-backups) |
| **Quit** | Stop DSiRPC |

The dot is green while the game answers, amber while DSiRPC waits for the
console, and red when Discord isn't running or there's no Discord
application yet (run setup).

## RetroAchievements

DSiRPC checks each game's achievements against the console's memory with
[rcheevos](https://github.com/RetroAchievements/rcheevos), RetroAchievements'
own library. An unlock gets a notification and a banner in the overlay
window, and goes in `logs\achievements.log`.

A game's achievements come in a *set*, kept in the `ra` folder. Sets come
from:

- **RetroAchievements**, once you've signed in with setup (only a login token
  is saved, never your password). DSiRPC works out which game is running and
  downloads its set. Give setup a folder of your game files (the ones you
  play in RALibretro, say) and it knows the exact game and version;
  without one it goes by the title, and setup can search for a set it can't
  tell.
- **RALibretro's cache**, without an account.

Signed in, your RetroAchievements profile shows what you're playing, and
Discord's hover text shows your progress ("12 of 132 unlocked").

**Sending your unlocks to RetroAchievements is a separate choice in setup**,
off unless you turn it on, and always softcore. RetroAchievements doesn't
officially support original hardware, and not every achievement can be
checked every frame like on an emulator, so ones about split-second moments
can unlock late, not at all or, rarely, when they shouldn't. Unlocks that
can't be sent right away (no internet) wait and go later.

A game started from the launcher is also checked by the console itself,
which is what makes [offline play](#playing-offline) work. DSiRPC checks the
rest, and each side tells the other what it unlocked.

## Playing offline

Away from your PC (or your Wi-Fi), press **B** while the launcher connects,
or **START** when it says it couldn't connect. The game runs as usual,
without Discord or the overlay, and its achievements still count: the
console checks them itself and saves each unlock to the SD card, with the
time from its clock.

Whenever the launcher reaches DSiRPC (when it connects, and again when you
start a game; **B** skips it), the two sync: DSiRPC sends the
[achievement sets](#retroachievements) you have (the launcher keeps them in
`sd:/DSiRPC/sets`), and the launcher hands over the offline unlocks, which
DSiRPC sends to RetroAchievements if sending is on. This works for games
started from the launcher, which puts the game's set on the SD card.

**nds-bootstrap's in-game menu** (**L + Down + SELECT** by default) says how
many achievements are new since you last looked. Its **Achievements** item
lists them: the ones you've earned first, newest first with the date and
time (in lime while DSiRPC hasn't had them yet), then the ones still to get,
including what you'd earned on RetroAchievements before. Up/Down move, L/R
turn the page, B goes back.

**On a DSi, an LED** pulses while there are unlocks you haven't seen in the
menu: the one TWiLight Menu++'s **ROM read LED** setting picks (the power
LED pulses purple). With DSiRPC's nds-bootstrap that LED no longer flashes
for ROM reads; set the setting to None to turn the achievement LED off. A
3DS has no LED for this.

## Save backups

Press **Y** in the launcher (while it's connected and DSiRPC is running) to
back up your saves to the PC and bring newer ones over from it, from your
other console for example. The launcher finds every game in `roms/nds`
(subfolders too) and its saves, wherever TWiLight Menu++ keeps them, every
save slot included (a save no game is named after, like a renamed backup,
is left alone).

The PC keeps them in a `saves` folder (setup can move it, to a cloud drive
for an off-site copy), a folder per game:

- the **live** save, the one your consoles share: the newest any of them
  sent;
- `backups/<console>/`: every save each console sent, its last **10** (setup
  can change the number), each dated when the console last wrote it. The
  newest is the live save over again, on purpose;
- `backups/External/`: saves that came from somewhere else. Copy a save
  over the live one by hand (from an emulator, say) and it becomes the live
  save, kept as an External backup too; put one anywhere else in the
  game's folder and the consoles can restore it.

Nothing on either side is replaced without being kept as a backup first.

The list has **Sync all** on top, then each save, decided by what the
console had at its last sync (the save it sent or took):

| Mark | Means | Syncing it |
|---|---|---|
| green `^` | Changed on this console since its last sync, and nothing newer from the others | Backs it up (your other consoles get it at their next sync) |
| cyan `v` | Unchanged here, and a newer save from another console (or only on the PC: the game is here, its save isn't) | Takes it; the list says whose it is |
| yellow `!` | Changed here, and a newer save from another console | Asks: **L** keeps this console's, **R** takes the other one, **B** decides later |
| grey `x` | Left out | Nothing, until it's back in |
| (none) | In sync | Nothing |

**A** syncs the save picked (or everything, on Sync all), **START** syncs
everything, **Y** leaves a save out (or puts it back in), **X** lists the
versions the PC keeps, with whose each one is, so you can put one back,
and **B** goes back. Syncing everything asks about each `!` first, shows how
it's going, then a summary.

The launcher only reads the saves whose size or time changed since the last
sync, so checking is quick, and its main screen says how many changed on
the console (newer saves on the PC show up in the list).

## The launcher's settings

Hold **L + R** on the launcher's main screen. The settings are kept in
`launcher.ini` next to the launcher.

- **Find DSiRPC:** automatically (it asks the whole network) or at an
  address, for networks that don't pass the question along. When the
  launcher finds DSiRPC, its main screen shows the address.
- **Saves:** back up and sync, or back up only (saves only go to the PC, so
  each console keeps its own).

## Stream overlay window

The overlay window (tray menu > **Overlay window**) is drawn in the DS
games' pixel-art style:

- **Platinum:** your party, and a battle view when a battle starts, with
  animated Pokémon and moves, your moves with PP and how effective each one
  is, and banners for shinies, level-ups, badges and achievements.
- **Black and White:** a view in those games' look (party, trainer, badges,
  the season, achievements), and battles in their style, with Gym Leaders,
  the Elite Four and the Champion making their entrances.
- **Any other game:** a card with its name, how long you've played, what
  you're doing (its rich presence) and your achievement progress.

It draws at the DS's 256x192 and scales up by a whole number, so the pixels
stay crisp. Add it to OBS with **Window Capture** (for a Chroma Key filter,
set `chroma`, a colour like `00FF00`, in `dsirpc.cfg`), or share the window
on Discord. Keys **1**-**6** change its size, and **V** switches to the party
screen (all six Pokémon with their moves, PP, nature and held item) and back.

## Troubleshooting

| Problem | Try |
|---|---|
| Nothing on Discord | Right-click the tray icon: its first lines say what DSiRPC sees. The PC and the console must be on the same network, and the firewall must allow DSiRPC on private networks (Windows Security > Firewall > Allow an app: `python.exe` and `pythonw.exe` in DSiRPC's `python` folder; on a Mac, System Settings > Privacy & Security > Local Network). |
| The launcher says it's running in DS mode | Set it to DSi mode in TWiLight Menu++'s per-game settings. |
| The launcher can't connect | Check the console's Wi-Fi settings (on a DSi, WPA2 needs connection 4, 5 or 6). |
| "DSiRPC wasn't found" or "can't be reached" | DSiRPC isn't running, or the firewall blocks it (as in "Nothing on Discord"; the launcher uses port 4245). If it is running, give the launcher the PC's address in [its settings](#the-launchers-settings). Games still start; offline unlocks wait on the SD card. |
| The game starts but never shows on Discord | nds-bootstrap's in-game menu should say **nds-bootstrap-DSiRPC**: if it says just "nds-bootstrap", the game wasn't started from the launcher. The launcher and `nds-bootstrap-dsirpc.nds` must be from the same release. |
| "This game has no save file yet" | Start the game once from TWiLight Menu++, then use the launcher again. |
| The in-game menu says "no set loaded" or "another game's" | Start the game with **START** in the launcher (not **X**, and not from TWiLight Menu++): that's what puts its set on the SD card. |
| A game shows only its name | It has no achievement set yet; the tray menu's RetroAchievements line says why. Run setup while the game runs to pick its set. |
| Discord stopped after the DSi's lid was closed | On purpose: a DSi that sleeps while connected switches itself off, so its Wi-Fi goes off with the lid. Achievements are still checked and saved. Start the game from the launcher again to reconnect. |
| Two activities on Discord | Another Rich Presence tool (like Vencord's CustomRPC) is still on. |

More is in [docs/DOCUMENTATION.md, section 11](docs/DOCUMENTATION.md#11-debugging-and-troubleshooting).
The log is `logs\dsirpc.log` (tray menu > **Open log**).

## Updating and removing

To update, unzip the new release over your DSiRPC folder (replace the files
when asked), or on a Mac replace DSiRPC.app. Copy the new SD card files over
the old ones too: the two go together. Your settings (`dsirpc.cfg`),
achievement sets and save backups stay.

To remove DSiRPC, turn off **Start with Windows**, quit it, and delete its
folder (move `saves` out first to keep your save backups).

## Known issues

- Games' own Wi-Fi features don't work while playing through DSiRPC (the
  console's Wi-Fi is DSiRPC's while you play).
- DSi-enhanced games (like Pokémon Black and White) run in DS mode when
  started from the launcher, since that's the only mode DSiRPC's part of
  nds-bootstrap runs in, so their DSi-only extras are off.

## How it works

```
Console                                          PC
dsirpc-launcher.nds   <--- sync, port 4245 --->  DSiRPC
  connects to Wi-Fi,                             sends sets, takes offline
  starts the game                                unlocks, backs up saves
        |
        v
DSiRPC's nds-bootstrap --boots--> the game
  memory server and                              reads the game's state,
  achievement checker  <------ UDP 4244 ------>  checks achievements
  (in the ARM7)                                    |                |
                                                   v                v
                                           Discord presence   overlay window
```

The console only answers "give me these bytes" (and, for offline play, runs
the achievement program DSiRPC prepares). Everything else, from decoding the
party to deciding what Discord shows, happens on the PC, so most new
features never need a console update. The console's part runs in the time
the game's second processor (the ARM7) leaves free, so games run at their
usual speed.

## For developers

| Where | What |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Running from the source code, building the console files, the command line and testing flags, tools, tests and releases |
| [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) | The technical reference: the protocol, the achievement checker, the memory maps, troubleshooting |
| [launcher/README.md](launcher/README.md), [nds-bootstrap/DSIRPC_CHANGES.md](nds-bootstrap/DSIRPC_CHANGES.md) | The console side: the launcher, and what was changed in nds-bootstrap |
| [tests/README.md](tests/README.md) | The tests GitHub runs on every change |
| [docs/HISTORY.md](docs/HISTORY.md) | How the project got here |

The PC side is Python (`app/`, `core/`, `overlay/`, `rpc/`); the console side
is a modified nds-bootstrap (GPLv3) and the launcher, built with BlocksDS.

## Roadmap

- [ ] Full presence for more games and versions (for now Platinum USA Rev 1
      and Black and White USA), and ordinary trainers' names in Black and
      White's battles.
- [ ] Location artwork for the big image, and more overworld states (running,
      biking, surfing). Leads are in [docs/research.md](docs/research.md).
- [ ] More for the overlay: encounter and shiny counters, a Nuzlocke mode,
      browser-source panels for OBS.
- [ ] Handle WPA2 group-key renewal in game, if a router ever disconnects
      the console on a schedule.

## Credits

- Pokémon sprites from [PokeAPI](https://pokeapi.co/)
  ([sprites repository](https://github.com/PokeAPI/sprites)).
- More sprites from [spriters-resource.com](https://www.spriters-resource.com/ds_dsi/pokemonblackwhite/).
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
