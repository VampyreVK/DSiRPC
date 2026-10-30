"""
make_music.py - the launcher's menu music (Music in its settings): turns the
two songs made on a Dirtywave M8 into XM modules for maxmod, which plays
them on the DS's ARM7 (launcher/source/music.c).

    python tools/make_music.py

    launcher/music/bright.m8s  ->  launcher/audio/bright.xm
    launcher/music/subtle.m8s  ->  launcher/audio/subtle.xm

The launcher's build packs launcher/audio/ into its soundbank (mmutil). Run
this again after changing a song on the M8 (copy the .m8s back over the one
in launcher/music/ first).

The DS doesn't try to sound like the M8. Its voices are the ones the songs'
browser preview used, picked by each instrument's name: a single cycle of a
sine, triangle or soft square wave, looped, with a volume envelope (a quick
attack, a hold, then an exponential decay), or for the drums a one-shot hit
of filtered noise. The lead's and bell's notes come back softer 3 steps
later on channels of their own (the preview's echo), and the lead and bell
each take turns on two channels so their notes ring over each other. The
groove (Subtle's swing) becomes a speed change on every row that needs one.
The M8's FX commands, tables, filters and effects aren't carried over.
"""

import math
import os
import random
import struct
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m8s  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS = os.path.join(REPO, "launcher", "music")
AUDIO = os.path.join(REPO, "launcher", "audio")

ECHO_STEPS = 3          # the echo comes back this many steps later
MAX_CHANNELS = 12       # maxmod's; the launcher keeps channels 12-15 for its sounds
NOISE_RATE = 32768      # the drum hits are made (and played) at this rate
AMPLITUDE = 30000       # a wave's peak, of 32767
PATTERN_ROWS = 64


@dataclass(frozen=True)
class Voice:
    level: float                # the preview's gain (the loudest note, before velocity)
    decay: float                # seconds to fade to about -60 dB
    wave: str = ""              # "sine", "triangle" or "square" (soft); or
    noise: str = ""             # "bandpass" or "highpass": a drum hit
    attack: float = 0.0
    hold: float = 0.0
    cutoff: float = 0.0         # the noise's filter, or the soft square's low-pass
    q: float = 0.7
    echo: float = 0.0           # how loud the echo comes back
    poly: bool = False          # two channels, so notes ring over each other


# The browser preview's voices, by song and then instrument name
VOICES = {
    "bright": {
        "LEAD": Voice(0.14, 0.28, wave="sine", attack=0.004, hold=0.03, echo=0.3, poly=True),
        "KEYS": Voice(0.06, 0.7, wave="triangle", attack=0.003),
        "BASS": Voice(0.16, 0.25, wave="square", attack=0.003, hold=0.04, cutoff=900, q=1.2),
        "BELL": Voice(0.06, 0.3, wave="sine", attack=0.002, echo=0.4, poly=True),
        "KICK": Voice(0.5, 0.14, wave="sine", attack=0.002),
        "SNAP": Voice(0.12, 0.07, noise="bandpass", cutoff=2600, q=3),
        "HAT": Voice(0.04, 0.025, noise="highpass", cutoff=8500, q=0.7),
    },
    "subtle": {
        "LEAD": Voice(0.16, 0.6, wave="triangle", attack=0.03, hold=0.08, echo=0.25, poly=True),
        "KEYS": Voice(0.075, 0.5, wave="sine", attack=0.004),
        "BASS": Voice(0.28, 0.4, wave="triangle", attack=0.003, hold=0.05),
        "BELL": Voice(0.05, 0.5, wave="sine", attack=0.002, echo=0.45, poly=True),
        "RIM": Voice(0.1, 0.035, noise="bandpass", cutoff=3200, q=4),
        "SHAKER": Voice(0.035, 0.025, noise="highpass", cutoff=8500, q=0.7),
    },
}
# For an instrument a song's table doesn't name (a new one, made on the M8)
FALLBACK = {
    "SINE": Voice(0.08, 0.4, wave="sine", attack=0.003),
    "TRIANGLE": Voice(0.08, 0.4, wave="triangle", attack=0.003),
    "NOISE": Voice(0.05, 0.05, noise="highpass", cutoff=6000),
}
DEFAULT = Voice(0.08, 0.4, wave="square", attack=0.003, cutoff=1500, q=0.7)


