DSiRPC {version} for macOS
=====================================================================

DSiRPC shows the game you're playing on a modded Nintendo DSi or 3DS as
your Discord status. Pokemon Platinum (USA, Rev 1) and Black and White get
the full treatment: where you are, your party, your badges and who you're
battling, with sprites. Any other DS game shows its name, box art and, if
it has a RetroAchievements set, what you're doing in it. Achievements are
checked while you play, even offline, and there's an optional overlay
window for streaming.

More help, and the source code: https://github.com/VampyreVK/DSiRPC


WHAT YOU NEED
---------------------------------------------------------------------
- A DSi or 3DS with TWiLight Menu++ installed.
- The console's Wi-Fi set up for the same network as your Mac. (On a DSi,
  a WPA2 network has to be in Connection 4, 5 or 6: System Settings >
  Internet > Connection Settings > Advanced Setup.)
- A Mac with Apple silicon (M1 or later) on macOS 12 or newer, with the
  Discord app.
- Your games as .nds files on the SD card. DSi-enhanced games (Pokemon
  Black and White, and later) have to be set to DS mode in TWiLight
  Menu++'s per-game settings.


STEP 1: THE MAC
---------------------------------------------------------------------
1. Drag DSiRPC.app into your Applications folder.

2. Open it. It isn't signed by an Apple developer account, so the first
   time macOS won't open it from a double-click: right-click (or
   Control-click) DSiRPC.app > Open > Open. On newer macOS versions, if
   there's no Open button: System Settings > Privacy & Security, scroll
   down to DSiRPC and click "Open Anyway".
   (Or, in Terminal: xattr -dr com.apple.quarantine /Applications/DSiRPC.app)

3. DSiRPC's icon, a little DSi, appears in the menu bar by the clock, and
   the first time setup opens in Terminal. Answer its questions; press
   Return to take the suggested answer (the one in [brackets]).
   - Discord: if this download comes with a Discord application, just
     press Return. Otherwise setup explains how to make one (it's free
     and takes a minute).
   - RetroAchievements is optional: skip it by pressing Return.
   Close the Terminal window when it's done. To change anything later,
   click the menu bar icon > Setup...

   When macOS asks whether DSiRPC may find devices on your local network,
   click Allow. Without that, DSiRPC never hears from the console. (It's
   in System Settings > Privacy & Security > Local Network if you missed
   it.)


STEP 2: THE SD CARD
---------------------------------------------------------------------
Copy the DSiRPC folder from the "SD card" folder here to the root of
your console's SD card. You should end up with:

    sd:/DSiRPC/dsirpc-launcher.nds
    sd:/DSiRPC/nds-bootstrap-dsirpc.nds

Keep those two files together, in the same folder.


STEP 3: PLAYING
---------------------------------------------------------------------
1. Start DSiRPC on the Mac, or turn on "Open at Login" in its menu so
   it's always there.

2. On the console, open DSiRPC/dsirpc-launcher.nds from TWiLight Menu++.
   It connects to Wi-Fi (it tries up to 3 times) and shows the IP
   address. It has to run in DSi mode; if it says it's in DS mode, change
   that in TWiLight Menu++'s per-game settings for it.

3. Press START and pick your game: A opens a folder or picks the game,
   B goes up a folder (the browser opens in the DSiRPC folder, so press B
   to get to your games). The game starts, still connected.

4. Within about 15 seconds, Discord shows what you're playing.

The menu's "Overlay window" opens the overlay for streaming (capture it
in OBS with a macOS Screen Capture or Window Capture source).

In the launcher, SELECT disconnects and goes back without starting a game.
No Wi-Fi? Press B while the launcher connects (or START when it says it
couldn't) to play offline: games start the same way, without Discord, and
achievements unlocked offline are sent the next time the launcher syncs
with DSiRPC. README.md on GitHub has the details.


IF SOMETHING DOESN'T WORK
---------------------------------------------------------------------
- Click DSiRPC's menu bar icon: the first lines say what it sees (the
  game, Discord, RetroAchievements).
- Nothing on Discord: the Mac and the console have to be on the same
  network, and DSiRPC needs Local Network access (above). Turn off other
  Rich Presence plugins, like Vencord's CustomRPC.
- Discord shows nothing while the icon's dot is red: Discord isn't
  running, or setup has no Discord application yet (menu > Setup...).
- DSiRPC's settings, log and achievement sets are in
  ~/Library/Application Support/DSiRPC (menu > Open DSiRPC folder, or
  Open log).


UPDATING AND REMOVING
---------------------------------------------------------------------
To update, quit DSiRPC and replace DSiRPC.app with the new one. Your
settings and achievement sets stay. Copy the new SD card files over the
old ones too. macOS may ask for Local Network access again after an
update.

To remove DSiRPC, turn off "Open at Login" in its menu, quit it, and
delete DSiRPC.app and ~/Library/Application Support/DSiRPC.

DSiRPC is an unofficial fan project, not affiliated with Nintendo, The
Pokemon Company or RetroAchievements. Licenses: see the licenses folder.
