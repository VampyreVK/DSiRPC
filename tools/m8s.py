"""
m8s.py - reads a Dirtywave M8 song (.m8s) far enough to play it elsewhere:
the tempo, groove 00, the song's first block of rows, every note its chains
and phrases play there, and the instruments' names. The launcher's menu
music is made from these (tools/make_music.py).

    song = m8s.read("launcher/music/bright.m8s")
    song.tempo, song.groove, song.steps          # 122.0, [6, 6], 256
    song.notes[0]                                # Note(step=2, track=0, ...)

From the command line it prints a song as it reads it (--notes: every note
too), to check one copied from the M8 before making the music:

    python tools/m8s.py launcher/music/subtle.m8s [--notes]

The offsets are a firmware 6 song's (112294 bytes or more), as the
m8-file-parser library (MIT) reads them. An M8 note is a MIDI note number
(its 11 octaves cover all 128, shown as octave = note // 12 + 1, so middle
C, 60, is its C-6). Phrase FX and tables aren't read: the launcher's player
doesn't do them.
"""

import argparse
import struct
import sys
from dataclasses import dataclass, field

TEMPO, TRANSPOSE, NAME = 143, 142, 148
GROOVES, SONG, PHRASES, CHAINS, INSTRUMENTS = 0xEE, 0x2EE, 0xAEE, 0x9A5E, 0x13A3E
STEP, PHRASE, CHAIN, INSTRUMENT = 9, 144, 32, 215
TRACKS, ROWS, EMPTY, OFF = 8, 256, 0xFF, 0x80
KINDS = {0: "WavSynth", 1: "MacroSynth", 2: "Sampler", 3: "MIDI Out", 4: "FM Synth", 5: "HyperSynth",
         6: "External"}
WAV_SHAPES = {0: "PULSE12", 1: "PULSE25", 2: "PULSE50", 3: "PULSE75", 4: "SAW", 5: "TRIANGLE", 6: "SINE",
              7: "NOISE_PITCHED", 8: "NOISE"}


class M8Error(ValueError):
    pass


@dataclass(frozen=True)
class Note:
    step: int           # 16ths from the start of the song
    track: int          # 0-7
    note: int           # MIDI note number, or OFF (the note before stops)
    velocity: int       # 0-127
    instrument: int     # 0-127


@dataclass(frozen=True)
class Instrument:
    number: int
    kind: str           # "WavSynth", ...
    name: str           # what the M8 shows, e.g. "LEAD"
    shape: str          # a WavSynth's wave ("SINE", ...), or ""


@dataclass
class Song:
    name: str
    tempo: float                    # BPM
    groove: list                    # groove 00: ticks per step (6 is straight)
    steps: int                      # the loop's length in 16ths
    notes: list = field(default_factory=list)          # [Note], by step
    instruments: dict = field(default_factory=dict)    # {number: Instrument}


def _text(raw):
    end = len(raw)
    for i, b in enumerate(raw):
        if b in (0, 0xFF):
            end = i
            break
    return raw[:end].decode("ascii", "replace")


def _signed(b):
    return b - 256 if b >= 128 else b


def _version(b):
    if b[:9] != b"M8VERSION":
        raise M8Error("not an M8 song")
    return b[11] & 0x0F, b[10] >> 4