def voice_for(song_name, instrument):
    table = VOICES.get(song_name, {})
    if instrument.name in table:
        return table[instrument.name]
    for v in VOICES.values():
        if instrument.name in v:
            return v[instrument.name]
    return FALLBACK.get(instrument.shape, DEFAULT)


# -- samples ---------------------------------------------------------------------

def lowpass_gain(f, cutoff, q):
    """A two-pole low-pass filter's gain at f"""
    r = f / cutoff
    return 1 / math.sqrt((1 - r * r) ** 2 + (r / q) ** 2)


def wave_cycle(voice, length, f0):
    """One cycle of the voice's wave, length samples, starting at 0 (so a
    note starts without a click). f0: a frequency the voice plays, for the
    soft square's filter."""
    out = []
    for i in range(length):
        x = i / length
        if voice.wave == "sine":
            v = math.sin(2 * math.pi * x)
        elif voice.wave == "triangle":
            v = 4 * x if x < 0.25 else 2 - 4 * x if x < 0.75 else 4 * x - 4
        else:
            # A square's odd harmonics through the voice's low-pass
            v = sum(math.sin(2 * math.pi * h * x) / h * (lowpass_gain(h * f0, voice.cutoff, voice.q)
                                                           if voice.cutoff else 1)
                    for h in range(1, 30, 2))
        out.append(v)
    peak = max(abs(v) for v in out)
    return [round(AMPLITUDE * v / peak) for v in out]


def biquad(kind, cutoff, q, rate):
    """RBJ cookbook coefficients: (b0, b1, b2, a1, a2), normalized"""
    w = 2 * math.pi * cutoff / rate
    alpha = math.sin(w) / (2 * q)
    cos = math.cos(w)
    if kind == "bandpass":
        b = (alpha, 0.0, -alpha)
    else:
        b = ((1 + cos) / 2, -(1 + cos), (1 + cos) / 2)
    a0, a1, a2 = 1 + alpha, -2 * cos, 1 - alpha
    return (b[0] / a0, b[1] / a0, b[2] / a0, a1 / a0, a2 / a0)


def noise_hit(voice, seed):
    """White noise (as the preview's, -1 to 1) through the voice's filter,
    fading to about -60 dB over its decay, at NOISE_RATE"""
    rnd = random.Random(seed)
    b0, b1, b2, a1, a2 = biquad(voice.noise, voice.cutoff, voice.q, NOISE_RATE)
    x1 = x2 = y1 = y2 = 0.0
    n = int(NOISE_RATE * voice.decay) + 1
    attack = max(1, int(NOISE_RATE * 0.002))
    out = []
    for i in range(n):
        x = rnd.uniform(-1, 1)
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        env = min(1.0, (i + 1) / attack) * 10 ** (-3 * i / n)
        out.append(max(-32767, min(32767, round(32767 * y * env))))
    return out


def tuning(rate_at_c4):
    """The XM sample's relative note and finetune for a sample that should
    play at rate_at_c4 Hz on C-4 (FT2's linear frequencies: C-4 is 8363 Hz)"""
    s = 12 * math.log2(rate_at_c4 / 8363)
    rel = round(s)
    fine = round((s - rel) * 128)
    if fine > 127:
        rel, fine = rel + 1, fine - 128
    return rel, fine


def cycle_length(top_hz):
    """The longest cycle (smoothest at the low end) whose top note still
    plays at 65 kHz or less"""
    for length in (256, 128, 64, 32):
        if top_hz * length <= 65535:
            return length
    return 16


def midi_hz(n):
    return 440 * 2 ** ((n - 69) / 12)


