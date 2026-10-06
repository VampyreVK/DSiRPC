# DSiRPC

Discord Rich Presence for games played on a real, modded Nintendo DSi or 3DS.
While you play, the console reads the game's memory and sends it over Wi-Fi
to your PC, which shows what you're doing as your Discord status.

**Pokémon Platinum (USA, Rev 1)** gets the full presence: where you are, your
party, your badges, and who you're battling, with animated sprites. **Any
other DS game** shows its name, box art and a picture of your console, plus
its [RetroAchievements](https://retroachievements.org/) rich presence
("Racing in Figure-8 Circuit") when it has one. Every game's achievements are
checked while you play, and an optional overlay window shows your party and
battles for streaming.

| Overworld (Playing) | Battle (Competing) |
|---|---|
| "Exploring Route 209", badges and Pokédex count, your trainer walking in the direction you face, your lead Pokémon, party fraction | "Battling rival Barry", "Blucifer is fighting Buizel", foe and your Pokémon as sprites (shiny-aware), HP on hover |

## What you need

- A **DSi or 3DS with [TWiLight Menu++](https://github.com/DS-Homebrew/TWiLightMenu)**
  installed, and your games as `.nds` files on its SD card.
- The console's **Wi-Fi set up** for the same network as your PC. On a DSi, a
  WPA2 network has to be saved in connection 4, 5 or 6 (System Settings >
  Internet > Connection Settings > Advanced Setup).
- A **64-bit Windows 10 or 11 PC** with the **Discord** desktop app.

## Install

1. Download **`DSiRPC-<version>-windows.zip`** from the
   [Releases page](https://github.com/VampyreVK/DSiRPC/releases/latest). It
   has everything: DSiRPC with its own copy of Python (nothing to install),
   the two files for your SD card, and a `README.txt` with these steps.
2. **On the PC:** unzip it somewhere you can write to (Documents, the
   Desktop; not Program Files). If Windows says it "protected your PC",
   right-click the zip > Properties > tick **Unblock**, and unzip it again.
3. Double-click **`Setup.bat`** and answer its questions; Enter takes the
   suggested answer. The download comes with a Discord application, so you
   can press Enter there too. Signing in to RetroAchievements is optional.
4. Double-click **`DSiRPC.bat`**. DSiRPC's icon appears in the taskbar's
   notification area, by the clock. When Windows asks about the firewall,
   allow access on **private networks**, or DSiRPC never hears from the
   console.
5. **On the SD card:** copy the `DSiRPC` folder from the zip's `SD card`
   folder to the root of the card, so you have `sd:/DSiRPC/dsirpc-launcher.nds`
   and `sd:/DSiRPC/nds-bootstrap-dsirpc.nds`. Keep the two together.

## Playing

1. **PC:** start DSiRPC (`DSiRPC.bat`), or turn on **Start with Windows** in
   its menu so it's always there. Turn off any other Rich Presence plugin
   (like Vencord's CustomRPC), or Discord shows two activities.
2. **Console:** open `DSiRPC/dsirpc-launcher.nds` from TWiLight Menu++. It
   connects to Wi-Fi in DSi mode (it tries up to 3 times by itself) and shows
   the console's IP address. If it says it's running in DS mode, set it to
   DSi mode in TWiLight Menu++'s per-game settings.
3. Press **START** and pick your game: **A** opens a folder or picks the game,
   **B** goes up a folder. The launcher starts it, still connected.
   (**SELECT** disconnects and goes back instead.)
4. Within about 15 seconds, Discord shows what you're playing, and the tray
   icon's dot turns green.

A game you've never started from TWiLight Menu++ has no save file yet; the
launcher says so. Start it once from TWiLight Menu++, then use the launcher.

When you close the game, DSiRPC clears the presence after about 30 seconds and
waits for the console again, so switching games or restarting needs nothing
on the PC.

### The tray icon

Right-click it for the menu:

| Item | What |
|---|---|
| The first lines | What's running, what Discord shows, and your RetroAchievements progress |
| **Discord presence** | Show the game on Discord, or not |
| **Console icon** | The picture Discord shows for games without their own presence: DSi XL, New 3DS, or none |
| **Overlay window** | The stream overlay (a left click on the icon toggles it too) |
| **Start with Windows** | Start DSiRPC in the tray when you sign in |
| **Setup...** | Runs setup again, to change an answer |
| **Open log** / **Open DSiRPC folder** | `logs\dsirpc.log`, and the folder DSiRPC is in |
| **Quit** | Stops DSiRPC |

The dot is green while the game answers, amber while DSiRPC waits for the
console, and red if Discord can't be reached (or there's no Discord
application yet).

## RetroAchievements

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

- DSiRPC checks achievements about once a second, not every frame like an
  emulator. Achievements about things that last (a flag set, a cup won) work
  the same; ones about split-second moments can unlock late, not at all or,
  rarely, when they shouldn't.
- RetroAchievements doesn't officially support playing on original hardware.
  DSiRPC tells it honestly what it is, so it only ever counts these unlocks
  as softcore.

Unlocks that can't be sent right away (no internet) are kept and sent later.

## Stream overlay window

The overlay window (tray menu > **Overlay window**) shows your party, and
switches to a battle view when a battle starts, in a pixel-art style inspired
by the DS games. The battle background follows the DS clock, the location
and the weather; Pokémon slide in, flash when hit and sink when they faint;
every move gets its "X used MOVE!" line and a type-coloured animation; stat
changes and conditions show on the HP boxes and Pokémon; and the bottom box
shows your moves with PP and how effective each one is. Banners pop up for
shiny encounters, level-ups, fainting, new badges and achievements. Other
games get a card with their name, rich presence and achievement progress.

It draws at the DS's 256x192 and scales up by a whole number, so the pixels
stay crisp. Add it to OBS with **Window Capture**, or share the window on
Discord. Keys **1**-**6** change its size, and **V** switches between
automatic, party only and battle only. For OBS's Chroma Key filter, set
`chroma` (a colour like `00FF00`) in `dsirpc.cfg`. The sprites are downloaded
the first time they're needed, then kept.

## Troubleshooting

| Problem | Try |
|---|---|
| Nothing on Discord | Right-click the tray icon: its first lines say what DSiRPC sees. The PC and the console must be on the same network, and the firewall must allow DSiRPC on private networks (Windows Security > Firewall > Allow an app: `python.exe` and `pythonw.exe` in DSiRPC's `python` folder). |
| The tray dot is red | Discord isn't running, or there's no Discord application yet: run setup. |
| The launcher can't connect | Check the console's Wi-Fi settings (on a DSi, WPA2 needs connection 4, 5 or 6). |
| "This game has no save file yet" | Start the game once from TWiLight Menu++, then use the launcher again. |
| Two activities on Discord | Another Rich Presence tool (like Vencord's CustomRPC) is still on. |
| A game shows only its name | It has no achievement set yet; the tray menu's RetroAchievements line says why. Run setup while the game runs to pick its set. |

More, including what the console sends and how to read it, is in
[docs/DOCUMENTATION.md, section 11](docs/DOCUMENTATION.md#11-debugging-and-troubleshooting).
The log is `logs\dsirpc.log` in DSiRPC's folder.

## Updating and removing

To update, unzip the new release over your DSiRPC folder (replace the files
when asked): your settings (`dsirpc.cfg`) and achievement sets stay. Copy the
new SD card files over the old ones too. To remove DSiRPC, turn off **Start
with Windows**, quit it, and delete its folder.

## How it works

```
Console: dsirpc-launcher.nds     connects to Wi-Fi in DSi mode, then starts the
        |                        game you pick with our nds-bootstrap, still connected
        v
our nds-bootstrap  --boots-->  the game
  a small memory server in its ARM7 code
    answers "read N bytes at X"  <--- UDP 4244 --->  PC: DSiRPC (tray)
    broadcasts a hello every second                     reads and decodes the game's state,
                                                        checks achievements
                                                          |                  |
                                                          v                  v
                                                  Discord Rich Presence   overlay window
```

The console side stays simple: it only answers "give me these bytes".
Everything else (decrypting the party, working out the location, deciding
what Discord shows) happens on the PC, so new features never need a console
update. The full technical reference is
[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md); building and running from
the source code is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Known issues and roadmap

- [ ] Fix graphical glitches in Pokémon Platinum (for example, the first time
      the pause menu opens).
- [ ] Location artwork for the big image, and more overworld states (running,
      biking, surfing, browsing the PC). Leads are in [docs/research.md](docs/research.md).
- [ ] Handle WPA2 group-key renewal in game, if your router ever disconnects
      the console on a schedule.
- [ ] Full presence for more games and versions: for now every DS game gets
      its name, box art and RetroAchievements rich presence, and only
      Platinum USA Rev 1 gets the full presence and the overlay's party and
      battle views.
- [ ] Achievements checked every frame, for the timing-sensitive ones.
- [ ] More for the overlay: encounter and shiny counters, a Nuzlocke mode,
      browser-source panels for OBS.
- [x] RetroAchievements: achievements (softcore unlocks are opt-in), sets
      downloaded by themselves, rich presence on the RA profile.
- [x] One app on the console: the launcher connects and starts the game.
- [x] A Windows download that needs nothing installed.
- Games' own Wi-Fi features don't work while playing through DSiRPC.
- DSi-enhanced games (Pokémon Black and White, and later) need to run in DS
  mode (TWiLight Menu++'s per-game settings).

## Credits

- Pokémon sprites from [PokeAPI](https://pokeapi.co/)
  ([sprites repository](https://github.com/PokeAPI/sprites)).
- CREDIT to (PurpleZaffre) for the overworld assets.
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
