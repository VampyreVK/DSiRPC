"""The launcher's menu music: the M8 songs (launcher/music/*.m8s) as
tools/m8s.py reads them, and the XM modules tools/make_music.py makes from
them (launcher/audio/*.xm, packed into the launcher by mmutil), read back
here with a reader of their own."""

import collections
import os
import struct
import sys

import pytest

from helpers import REPO

sys.path.insert(0, os.path.join(REPO, "tools"))
import m8s  # noqa: E402
import make_music  # noqa: E402

SONGS = os.path.join(REPO, "launcher", "music")
AUDIO = os.path.join(REPO, "launcher", "audio")


def song(name):
    return m8s.read(os.path.join(SONGS, name + ".m8s"))


# -- an XM reader --------------------------------------------------------------

def read_xm(path):
    with open(path, "rb") as f:
        d = f.read()
    assert d[:17] == b"Extended Module: " and d[37] == 0x1A
    assert struct.unpack_from("<H", d, 58)[0] == 0x0104
    size = struct.unpack_from("<I", d, 60)[0]
    length, restart, channels, n_patterns, n_instruments, flags, speed, bpm = struct.unpack_from("<8H", d, 64)
    xm = {"channels": channels, "linear": flags & 1, "speed": speed, "bpm": bpm, "restart": restart,
          "orders": list(d[80:80 + length]), "patterns": [], "instruments": []}
    at = 60 + size
    for _ in range(n_patterns):
        head, packing, rows, packed = struct.unpack_from("<IBHH", d, at)
        assert packing == 0
        data, i, cells = d[at + head:at + head + packed], 0, {}
        at += head + packed
        for r in range(rows):
            for c in range(channels):
                b = data[i]
                i += 1
                if b & 0x80:
                    cell = []
                    for bit in range(5):
                        if b & (1 << bit):
                            cell.append(data[i])
                            i += 1
                        else:
                            cell.append(0)
                else:
                    cell = [b] + list(data[i:i + 4])
                    i += 4
                if any(cell):
                    cells[(r, c)] = tuple(cell)
        assert i == len(data)
        xm["patterns"].append((rows, cells))
    for _ in range(n_instruments):
        isize = struct.unpack_from("<I", d, at)[0]
        name = d[at + 4:at + 26].rstrip(b"\0").decode()
        n_samples = struct.unpack_from("<H", d, at + 27)[0]
        assert n_samples == 1
        points = struct.unpack_from("<24H", d, at + 129)
        n_points, vol_type = d[at + 225], d[at + 233]
        s = at + isize
        length, loop_start, loop_len, volume, fine, kind, pan, rel = struct.unpack_from("<IIIBbBBb", d, s)
        at = s + 40
        deltas = struct.unpack_from(f"<{length // 2}h", d, at)
        at += length
        samples, v = [], 0
        for x in deltas:
            v = (v + x + 32768) % 65536 - 32768
            samples.append(v)
        xm["instruments"].append({
            "name": name, "envelope": [(points[2 * k], points[2 * k + 1]) for k in range(n_points)],
            "envelope_on": vol_type & 1, "samples": samples, "loop": (loop_start, loop_len) if kind & 3 else None,
            "bits16": bool(kind & 0x10), "rel": rel, "fine": fine, "volume": volume})
    assert at == len(d)
    return xm


def all_cells(xm):
    """{(song row, channel): cell} across the patterns, in order"""
    out, start = {}, 0
    for p in xm["orders"]:
        rows, cells = xm["patterns"][p]
        for (r, c), cell in cells.items():
            out[(start + r, c)] = cell
        start += rows
    return out, start


def hz(note, rel, fine):
    """FT2's linear frequency for an XM note (1 = C-0)"""
    return 8363 * 2 ** ((note - 1 + rel - 48) / 12 + fine / 1536)


def midi_hz(n):
    return 440 * 2 ** ((n - 69) / 12)


def cents(a, b):
    return abs(1200 * (a - b) / b) if b else 0


# -- the songs ------------------------------------------------------------------

def test_reads_the_songs():
    bright, subtle = song("bright"), song("subtle")
    assert (bright.name, bright.tempo, bright.groove, bright.steps) == ("MENU BRIGHT", 122.0, [6, 6], 256)
    assert (subtle.name, subtle.tempo, subtle.groove, subtle.steps) == ("MENU SUBTLE", 100.0, [7, 7, 5, 5], 256)
    assert [i.name for i in bright.instruments.values()] == ["LEAD", "KEYS", "BASS", "BELL", "KICK", "SNAP", "HAT"]
    assert [i.name for i in subtle.instruments.values()] == ["LEAD", "KEYS", "BASS", "BELL", "RIM", "SHAKER"]
    assert sorted(collections.Counter(n.track for n in bright.notes).items()) == \
        [(0, 59), (1, 40), (2, 40), (3, 40), (4, 96), (5, 18), (6, 75), (7, 256)]
    assert len(subtle.notes) == 324
    # Bright opens with the falling maj9 figure (F5 D5 Bb4 G4 Eb4) on steps
    # 2-6, and its echo on 8-12
    first = [(n.step, n.note, n.velocity) for n in bright.notes if n.track == 0][:10]
    assert first == [(2, 77, 96), (3, 74, 96), (4, 70, 96), (5, 67, 96), (6, 63, 96),
                     (8, 77, 54), (9, 74, 54), (10, 70, 54), (11, 67, 54), (12, 63, 54)]
    # Subtle's melody waits for bar 4
    assert min(n.step for n in subtle.notes if n.track == 0) == 3 * 16 + 12


