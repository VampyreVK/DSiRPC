DSiRPC {version} for macOS
=====================================================================

DSiRPC shows the game you're playing on a modded Nintendo DSi or 3DS as
your Discord status. Pokemon Platinum (USA, Rev 1) and Black and White
(USA) get the full treatment: where you are, your party, your badges and
who you're battling, with sprites. Any other DS game shows its name, box
art and, if it has a RetroAchievements set, what you're doing in it.
Achievements are checked while you play, even offline, the launcher backs
up your saves, and there's an optional overlay window for streaming.

More help, and the source code: https://github.com/VampyreVK/DSiRPC


WHAT YOU NEED
---------------------------------------------------------------------
- A DSi or 3DS with TWiLight Menu++ installed, and your games as .nds
  files on its SD card.
- The console's Wi-Fi set up for the same network as your Mac. (On a DSi,
  a WPA2 network has to be in Connection 4, 5 or 6: System Settings >
  Internet > Connection Settings > Advanced Setup.)
- A Mac with Apple silicon (M1 or later) on macOS 12 or newer, with the
  Discord app.


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
   RetroAchievements is optional. Close the Terminal window when it's
   done. To change anything later, click the menu bar icon > Setup...

   When macOS asks whether DSiRPC may find devices on your local network,
   click Allow. Without that, DSiRPC never hears from the console. (It's
   in System Settings > Privacy & Security > Local Network if you missed
   it.)


STEP 2: THE SD CARD
---------------------------------------------------------------------
Copy the entire DSiRPC folder from the "SD card" folder here to
/roms/nds on your console's SD card, with your games. You should end up
with:

    sd:/roms/nds/DSiRPC/dsirpc-launcher.nds
    sd:/roms/nds/DSiRPC/nds-bootstrap-dsirpc.nds

Keep those two files together, in the same folder. This is the only time
they need copying: after that, the launcher updates them from DSiRPC
(see UPDATING below).


STEP 3: PLAYING
---------------------------------------------------------------------
1. Start DSiRPC on the Mac, or turn on "Open at Login" in its menu so
   it's always there.

2. On the console, open roms/nds/DSiRPC/dsirpc-launcher.nds from TWiLight
   Menu++.
   It connects to Wi-Fi (the DSi on the top screen turns its Wi-Fi sign
   green) and shows the console's IP address. X exits and stays connected,
   SELECT disconnects and exits.

3. Press START and pick your game (it opens in roms/nds): A opens a
   folder or picks the game, B goes up, START picks the game you last
   started from the launcher, SELECT goes back. The game starts, still
   connected.

4. Within about 15 seconds, Discord shows what you're playing.

The menu's "Overlay window" opens the overlay for streaming (capture it
in OBS with a macOS Screen Capture or Window Capture source).

Save backups: Y in the launcher backs up your games' saves to the Mac and
takes newer ones from it (from your other console, say; the launcher
says whose). The Mac keeps the live save your consoles share and each
console's last 10 backups (menu > Open save backups). L+R opens the
launcher's settings: how it finds DSiRPC, and whether saves sync or only
back up.

No Wi-Fi? Press B while the launcher connects (or START when it says it
couldn't) to play offline: games start the same way, without Discord,
and achievements unlocked offline are sent the next time the launcher
syncs with DSiRPC. The user guide on GitHub (docs/USER_GUIDE.md) has
the details.


IF SOMETHING DOESN'T WORK
---------------------------------------------------------------------
- Click DSiRPC's menu bar icon: the first lines say what it sees (the
  game, Discord, RetroAchievements).
- Nothing on Discord: the Mac and the console have to be on the same
  network, and DSiRPC needs Local Network access (above). Turn off other
  Rich Presence plugins, like Vencord's CustomRPC.
- The icon's dot is red: Discord isn't running, or setup has no Discord
  application yet (menu > Setup...).
- The launcher says it needs DSi mode: set it to DSi mode in TWiLight
  Menu++'s per-game settings.
- The launcher says "DSiRPC wasn't found": DSiRPC isn't running, or has
  no Local Network access. If it's running, give the launcher the Mac's
  address in its settings (L+R).
- The game starts but never shows up: the in-game menu (L + Down +
  SELECT) should say nds-bootstrap-DSiRPC at the bottom. If it says just
  nds-bootstrap, the game was started from TWiLight Menu++ instead of the
  launcher. Copy both SD card files from the same download: they go
  together.
- "This game has no save file yet": start the game once from TWiLight
  Menu++, then use the launcher.
- DSiRPC's settings, log, achievement sets and save backups are in
  ~/Library/Application Support/DSiRPC (menu > Open DSiRPC folder, or
  Open log).


UPDATING AND REMOVING
---------------------------------------------------------------------
To update, quit DSiRPC and replace DSiRPC.app with the new one. Your
settings, achievement sets and save backups stay. macOS may ask for Local
Network access again after an update.

The next time the launcher finds DSiRPC, it offers the new SD card files
(A updates, B not now): it downloads and checks them over Wi-Fi, swaps
them in and exits, and you start it again. Auto-update in the launcher's
settings (L+R) and Console updates in DSiRPC's menu turn this off. Coming
from v0.8.1 or older? Copy the SD card files by hand this once.

To remove DSiRPC, turn off "Open at Login" in its menu, quit it, and
delete DSiRPC.app and ~/Library/Application Support/DSiRPC (move its
saves folder out first to keep your save backups).

DSiRPC is an unofficial fan project, not affiliated with Nintendo, The
Pokemon Company or RetroAchievements. Licenses: see the licenses folder.
