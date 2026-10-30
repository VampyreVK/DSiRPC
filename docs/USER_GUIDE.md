# DSiRPC user guide

Everything about using DSiRPC, from installing it to save backups, playing
offline and the stream overlay. The [README](../README.md) has the short
version; [DOCUMENTATION.md](DOCUMENTATION.md) has how it all works inside.

**Contents:** [What you need](#what-you-need) · [Install](#install) ·
[Playing](#playing) · [The tray icon](#the-tray-icon) ·
[RetroAchievements](#retroachievements) · [Playing offline](#playing-offline) ·
[Save backups](#save-backups) · [The launcher's settings](#the-launchers-settings) ·
[Stream overlay window](#stream-overlay-window) · [Troubleshooting](#troubleshooting) ·
[Updating and removing](#updating-and-removing) · [Known issues](#known-issues)

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
   connects to Wi-Fi, ticking off each step on the bottom screen (the DSi on
   the top screen turns its Wi-Fi sign green), and finds DSiRPC. (Away from
   your PC? Press **B** to [play offline](#playing-offline).)
3. Open **Play** (or press **START** to start the game you played last) and
   pick your game ([the game list](#the-game-list)). The launcher starts
   it, still connected.
4. Within about 15 seconds, Discord shows what you're playing and the tray
   icon's dot turns green.

When you close the game, the presence clears after about 30 seconds and
DSiRPC waits for the console again, so switching games needs nothing on the
PC. Leaving the launcher without starting a game (**SELECT**, or **X** to
exit connected) clears DSiRPC's "connected" right away.

## The game list

**Play** on the launcher's main screen lists every game in `roms/nds` (and
its folders) with its own icon and name, as the DSi menu shows them, and
how many of its achievements you have. The top screen shows the game you're
on: its icon, its publisher, its achievements, how long you've played it
and when you last did.

- **A** starts the game, **B** goes back, and **START** starts the game you
  last started from the launcher.
- **L** / **R** change the order: the games you played last first, A to Z,
  or your favorites first. The launcher remembers the one you picked.
- **Y** makes a game a favorite (a star), or not.
- **X** lists its achievements, with their points, and what each one asks
  for on the top screen. A green check is earned, an amber one was unlocked
  on the console and waits for DSiRPC (offline play), and **L** / **R**
  shows all of them, the ones to earn or the earned ones. The list comes
  from the game's achievement set on the SD card, which DSiRPC puts there
  the first time you start the game while it's around.

Playtime is the time DSiRPC saw the game running, so it counts when you
play near your PC, not offline. The launcher asks DSiRPC for it as it
starts, and keeps it on the SD card for when you're away.

The first time, the list takes a moment to read every game's name; after
that, only new games are read. Everything on this screen works with the
touch screen too: tap a game to pick it, and again to start it.

## The tray icon

Right-click it (on a Mac, click it in the menu bar) for the menu:

| Item | What |
|---|---|
| The first lines | What's running, what Discord shows, and your RetroAchievements progress |
| **Discord presence** | Show the game on Discord, or not |
| **Console icon** | The picture Discord shows for games without their own presence |
| **Overlay window** | The [stream overlay](#stream-overlay-window) (a left click on the icon toggles it too) |
| **Console updates** | Let the launcher [update its files](#updating-and-removing) from this DSiRPC |
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

DSiRPC remembers every unlock it has seen, on the console or the PC, sent
or not, and the sets it gives the console mark them all earned, so the
console never loses one it handed over. Before the launcher starts a game,
DSiRPC checks that game with RetroAchievements: unlocks you earned elsewhere
come to the console, and ones RetroAchievements doesn't have yet are sent
(if sending is on). When RetroAchievements can't be reached, what DSiRPC
remembers is used instead.

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
| yellow `!` | Changed here, and a newer save from another console (or this console's save was written after the PC's) | Asks: **L** keeps this console's, **R** takes the other one, **B** decides later |
| grey `x` | Left out | Nothing, until it's back in |
| (none) | In sync | Nothing |

A save on the console is never replaced by an older one without asking:
when the PC's is older than the console's (by when each console wrote
them; say one console put an older version back), it's a `!`, never a `v`.

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
- **Auto-update:** on, the launcher asks DSiRPC as it starts whether it has
  other versions of the launcher or nds-bootstrap, and offers them
  ([Updating](#updating-and-removing)).
- **Look:** modern (the tiles, the game list with icons, the battery on the
  top screen) or classic (the original text screens, with a file browser
  for picking games). It changes as soon as you pick it.
- **Sounds:** the modern look's soft menu sounds, on or off.

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
| The launcher never offers an update | **Auto-update** is off in [its settings](#the-launchers-settings), **Console updates** is off in the tray menu, or the launcher is from v0.8.1 or older: copy the SD card files by hand once. |

More is in [docs/DOCUMENTATION.md, section 11](DOCUMENTATION.md#11-debugging-and-troubleshooting).
The log is `logs\dsirpc.log` (tray menu > **Open log**).

## Updating and removing

To update, unzip the new release over your DSiRPC folder (replace the files
when asked), or on a Mac replace DSiRPC.app. Your settings (`dsirpc.cfg`),
achievement sets and save backups stay.

The console's files come along. The next time the launcher finds DSiRPC, it
offers the launcher and nds-bootstrap that came with it, if they differ from
the SD card's (**A** updates, **B** not now). It downloads them over Wi-Fi
and checks them before anything on the SD card changes, then turns the
Wi-Fi off, swaps them in and exits; start it again from TWiLight Menu++.
Only files that changed are downloaded. **Auto-update** in
[the launcher's settings](#the-launchers-settings) turns the asking off, and
**Console updates** in the tray menu the offering. A launcher from v0.8.1 or
older can't update itself: copy the two SD card files from the zip by hand
once more.

To remove DSiRPC, turn off **Start with Windows**, quit it, and delete its
folder (move `saves` out first to keep your save backups).

## Known issues

- Games' own Wi-Fi features don't work while playing through DSiRPC (the
  console's Wi-Fi is DSiRPC's while you play).
- DSi-enhanced games (like Pokémon Black and White) run in DS mode when
  started from the launcher, since that's the only mode DSiRPC's part of
  nds-bootstrap runs in, so their DSi-only extras are off.