def test_rejects_what_isnt_a_firmware_6_song(tmp_path):
    other = tmp_path / "other.m8s"
    other.write_bytes(b"MThd" + bytes(200000))
    with pytest.raises(m8s.M8Error):
        m8s.read(str(other))
    with open(os.path.join(SONGS, "bright.m8s"), "rb") as f:
        b = bytearray(f.read())
    b[11] = 4                   # saved by firmware 4
    old = tmp_path / "old.m8s"
    old.write_bytes(bytes(b))
    with pytest.raises(m8s.M8Error, match="firmware 6"):
        m8s.read(str(old))


# -- the modules ----------------------------------------------------------------

@pytest.mark.parametrize("name", ["bright", "subtle"])
def test_the_modules_are_up_to_date(name):
    made = make_music.make_xm(song(name), name, "DSiRPC " + name.capitalize())
    with open(os.path.join(AUDIO, name + ".xm"), "rb") as f:
        assert f.read() == made, f"run tools/make_music.py: launcher/audio/{name}.xm is out of date"


@pytest.mark.parametrize("name", ["bright", "subtle"])
def test_the_modules_play_the_songs(name):
    s, xm = song(name), read_xm(os.path.join(AUDIO, name + ".xm"))
    assert xm["linear"] and xm["bpm"] == round(s.tempo) and xm["speed"] == s.groove[0] and xm["restart"] == 0
    assert xm["channels"] <= make_music.MAX_CHANNELS and xm["channels"] % 2 == 0
    cells, rows = all_cells(xm)
    assert rows == s.steps

    # Every note of the song, at its row, at its pitch (XM's C-4 is MIDI 60)
    played = collections.Counter((r, c[0]) for (r, _), c in cells.items() if c[0])
    wanted = collections.Counter((n.step, n.note - 11) for n in s.notes)
    assert not wanted - played
    # ... plus one echo for each of the lead's and the bell's, 3 steps later
    names = {i.number: i.name for i in s.instruments.values()}
    echoes = sum(1 for n in s.notes if names[n.instrument] in ("LEAD", "BELL"))
    assert sum(played.values()) == len(s.notes) + echoes
    for n in s.notes:
        if names[n.instrument] == "LEAD":
            row = (n.step + make_music.ECHO_STEPS) % s.steps
            assert (row, n.note - 11) in played

    # The groove: the speed in force on each row
    speed = None
    for r in range(rows):
        c = cells.get((r, 0))
        if c and c[3] == 0x0F:
            speed = c[4]
        assert speed == s.groove[r % len(s.groove)], f"row {r}"


@pytest.mark.parametrize("name", ["bright", "subtle"])
def test_the_samples_are_in_tune(name):
    s, xm = song(name), read_xm(os.path.join(AUDIO, name + ".xm"))
    cells, _ = all_cells(xm)
    for k, ins in enumerate(xm["instruments"]):
        notes = [c[0] for c in cells.values() if c[1] == k + 1 and c[0]]
        assert notes and ins["bits16"] and ins["volume"] == 64
        if ins["loop"]:
            # One cycle of a wave, looped: every note it plays is in tune
            assert ins["loop"] == (0, len(ins["samples"]) * 2)
            assert ins["samples"][0] == 0               # starts at 0: no click
            for note in set(notes):
                tone = hz(note, ins["rel"], ins["fine"]) / len(ins["samples"])
                assert cents(tone, midi_hz(note + 11)) < 1, (ins["name"], note)
            env = ins["envelope"]
            assert ins["envelope_on"] and 2 <= len(env) <= 12
            assert all(a[0] < b[0] for a, b in zip(env, env[1:])) and env[-1][1] == 0
            assert max(y for _, y in env) == 64
        else:
            # A drum hit, played at 32768 Hz on its usual note, fading out
            common = max(set(notes), key=notes.count)
            assert cents(hz(common, ins["rel"], ins["fine"]), make_music.NOISE_RATE) < 1, ins["name"]
            assert not ins["envelope_on"]
            tail = ins["samples"][-len(ins["samples"]) // 10:]
            assert max(abs(v) for v in tail) < max(abs(v) for v in ins["samples"]) / 20


def test_the_voices_follow_the_preview():
    s = song("bright")
    voices = {i.name: make_music.voice_for("bright", i) for i in s.instruments.values()}
    assert voices["LEAD"].wave == "sine" and voices["LEAD"].echo == 0.3 and voices["LEAD"].poly
    assert voices["SNAP"].noise == "bandpass" and voices["HAT"].noise == "highpass"
    # An instrument neither song names gets a voice from its wave
    new = m8s.Instrument(9, "WavSynth", "PAD", "TRIANGLE")
    assert make_music.voice_for("bright", new).wave == "triangle"
