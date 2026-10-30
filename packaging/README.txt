DSiRPC {version}
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
- The console's Wi-Fi set up for the same network as your PC. (On a DSi,
  a WPA2 network has to be in Connection 4, 5 or 6: System Settings >
  Internet > Connection Settings > Advanced Setup.)
- A 64-bit Windows 10 or 11 PC with the Discord app.

Nothing needs installing on the PC: this folder has everything.


STEP 1: THE PC
---------------------------------------------------------------------
1. Put this DSiRPC folder somewhere you can write to, like Documents or
   the Desktop (not Program Files).

   If Windows says it "protected your PC" when you open a file: right-click
   the zip you downloaded > Properties > tick "Unblock" > OK, and unzip it
   again. (Or click "More info" > "Run anyway".)

2. Double-click Setup.bat and answer its questions. Press Enter to take
   the suggested answer (the one in [brackets]). RetroAchievements is
   optional.

3. Double-click DSiRPC.bat. DSiRPC's icon appears by the clock;
   right-click it for the menu.

   When Windows asks about the firewall, allow access on private
   networks. Without that, DSiRPC never hears from the console.


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
1. Start DSiRPC on the PC (DSiRPC.bat), or turn on "Start with Windows"
   in its menu so it's always there.

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

Save backups: Y in the launcher backs up your games' saves to the PC and
takes newer ones from it (from your other console, say; the launcher
says whose). The PC keeps the live save your consoles share and each
console's last 10 backups in its saves folder (tray menu > Open save
backups). L+R opens the launcher's settings: how it finds DSiRPC, and
whether saves sync or only back up.

No Wi-Fi? Press B while the launcher connects (or START when it says it
couldn't) to play offline: games start the same way, without Discord,
and the console checks their achievements itself, saving what you unlock
to the SD card. Whenever the launcher is connected and DSiRPC is
running, the two sync (B skips it): DSiRPC puts your achievement sets on
the SD card and sends the offline unlocks to RetroAchievements.

nds-bootstrap's in-game menu (L + Down + SELECT) says what's new and
lists the game's achievements (its Achievements item). On a DSi, the LED
you picked as TWiLight Menu++'s "ROM read LED" pulses while there are
unlocks you haven't seen in that menu.


IF SOMETHING DOESN'T WORK
---------------------------------------------------------------------
- Right-click DSiRPC's tray icon: the first lines say what it sees (the
  game, Discord, RetroAchievements).
- Nothing on Discord: the PC and the console have to be on the same
  network, and the firewall has to allow DSiRPC (Windows Security >
  Firewall > Allow an app: python.exe and pythonw.exe from this folder's
  python folder, on private networks). Turn off other Rich Presence
  plugins, like Vencord's CustomRPC.
- The tray icon's dot is red: Discord isn't running, or setup has no
  Discord application yet (run Setup.bat).
- The launcher says it needs DSi mode: set it to DSi mode in TWiLight
  Menu++'s per-game settings.
- The launcher can't connect: check the console's Wi-Fi settings.
- The launcher says "DSiRPC wasn't found": DSiRPC isn't running, or the
  firewall blocks it (see "Nothing on Discord"). If it's running, give
  the launcher the PC's address in its settings (L+R).
- The game starts but never shows up: the in-game menu should say
  nds-bootstrap-DSiRPC at the bottom. If it says just nds-bootstrap, the
  game was started from TWiLight Menu++ instead of the launcher. Copy
  both SD card files from the same download: they go together.
- "This game has no save file yet": start the game once from TWiLight
  Menu++, then use the launcher.
- Discord stopped after closing a DSi's lid: that's on purpose (a DSi
  that sleeps while connected switches itself off). Achievements are
  still checked and saved; start the game from the launcher again to
  reconnect.
- DSiRPC's log is logs\dsirpc.log in this folder (tray menu > Open log).


UPDATING AND REMOVING
---------------------------------------------------------------------
To update, unzip the new release over this folder (replace the files
when asked). Your settings (dsirpc.cfg), achievement sets (ra) and save
backups (saves) stay.

The next time the launcher finds DSiRPC, it offers the new SD card files
(A updates, B not now): it downloads and checks them over Wi-Fi, swaps
them in and exits, and you start it again. Auto-update in the launcher's
settings (L+R) and Console updates in DSiRPC's menu turn this off. Coming
from v0.8.1 or older? Copy the SD card files by hand this once.

To remove DSiRPC, turn off "Start with Windows" in its menu, quit it,
and delete this folder (move the saves folder out first to keep your
save backups).

DSiRPC is an unofficial fan project, not affiliated with Nintendo, The
Pokemon Company or RetroAchievements. Licenses: see the licenses folder.
