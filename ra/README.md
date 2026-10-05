# RetroAchievements set files

DSiRPC reads a game's RetroAchievements set from here to show its rich
presence text and icon in Discord and the overlay (see `core/other_game.py`).
It never talks to RetroAchievements itself.

A set file is what an RA emulator downloads while you're logged in:
RALibretro keeps it as `RACache\Data\<RA game ID>.json` after you load the
game once. Three ways to get one here:

- `dsirpc.py setup` (Setup.bat): give it RALibretro's folder, and it lists the
  DS/DSi sets there and copies the one you pick for the game the DSi runs (or
  any game code you type).
- On its own: with RALibretro's folder in `dsirpc.cfg` (`racache`), DSiRPC
  copies a game's set the first time the game runs, if exactly one set's title
  clearly matches the game's (`auto_import`).
- By hand: `python tools/ra_tool.py add <file>` while the game runs on the DSi
  (or with `--code AMCE`).

Files here are ignored by git (they're RA's data).

- `<game code>.json`: the set for that game code (e.g. `AMCE.json`)
- `games.txt` (optional): lines like `AMCE 12711` to use `12711.json` for `AMCE`
