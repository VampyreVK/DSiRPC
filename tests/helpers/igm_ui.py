"""nds-bootstrap's in-game menu in DSiRPC's look, on a PC (tests/c/igm/
igm_host.c runs the menu's own code): building the host, the font and an
achievement set for it, a script of key presses, and its frames, for the
README (tools/render_igm.py) as much as for tests/test_igm_menu.py."""

import os
import struct
import subprocess
import tempfile

from . import REPO, RETAIL, COMMON_INCLUDE, cbuild

IGM_SOURCE = os.path.join(RETAIL, "cardenginei", "arm9_igm", "source")
HOST_DIR = os.path.join(REPO, "tests", "c", "igm")
FONT = os.path.join(RETAIL, "nitrofiles", "fonts", "ascii.lz77")
W, H = 256, 192

# Keys (libnds' input.h)
A, B, RIGHT, LEFT, UP, DOWN, R, L = 1, 2, 16, 32, 64, 128, 256, 512

# The game's achievements, made up: (title, description, points, how it's earned)
# where "pc" is earned as far as DSiRPC knew, "new" earned on this console
# since the menu last opened (newest last), None not yet
CHEEVOS = [
    ("Clean Sweep", "Clear the whole board in Marathon", 10, "new"),
    ("T-Spin Double", "Clear two lines with a T-Spin", 10, "new"),
    ("First Lines", "Clear your first line in any mode", 1, "pc"),
    ("Four at Once", "Clear four lines with one piece", 5, "pc"),
    ("Hold That Thought", "Use the hold box ten times in one game", 2, "pc"),
    ("Level 10", "Reach level 10 in Marathon", 10, None),
    ("Back to Back", "Clear two Tetrises in a row", 10, None),
    ("Speed Demon", "Reach level 15 in Marathon", 25, None),
    ("Marathon Runner", "Clear 150 lines in one game of Marathon", 25, None),
    ("Puzzle Solver", "Finish ten puzzles in Push mode", 5, None),
    ("Mission Complete", "Finish every mission in Mission mode", 25, None),
    ("Century", "Clear 100 lines in one game", 10, None),
]


def build(out, sanitize=True):
    sources = [os.path.join(HOST_DIR, "igm_host.c")] + [os.path.join(IGM_SOURCE, f) for f in
                                                       ("inGameMenu.c", "dsirpc_skin.c", "dsirpc_ach.c")]
    sources.append(os.path.join(RETAIL, "common", "source_general", "tonccpy.c"))
    flags = ["-std=gnu11", "-DARM9", "-DNO_CARDID", "-Wno-unused-function", "-Wno-unused-variable",
             "-Wno-unused-but-set-variable", "-Wno-address", "-Wno-int-to-pointer-cast", "-Wno-pointer-to-int-cast",
             "-include", os.path.join(HOST_DIR, "prelude.h"),
             "-I", os.path.join(HOST_DIR, "stub"), "-I", os.path.join(REPO, "tests", "c", "stubs"),
             "-I", IGM_SOURCE, "-I", COMMON_INCLUDE]
    return cbuild.build(out, sources, flags=flags, sanitize=("address", "undefined") if sanitize else ())


def unlz77(data):
    """The GBA BIOS' LZ77 (type 0x10), as nds-bootstrap packs its fonts."""
    assert data[0] == 0x10, "not LZ77"
    size = data[1] | data[2] << 8 | data[3] << 16
    out, i = bytearray(), 4
    while len(out) < size:
        flags = data[i]
        i += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                n = (data[i] >> 4) + 3
                back = ((data[i] & 0xF) << 8 | data[i + 1]) + 1
                i += 2
                for _ in range(n):
                    out.append(out[-back])
            else:
                out.append(data[i])
                i += 1
    return bytes(out[:size])


def font():
    with open(FONT, "rb") as f:
        return unlz77(f.read())


class _Set:
    """Enough of a RaSet for offline.build_list()"""
    def __init__(self, cheevos):
        self.playable_achievements = [{"id": 5000 + i, "title": t, "description": d, "points": p}
                                      for i, (t, d, p, _) in enumerate(cheevos)]


def ach_image(cheevos=CHEEVOS, now=None, link=0x80 | 2 << 4):
    """DSIRPC_ACH_LOCATION's RAM as the ARM7's probe_ach.c leaves it: the
    set's header with the menu's anchor in bytes 40-63, and the list right
    after it (core/offline.py's build_list(), with the console's unlocks
    marked as probe_ach.c marks them). link: rpcprobe's status (sending to
    DSiRPC: the Wi-Fi sign is green)."""
    from core import offline
    import time
    now = int(time.time()) if now is None else now
    raset = _Set(cheevos)
    earned = {5000 + i: now - (len(cheevos) - i) * 86400 for i, c in enumerate(cheevos) if c[3] == "pc"}
    the_list = bytearray(offline.build_list(raset, earned, [5000 + i for i in range(len(cheevos))]))
    clock = offline.console_clock(now)
    seq = 0
    for i, c in enumerate(cheevos):
        if c[3] != "new":
            continue
        seq += 1
        at = offline.LIST_HEADER.size + i * offline.LIST_ENTRY.size
        aid, _, title, desc, points, flags, _ = offline.LIST_ENTRY.unpack_from(the_list, at)
        offline.LIST_ENTRY.pack_into(the_list, at, aid, clock - 60 * (10 - seq), title, desc, points,
                                     flags | offline.LIST_ON_CONSOLE, seq)
    header = bytearray(64)
    header[0:8] = b"DRSE" + struct.pack("<HH", 5, 64)
    header[8:12] = b"TEST"
    # the anchor: "DRMA", the game, ready, the last unlock's number, the
    # number the menu saw last (0: both are new), open, the list, the link
    header[40:64] = struct.pack("<I4shHHHII", 0x414D5244, b"TEST", 2, seq, 0, 1, 64, link)
    return bytes(header) + bytes(the_list)


def script(*steps):
    """[(frames, keys)] -> the host's lines. A key press is held a few frames
    and let go, as a person would."""
    return [f"keys {n} {k}" for n, k in steps]


def press(keys, wait):
    """A press held 4 frames, then `wait` frames with nothing pressed"""
    return [(4, keys), (wait, 0)]


def run(host, commands, version="dev"):
    """Runs the host with these lines before `run` (its font and set
    added); returns its output lines."""
    with tempfile.TemporaryDirectory() as tmp:
        font_path, ach_path = os.path.join(tmp, "font.bin"), os.path.join(tmp, "ach.bin")
        with open(font_path, "wb") as f:
            f.write(font())
        with open(ach_path, "wb") as f:
            f.write(ach_image())
        lines = [f"font {font_path}", f"ach {ach_path}", f"version {version}"] + list(commands) + ["run"]
        r = subprocess.run([host], input="\n".join(lines) + "\n", capture_output=True, text=True,
                           env=cbuild.run_env(), timeout=300)
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert not any(ln.startswith("?") for ln in out), out
    assert out[-1] == "exit", out[-5:]
    return out


def text(out, frame):
    """The text background on that frame (the host's `text` lines): 24 rows of 32"""
    rows = [ln.split("|")[1] for ln in out if ln.startswith(f"text {frame} ")]
    assert len(rows) == 24, f"no text for frame {frame}"
    return rows


def frames(path):
    """The recorded frames: [bytes of 256x192 RGB]"""
    size = W * H * 3
    with open(path, "rb") as f:
        data = f.read()
    return [data[i:i + size] for i in range(0, len(data) - size + 1, size)]