def envelope(voice, tick):
    """XM volume envelope points [(tick, 0-64)]: the attack, the hold, then
    an exponential fall to silence over the decay"""
    pts = []
    t = voice.attack
    if t >= tick:
        pts += [(0, 8), (round(t / tick), 64)]
    else:
        pts.append((0, 64))
    if voice.hold >= tick:
        t += voice.hold
        pts.append((round(t / tick), 64))
    else:
        t += voice.hold
    for f in (0.08, 0.17, 0.3, 0.45, 0.65, 1.0):
        pts.append((round((t + f * voice.decay) / tick), round(64 * 10 ** (-3 * f))))
    out = []
    for x, y in pts:
        if out and x <= out[-1][0]:
            x = out[-1][0] + 1
        out.append((x, y))
    out[-1] = (out[-1][0], 0)
    return out[:12]


# -- the module --------------------------------------------------------------------

def plan(song, song_name):
    """Which XM channels each track's notes go to, and the notes themselves:
    [(row, channel, xm note, instrument index, volume)]"""
    used = sorted({n.instrument for n in song.notes})
    voices = {i: voice_for(song_name, song.instruments[i]) for i in used}
    order = {num: k for k, num in enumerate(used)}      # M8 instrument -> XM instrument (0-based)

    top = max((v.level * max((n.velocity for n in song.notes if n.instrument == i), default=0) / 127
               for i, v in voices.items() if song.instruments[i].name != "KICK"), default=0.1)
    loud = top / 0.75           # the loudest note but the kick's plays at about 48 of 64

    channels = 0
    main, echo = {}, {}
    for t in range(m8s.TRACKS):
        played = {n.instrument for n in song.notes if n.track == t}
        if not played:
            continue
        poly = any(voices[i].poly for i in played)
        main[t] = list(range(channels, channels + (2 if poly else 1)))
        channels += len(main[t])
        if any(voices[i].echo > 0 for i in played):
            echo[t] = channels
            channels += 1
    if channels > MAX_CHANNELS:
        raise SystemExit(f"{song_name}: needs {channels} channels, the launcher has {MAX_CHANNELS} for music")
    channels += channels % 2    # XM wants an even number

    events = {}
    turn = {t: 0 for t in main}
    for n in song.notes:
        v = voices.get(n.instrument)
        chans = main[n.track]
        if n.note == m8s.OFF:
            for c in chans:
                events[(n.step, c)] = (97, 0, 0)
            continue
        vol = max(1, min(64, round(64 * v.level * n.velocity / 127 / loud)))
        c = chans[turn[n.track] % len(chans)]
        turn[n.track] += 1
        events[(n.step, c)] = (n.note - 11, order[n.instrument] + 1, vol)
        if v.echo > 0:
            e = round(vol * v.echo)
            if e >= 1:
                events[((n.step + ECHO_STEPS) % song.steps, echo[n.track])] = (n.note - 11, order[n.instrument] + 1, e)
    return used, voices, channels, events


def build_instrument(song, song_name, number, voice, tick, seed):
    ins = song.instruments[number]
    notes = [n.note for n in song.notes if n.instrument == number and n.note != m8s.OFF]
    if voice.noise:
        data = noise_hit(voice, seed)
        # Played at NOISE_RATE on the note the song uses most
        common = max(set(notes), key=notes.count)
        rel, fine = tuning(NOISE_RATE / 2 ** ((common - 60) / 12))
        loop = None
        env = []
    else:
        length = cycle_length(midi_hz(max(notes)))
        f0 = math.sqrt(midi_hz(min(notes)) * midi_hz(max(notes)))
        data = wave_cycle(voice, length, f0)
        rel, fine = tuning(midi_hz(60) * length)
        loop = (0, len(data))
        env = envelope(voice, tick)
    if not -96 <= rel <= 95:
        raise SystemExit(f"{song_name}: {ins.name} can't be tuned")
    return ins.name, data, rel, fine, loop, env