def read(path):
    with open(path, "rb") as f:
        b = f.read()
    major, _ = _version(b)
    if major < 6 or len(b) < INSTRUMENTS + 128 * INSTRUMENT:
        raise M8Error(f"{path}: only songs saved by M8 firmware 6 or later can be read")

    groove = []
    for t in b[GROOVES:GROOVES + 16]:
        if t == EMPTY:
            break
        groove.append(t)
    song = Song(name=_text(b[NAME:NAME + 12]), tempo=struct.unpack_from("<f", b, TEMPO)[0],
                groove=groove or [6, 6], steps=0)
    song_transpose = _signed(b[TRANSPOSE])

    # The song's first block: rows from 00 up to the first empty one. Each
    # track plays its own chains down the block, so each has a length; the
    # block's is the longest, and shorter tracks start over within it.
    rows = []
    for r in range(ROWS):
        row = b[SONG + r * TRACKS:SONG + (r + 1) * TRACKS]
        if all(c == EMPTY for c in row):
            break
        rows.append(row)
    if not rows:
        raise M8Error(f"{path}: the song's row 00 is empty")

    per_track = []
    for t in range(TRACKS):
        notes, at = [], 0
        instrument, velocity = 0, 0x7F
        for row in rows:
            c = row[t]
            if c == EMPTY:
                continue
            for s in range(16):
                phrase, transpose = b[CHAINS + c * CHAIN + s * 2], _signed(b[CHAINS + c * CHAIN + s * 2 + 1])
                if phrase == EMPTY:
                    break
                for i in range(16):
                    n, v, ins = b[PHRASES + phrase * PHRASE + i * STEP:PHRASES + phrase * PHRASE + i * STEP + 3]
                    # An empty instrument or velocity column keeps the one
                    # before, as on the M8
                    if ins != EMPTY:
                        instrument = ins
                    if v != EMPTY:
                        velocity = min(v, 0x7F)
                    if n == EMPTY:
                        continue
                    note = OFF if n >= OFF else n + transpose + song_transpose
                    if note != OFF and not 0 <= note < OFF:
                        raise M8Error(f"{path}: track {t + 1} plays a note out of range")
                    notes.append(Note(at + i, t, note, velocity, instrument))
                at += 16
        per_track.append((notes, at))
    song.steps = max(length for _, length in per_track)
    if song.steps == 0:
        raise M8Error(f"{path}: the song's first block plays nothing")
    for notes, length in per_track:
        if length == 0:
            continue
        for start in range(0, song.steps, length):
            song.notes.extend(Note(n.step + start, n.track, n.note, n.velocity, n.instrument)
                              for n in notes if n.step + start < song.steps)
    song.notes.sort(key=lambda n: (n.step, n.track))

    for number in sorted({n.instrument for n in song.notes}):
        r = b[INSTRUMENTS + number * INSTRUMENT:INSTRUMENTS + (number + 1) * INSTRUMENT]
        if r[0] == EMPTY:
            raise M8Error(f"{path}: instrument {number:02X} is played but empty")
        kind = KINDS.get(r[0], f"kind {r[0]}")
        song.instruments[number] = Instrument(number, kind, _text(r[1:13]),
                                              WAV_SHAPES.get(r[18], "") if r[0] == 0 else "")
    return song


NOTE_NAMES = ("C-", "C#", "D-", "D#", "E-", "F-", "F#", "G-", "G#", "A-", "A#", "B-")


def note_name(n):
    """A note as the M8 shows it (60, middle C: "C-6")."""
    return "OFF" if n >= OFF else f"{NOTE_NAMES[n % 12]}{n // 12 + 1:X}"


def describe(song, notes=False):
    """The song as text: what it plays, as the M8 names the notes."""
    ticks = sum(song.groove[s % len(song.groove)] for s in range(song.steps))
    lines = [f"{song.name}: {song.tempo:g} BPM, groove {' '.join(map(str, song.groove))}, {song.steps} steps "
             f"({ticks * 2.5 / song.tempo:.1f} s a loop), {len(song.notes)} notes"]
    for number, ins in sorted(song.instruments.items()):
        played = [n for n in song.notes if n.instrument == number]
        pitches = [n.note for n in played if n.note != OFF]
        tracks = ", ".join(str(t + 1) for t in sorted({n.track for n in played}))
        span = f"{note_name(min(pitches))} to {note_name(max(pitches))}" if pitches else "no notes"
        what = f"{ins.kind} {ins.shape}".strip()
        lines.append(f"  {number:02X} {ins.name:<12} {what:<18} {len(pitches):4} notes, {span}, track {tracks}")
    if notes:
        lines.append("  step track note vel instrument")
        for n in song.notes:
            name = song.instruments[n.instrument].name if n.instrument in song.instruments else f"{n.instrument:02X}"
            lines.append(f"  {n.step:4} {n.track + 1:5} {note_name(n.note):>4} {n.velocity:3} {name}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Print an M8 song as tools/make_music.py reads it")
    ap.add_argument("song", nargs="+", help=".m8s files")
    ap.add_argument("--notes", action="store_true", help="list every note too")
    args = ap.parse_args()
    for path in args.song:
        try:
            print(describe(read(path), args.notes))
        except (OSError, M8Error) as e:
            sys.exit(f"{path}: {e}")


if __name__ == "__main__":
    main()
