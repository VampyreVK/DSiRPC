# RetroAchievements set files

A *set* is a game's RetroAchievements data: its achievements, its rich
presence script, its title and icon. DSiRPC keeps one per game here, as
`<game code>.json` (e.g. `AMCE.json` for Mario Kart DS), and uses it to check
the game's achievements while you play and to show its rich presence in
Discord and on your RetroAchievements profile (see `core/ra_game.py`).

How sets get here:

- **On their own, signed in.** With a RetroAchievements account in
  `dsirpc.cfg` (Setup.bat signs in), DSiRPC works out which game the DSi runs
  and downloads its set: by the hash of your copy of the game (the `roms`
  folder in `dsirpc.cfg`), else by the game's title when exactly one
  RetroAchievements game clearly matches. Sets are downloaded again when
  they're more than a day old.
- **Setup** (`dsirpc.py setup`): for the game the DSi runs now, or any game
  code you type, it lists the possible sets (from RetroAchievements, or from
  RALibretro's cache) and saves the one you pick. It can also search
  RetroAchievements by name.
- **From RALibretro's cache.** RALibretro keeps the set of every game you've
  played in it as `RACache\Data\<RA game ID>.json`. With its folder in
  `dsirpc.cfg` (`racache`), DSiRPC copies a game's set from there when
  exactly one clearly matches (`auto_import`).
- **By hand:** `python tools/ra_tool.py add <file>` while the game runs on the
  DSi (or with `--code AMCE`).

Everything here is ignored by git (it's RetroAchievements' data, and your
own state):

- `<game code>.json`: the set for that game code
- `games.txt` (optional): lines like `AMCE 12711` to use `12711.json` for `AMCE`
- `cache/`: RetroAchievements' lists of DS and DSi games (for matching
  titles, kept a week), which of your game files is which game
  (`roms.json`), and unlocks waiting to be sent (`pending_unlocks.json`)