def xm_instrument(name, data, rel, fine, loop, env):
    pts = [0] * 24
    for k, (x, y) in enumerate(env):
        pts[2 * k], pts[2 * k + 1] = x, y
    head = struct.pack("<I22sBH", 263, name.encode("ascii")[:22], 0, 1)
    head += struct.pack("<I", 40) + bytes(96)
    head += struct.pack("<24H", *pts) + struct.pack("<24H", *([0] * 24))
    head += struct.pack("<8B", len(env), 0, 0, 0, 0, 0, 0, 0)
    head += struct.pack("<2B4BH", 1 if env else 0, 0, 0, 0, 0, 0, 0x400) + bytes(22)
    assert len(head) == 263
    size = len(data) * 2
    loop_start, loop_len = (loop[0] * 2, (loop[1] - loop[0]) * 2) if loop else (0, 0)
    kind = 0x10 | (1 if loop else 0)            # 16-bit, forward loop
    sample = struct.pack("<IIIBbBBbB22s", size, loop_start, loop_len, 64, fine, kind, 128, rel, 0,
                         name.encode("ascii")[:22])
    prev, deltas = 0, []
    for v in data:
        deltas.append((v - prev + 32768) % 65536 - 32768)
        prev = v
    return head + sample + struct.pack(f"<{len(deltas)}h", *deltas)


def xm_pattern(rows, channels, cells):
    out = bytearray()
    for r in range(rows):
        for c in range(channels):
            note, ins, vol, fx, param = cells.get((r, c), (0, 0, 0, 0, 0))
            if not (note or ins or vol or fx or param):
                out.append(0x80)
                continue
            flags = 0x80 | (1 if note else 0) | (2 if ins else 0) | (4 if vol else 0) | (8 if fx else 0) | \
                (16 if param else 0)
            out.append(flags)
            out += bytes(x for x in (note, ins, vol, fx, param) if x)
    return struct.pack("<IBHH", 9, 0, rows, len(out)) + bytes(out)


def make_xm(song, song_name, title):
    used, voices, channels, events = plan(song, song_name)
    tick = 2.5 / song.tempo
    instruments = [build_instrument(song, song_name, num, voices[num], tick, seed=k + 1)
                   for k, num in enumerate(used)]

    patterns = []
    for start in range(0, song.steps, PATTERN_ROWS):
        rows = min(PATTERN_ROWS, song.steps - start)
        cells = {}
        for (step, c), (note, ins, vol) in events.items():
            if start <= step < start + rows:
                cells[(step - start, c)] = (note, ins, 0x10 + vol if vol else 0, 0, 0)
        # The groove: the speed (ticks a row) wherever it changes, and at the
        # top of every pattern so a loop starts right
        speed = None
        for r in range(rows):
            want = song.groove[(start + r) % len(song.groove)]
            if want != speed:
                note, ins, vol, _, _ = cells.get((r, 0), (0, 0, 0, 0, 0))
                cells[(r, 0)] = (note, ins, vol, 0x0F, want)
                speed = want
        patterns.append(xm_pattern(rows, channels, cells))

    bpm = max(32, min(255, round(song.tempo)))
    head = b"Extended Module: " + title.encode("ascii")[:20].ljust(20) + b"\x1a"
    head += b"make_music.py".ljust(20) + struct.pack("<H", 0x0104)
    orders = bytes(range(len(patterns))).ljust(256, b"\0")
    head += struct.pack("<IHHHHHHHH", 276, len(patterns), 0, channels, len(patterns), len(instruments), 1,
                        song.groove[0], bpm) + orders
    return head + b"".join(patterns) + b"".join(xm_instrument(*i) for i in instruments)


def main():
    os.makedirs(AUDIO, exist_ok=True)
    for name in ("bright", "subtle"):
        song = m8s.read(os.path.join(SONGS, name + ".m8s"))
        data = make_xm(song, name, "DSiRPC " + name.capitalize())
        out = os.path.join(AUDIO, name + ".xm")
        with open(out, "wb") as f:
            f.write(data)
        print(f"{os.path.relpath(out, REPO)}: {len(song.notes)} notes, {song.tempo:g} BPM, "
              f"groove {song.groove}, {len(data)} bytes")


if __name__ == "__main__":
    main()
