DSiRPC {version}
=====================================================================

DSiRPC shows the game you're playing on a modded Nintendo DSi or 3DS as
your Discord status. Pokemon Platinum (USA, Rev 1) gets the full
treatment: where you are, your party, your badges and who you're
battling, with sprites. Any other DS game shows its name, box art and, if
it has a RetroAchievements set, what you're doing in it. Achievements are
checked while you play, even offline, and there's an optional overlay
window for streaming.

More help, and the source code: https://github.com/VampyreVK/DSiRPC


WHAT YOU NEED
---------------------------------------------------------------------
- A DSi or 3DS with TWiLight Menu++ installed.
- The console's Wi-Fi set up for the same network as your PC. (On a DSi,
  a WPA2 network has to be in Connection 4, 5 or 6: System Settings >
  Internet > Connection Settings > Advanced Setup.)
- A 64-bit Windows 10 or 11 PC with the Discord app.
- Your games as .nds files on the SD card. DSi-enhanced games (Pokemon
  Black and White, and later) have to be set to DS mode in TWiLight
  Menu++'s per-game settings.

Nothing needs installing on the PC: this folder has everything.


STEP 1: THE PC
---------------------------------------------------------------------
1. Put this DSiRPC folder somewhere you can write to, like Documents or
   the Desktop (not Program Files).

   If Windows says it "protected your PC" when you open a file: right-click
   the zip you downloaded > Properties > tick "Unblock" > OK, and unzip it
   again. (Or click "More info" > "Run anyway".)

2. Double-click Setup.bat and answer its questions. Press Enter to take
   the suggested answer (the one in [brackets]).
   - Discord: if this download comes with a Discord application, just
     press Enter. Otherwise setup explains how to make one (it's free and
     takes a minute).
   - RetroAchievements is optional: skip it by pressing Enter.

3. Double-click DSiRPC.bat. DSiRPC's icon appears in the taskbar's
   notification area, by the clock. Right-click it for the menu.

   When Windows asks about the firewall, allow access on private
   networks. Without that, DSiRPC never hears from the console.


STEP 2: THE SD CARD
---------------------------------------------------------------------
Copy the DSiRPC folder from the "SD card" folder here to the root of
your console's SD card. You should end up with:

    sd:/DSiRPC/dsirpc-launcher.nds
    sd:/DSiRPC/nds-bootstrap-dsirpc.nds

Keep those two files together, in the same folder.


STEP 3: PLAYING
---------------------------------------------------------------------
1. Start DSiRPC on the PC (DSiRPC.bat), or turn on "Start with Windows"
   in its menu so it's always there.

2. On the console, open DSiRPC/dsirpc-launcher.nds from TWiLight Menu++.
   It connects to Wi-Fi (it tries up to 3 times) and shows the IP
   address. It has to run in DSi mode; if it says it's in DS mode, change
   that in TWiLight Menu++'s per-game settings for it.

3. Press START and pick your game: A opens a folder or picks the game,
   B goes up a folder (the browser opens in the DSiRPC folder, so press B
   to get to your games). The game starts, still connected.

4. Within about 15 seconds, Discord shows what you're playing.

In the launcher, SELECT disconnects and goes back without starting a game.

No Wi-Fi? Press B while the launcher connects (or START when it says it
couldn't) to play offline: games start the same way, without Discord.
Whenever the launcher is connected and DSiRPC is running, the two sync
(B skips it): DSiRPC puts your achievement sets on the SD card and sends
achievements unlocked offline to RetroAchievements. While you play, the
console checks the game's achievements itself and saves what you unlock to
the SD card. On a DSi, the LED you picked as TWiLight Menu++'s "ROM read
LED" pulses while there are new unlocks; opening nds-bootstrap's in-game
menu (L + Down + SELECT) stops it. A 3DS has no such LED; the menu says
what's new instead. That menu also lists the game's achievements (its
Achievements item), earned ones first.

A game you've never started from TWiLight Menu++ has no save file yet,
and the launcher says so: start it once from TWiLight Menu++ first.


IF SOMETHING DOESN'T WORK
---------------------------------------------------------------------
- Right-click DSiRPC's tray icon: the first lines say what it sees (the
  game, Discord, RetroAchievements).
- Nothing on Discord: the PC and the console have to be on the same
  network, and the firewall has to allow DSiRPC (Windows Security >
  Firewall > Allow an app: python.exe and pythonw.exe from this folder's
  python folder, on private networks). Turn off other Rich Presence
  plugins, like Vencord's CustomRPC.
- Discord shows nothing while the tray icon's dot is red: Discord isn't
  running, or setup has no Discord application yet (run Setup.bat).
- The launcher can't connect: check the console's Wi-Fi settings.
- Discord stopped after closing a DSi's lid: that's on purpose (a DSi
  that sleeps while connected switches itself off). Achievements are
  still checked and saved; start the game from the launcher again to
  reconnect.
- DSiRPC's log is logs\dsirpc.log in this folder (tray menu > Open log).


UPDATING AND REMOVING
---------------------------------------------------------------------
To update, unzip the new release over this folder (replace the files
when asked). Your settings (dsirpc.cfg) and achievement sets (ra) stay.
Copy the new SD card files over the old ones too.

To remove DSiRPC, turn off "Start with Windows" in its menu, quit it,
and delete this folder.

DSiRPC is an unofficial fan project, not affiliated with Nintendo, The
Pokemon Company or RetroAchievements. Licenses: see the licenses folder.
