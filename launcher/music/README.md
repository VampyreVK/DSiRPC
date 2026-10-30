# The menu music

`bright.m8s` and `subtle.m8s` are the launcher's two songs, saved by a
Dirtywave M8 (firmware 6 or later). The launcher doesn't play these files:
`tools/make_music.py` turns them into XM modules in `launcher/audio/`, and
those are what the console plays (maxmod) and what DSiRPC's overlay window
plays on the PC (the tray's Ambient music). How it all fits is in
[launcher/README.md](../README.md#the-menu-music).

## Changing a song

1. Edit it on the M8, then copy the song over `bright.m8s` or `subtle.m8s`
   here (same name: the launcher knows them by it).
2. Make the modules again, from the repo root:

   ```
   python tools/make_music.py
   ```

   It prints each song's notes, tempo and groove, and rewrites
   `launcher/audio/bright.xm` and `subtle.xm`. To see a song as it reads
   it first (tempo, groove, each instrument's notes and range, as the M8
   names them; `--notes` lists every note):

   ```
   python tools/m8s.py launcher/music/subtle.m8s
   ```

3. Run the music tests:

   ```
   python -m pytest tests/test_music.py
   ```

   `test_reads_the_songs` checks each song's name, tempo, groove, length,
   instruments and note counts, so after a change it says what's new:
   update those numbers in `tests/test_music.py` once the song sounds right.
   The other tests check the modules against the songs (up to date, every
   note in place, in tune) and need no changes.
4. Build the launcher (it packs the modules into maxmod's soundbank):

   ```
   docker run --rm -v "$PWD/launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest
   ```

The PC side needs nothing more: the overlay plays `launcher/audio/*.xm`
straight from there, and the Windows and Mac builds ship that folder.

## What carries over from the M8

- The song's first block: rows from 00 down to the first empty one.
- Notes, velocities, instruments, the groove and the tempo. Not the FX
  commands, tables, modulators or effects.
- The voices come from the instrument's name, not its settings:
  `LEAD`, `KEYS`, `BASS`, `BELL` (single-cycle sine, triangle or soft square
  waves with an envelope; the lead and the bell get an echo) and `KICK`,
  `SNAP`, `HAT`, `RIM`, `SHAKER` (filtered noise hits). Each song's voices
  are in `VOICES` at the top of `tools/make_music.py`, the place to change
  how one sounds. Another name gets a voice from the M8 instrument's
  waveform.

## Limits

- 12 channels at most, counting the echoes and the lead's second voice
  (the console keeps the other 4 for the menu sounds); `make_music.py`
  says so if a song needs more.
- Mind the lowest bass notes: the DSi's and 3DS's speakers barely go below
  100 Hz or so. Subtle's soft triangle bass rattled them on F2 (the M8's
  F-4), so those notes moved up to F3 (F-5). Bright's square-ish bass goes
  down to D#2 (D#4) and has sounded fine so far. Note names: the M8 counts
  octaves from MIDI's note number // 12 + 1, so middle C (MIDI 60) is its C-6
  (`python tools/m8s.py` prints the M8's names).
