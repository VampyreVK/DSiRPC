"""The launcher's modern look on a PC (tests/c/ui/ui_host.c): building the
host, an SD card for it (games with banners, an achievement set, playtimes,
an unlock waiting), and its screens as pixel-art SVG, for the README
(tools/render_launcher.py) as much as for tests/test_launcher_ui.py."""

import calendar
import os
import struct
import subprocess
import time
import zlib

from . import REPO, cbuild

LAUNCHER = os.path.join(REPO, "launcher", "source")
HOST_DIR = os.path.join(REPO, "tests", "c", "ui")
HOST_SOURCES = ["ui_host.c", "host_stubs.c", "host_main.c", "host_update.c", "host_settings.c", "host_picker.c",
                "host_saves.c"]
LAUNCHER_SOURCES = ["ui.c", "topscreen.c", "browser.c", "sync.c", "savesync.c", "stats.c", "bootstrap_ini.c",
                    "music.c"]
UNIX_2000 = 946684800
KEY = (255, 0, 255)         # the top screen's clear pixels, in a dump with key=1


def build(out, sanitize=True):
    sources = [os.path.join(HOST_DIR, f) for f in HOST_SOURCES] + [os.path.join(LAUNCHER, f) for f in LAUNCHER_SOURCES]
    flags = ["-std=gnu11", "-D__NDS__", "-I", os.path.join(HOST_DIR, "stub"), "-I", HOST_DIR, "-I", LAUNCHER]
    return cbuild.build(out, sources, flags=flags, sanitize=("address", "undefined") if sanitize else ())


def run(host, *commands, cwd=None):
    r = subprocess.run([host], input="\n".join(commands) + "\n", capture_output=True, text=True, encoding="utf-8",
                       cwd=cwd, env=cbuild.run_env(), timeout=120)
    assert r.returncode == 0, r.stderr
    assert not any(ln.startswith("?") for ln in r.stdout.splitlines()), r.stdout
    return r.stdout.splitlines()


def console_now():
    """The console's clock: seconds since 2000, local time."""
    return calendar.timegm(time.localtime()) - UNIX_2000


# -- an SD card -------------------------------------------------------------------

def bgr555(r, g, b):
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def icon(kind, colors):
    """A 32x32 banner icon of a simple shape (4 bits a pixel, 4x4 tiles of
    8x8, the low nibble on the left) and its palette."""
    px = [[0] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            dx, dy = x - 15.5, y - 15.5
            d = (dx * dx + dy * dy) ** 0.5
            if kind == "ball":
                if d < 14:
                    px[y][x] = 1 if y < 15 else 2
                if d < 14 and abs(dy) < 1.5 or d < 5:
                    px[y][x] = 3
                if d < 3:
                    px[y][x] = 4
            elif kind == "box":
                if 3 <= x < 29 and 3 <= y < 29:
                    px[y][x] = 1
                if 7 <= x < 25 and 7 <= y < 18:
                    px[y][x] = 2
                if 9 <= x < 15 and 21 <= y < 26:
                    px[y][x] = 3
            elif kind == "blocks":
                if 4 <= x < 28 and 4 <= y < 28:
                    px[y][x] = 1
                for bx, by, c in ((8, 18, 2), (14, 18, 3), (14, 12, 4), (20, 18, 2)):
                    if bx <= x < bx + 6 and by <= y < by + 6:
                        px[y][x] = c
            elif kind == "leaf":
                if (dx * dx * 1.6 + dy * dy) ** 0.5 < 13:
                    px[y][x] = 1
                if abs(dx) < 1 and dy > -10:
                    px[y][x] = 2
                if dy > 10 and abs(dx) < 3:
                    px[y][x] = 3
    tiles = bytearray(512)
    for t in range(16):
        for row in range(8):
            for col in range(4):
                x, y = (t % 4) * 8 + col * 2, (t // 4) * 8 + row
                tiles[t * 32 + row * 4 + col] = px[y][x] | (px[y][x + 1] << 4)
    pal = [0] + [bgr555(*c) for c in colors]
    return bytes(tiles), pal + [0] * (16 - len(pal))


def rom(code, title, kind="box", colors=((200, 50, 50), (240, 200, 60), (250, 250, 250)), version=0, banner=True):
    """A small .nds: its header (code, version, the banner's offset) and,
    unless banner is False, a banner with an icon and its title in every
    language (UTF-16, lines split at '\\n')."""
    data = bytearray(0x200 + 0x840)
    data[0:12] = b"TESTGAME\0\0\0\0"
    data[0x0C:0x10] = code.encode()
    data[0x1E] = version
    if banner:
        struct.pack_into("<I", data, 0x68, 0x200)
        tiles, pal = icon(kind, colors)
        struct.pack_into("<H", data, 0x200, 1)
        data[0x220:0x420] = tiles
        struct.pack_into("<16H", data, 0x420, *pal)
        text = title.encode("utf-16-le")
        for lang in range(6):
            at = 0x440 + lang * 0x100
            data[at:at + len(text)] = text
    return bytes(data)


GAMES = [
    ("Pokemon Platinum.nds", "CPUE", "Pokémon Platinum Version\nNintendo", "ball",
     ((120, 120, 136), (220, 220, 230), (40, 40, 48), (240, 200, 60)), 1),
    ("Pokemon Black.nds", "IRBO", "Pokémon Black Version\nNintendo", "ball",
     ((40, 40, 44), (200, 200, 210), (20, 20, 24), (90, 200, 230)), 0),
    ("Mario Kart DS.nds", "AMCE", "Mario Kart DS\nNintendo", "box",
     ((200, 50, 50), (240, 200, 60), (250, 250, 250)), 0),
    ("Animal Crossing WW.nds", "ADME", "Animal Crossing\nWild World\nNintendo", "leaf",
     ((80, 170, 80), (140, 90, 40), (120, 80, 40)), 0),
    ("Tetris DS.nds", "ATRE", "Tetris DS\nNintendo", "blocks",
     ((50, 80, 200), (230, 70, 60), (240, 200, 60), (90, 200, 120)), 0),
    ("Professor Layton.nds", "A5FE", "Professor Layton and the Curious Village\nNintendo", "box",
     ((120, 80, 40), (230, 210, 170), (60, 40, 20)), 0),
    ("Zelda PH.nds", "AZEE", "The Legend of Zelda\nPhantom Hourglass\nNintendo", "leaf",
     ((60, 140, 60), (240, 220, 120), (90, 60, 30)), 0),
    ("Club Penguin.nds", "YCPE", "Club Penguin\nElite Penguin Force\nDisney", "ball",
     ((30, 70, 140), (240, 240, 250), (20, 30, 60), (240, 200, 60)), 0),
]

# Platinum's set: (ID, title, description, points, earned)
CHEEVOS = [
    (1001, "Starter Pokemon", "Choose your first Pokemon", 5, True),
    (1002, "First Gym", "Beat Roark at the Oreburgh Gym", 10, True),
    (1003, "Second Gym", "Beat Gardenia at the Eterna Gym and get the Forest Badge", 10, False),
    (1004, "Bike Ride", "Get the Bicycle in Eterna City", 5, False),
    (1005, "Galactic Trouble", "Defeat Team Galactic at the Valley Windworks", 10, False),
    (1006, "Champion", "Become the Champion of the Sinnoh League", 25, False),
]
WAITING = 1003      # unlocked on the console, in RPCUNLK.BIN


def set_file(code, cheevos, now):
    """An offline set (core/offline.py's CODE.DRS, version 4) with no
    programs, only the list for the menus."""
    text, entries = bytearray(), bytearray()
    for aid, title, desc, points, earned in cheevos:
        title_at = len(text)
        text += title.encode() + b"\0"
        desc_at = len(text)
        text += desc.encode() + b"\0"
        entries += struct.pack("<IIHHBBH", aid, now - 3 * 86400 if earned else 0, title_at, desc_at, points,
                               1 if earned else 4, 0)
    body = struct.pack("<4sHHII", b"DRMN", 1, len(cheevos), len(text), 0) + entries + text
    header = struct.pack("<4sHH4sIIHHIIII24s", b"DRSE", 4, 64, code.encode(), 1234, zlib.crc32(body), len(cheevos),
                         0, 0, 0, len(body), 0, b"\0" * 24)
    return header + body


def unlock_file(unlocks):
    """RPCUNLK.BIN with these (ID, code, when) unlocks waiting."""
    data = bytearray(4096)
    data[0:16] = struct.pack("<4sHHH6x", b"DRUL", 1, 16, 256)
    for i, (aid, code, when) in enumerate(unlocks, 1):
        slot = struct.pack("<I4sIH", aid, code.encode(), when, i)
        check = (0x5AA5 + sum(struct.unpack("<7H", slot))) & 0xFFFF
        data[i * 16:i * 16 + 16] = slot + struct.pack("<H", check)
    return bytes(data)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def make_sd(root, now=None):
    """The SD card: the games in roms/nds, Platinum's set, the PC's
    playtimes (Platinum 41h 12m two days ago, Black an hour 40 days ago) and
    one of Platinum's unlocks waiting. Returns now (the console's clock)."""
    now = console_now() if now is None else now
    for name, code, title, kind, colors, version in GAMES:
        write(os.path.join(root, "roms", "nds", name), rom(code, title, kind, colors, version))
    write(os.path.join(root, "DSiRPC", "sets", "CPUE.DRS"), set_file("CPUE", CHEEVOS, now))
    write(os.path.join(root, "DSiRPC", "stats.idx"),
          f"DSiRPC stats 1\npc GAMING-PC\nra VampyreVK\ndiscord 1\nCPUE 148320 {now - 2 * 86400}\n"
          f"IRBO 3600 {now - 40 * 86400}\n".encode())
    write(os.path.join(root, "RPCUNLK.BIN"), unlock_file([(WAITING, "CPUE", now)]))
    return now


# -- the screens ---------------------------------------------------------------------

def read_ppm(path):
    """(width, height, rows of (r, g, b))"""
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(maxsplit=4)
    assert parts[0] == b"P6"
    w, h = int(parts[1]), int(parts[2])
    pixels = parts[4]
    rows = [[tuple(pixels[(y * w + x) * 3:(y * w + x) * 3 + 3]) for x in range(w)] for y in range(h)]
    return w, h, rows


def rectangles(rows, x0, y0, w, h, skip=None):
    """The pixels as rectangles of one color, {color: [(x, y, w, h)]}: each
    row's runs, a run grown downward while the next row has the same one.
    Pixels in skip's color are left out."""
    out = {}
    open_runs = {}      # (x, width, color) -> its rectangle [x, y, w, h]
    for y in range(h):
        row = rows[y0 + y]
        runs, x = [], 0
        while x < w:
            c = row[x0 + x]
            end = x + 1
            while end < w and row[x0 + end] == c:
                end += 1
            if c != skip:
                runs.append((x, end - x, c))
            x = end
        still = {}
        for run in runs:
            rect = open_runs.get(run)
            if rect is not None:
                rect[3] += 1
            else:
                rect = [run[0], y, run[1], 1]
                out.setdefault(run[2], []).append(rect)
            still[run] = rect
        open_runs = still
    return out


def _hex(c):
    return "#%02x%02x%02x" % c


def _paths(rects, dx, dy):
    lines = []
    for color, rs in sorted(rects.items(), key=lambda kv: -len(kv[1])):
        d = "".join(f"M{x + dx} {y + dy}h{w}v{h}h-{w}z" for x, y, w, h in rs)
        lines.append(f'<path fill="{_hex(color)}" d="{d}"/>')
    return lines


def to_svg(ppm, pattern, title):
    """Both screens of a dump (made with key=1) as an SVG of a DSi: its two
    halves, the screens 1:1 in them, the top screen's diamonds as a pattern
    (pattern: the backdrop's, tile's and dot's colors as RRGGBB)."""
    w, h, rows = read_ppm(ppm)
    assert (w, h) == (256, 384)
    back, tile, dot = ("#" + c.lower() for c in pattern)
    # The diamonds: launcher/source/topscreen.c's make_pattern(), a 16x16 cell
    cell = [f'<rect width="16" height="16" fill="{back}"/>']
    for i in range(4):
        cell.append(f'<rect x="{8 - i}" y="{4 + i}" width="{2 * i + 1}" height="1" fill="{tile}"/>')
        cell.append(f'<rect x="{8 - i}" y="{11 - i}" width="{2 * i + 1}" height="1" fill="{tile}"/>')
    cell.append(f'<rect x="8" y="7" width="1" height="1" fill="{dot}"/>')

    # The console around the screens (the mockups' DSi)
    sx, top_y, bottom_y = 14, 12, 228
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 284 432" width="284" height="432" '
           f'shape-rendering="crispEdges" role="img" aria-label="{title}">',
           f'<title>{title}</title>',
           '<defs><pattern id="diamonds" width="16" height="16" patternUnits="userSpaceOnUse" '
           f'x="{sx}" y="{top_y}">' + "".join(cell) + '</pattern></defs>',
           '<rect x="1" y="1" width="282" height="214" rx="14" fill="#3d4b5f" stroke="#161b21" stroke-width="2"/>',
           '<rect x="18" y="214" width="248" height="4" fill="#252d39"/>',
           '<rect x="1" y="217" width="282" height="214" rx="14" fill="#333f50" stroke="#161b21" stroke-width="2"/>',
           f'<rect x="{sx - 2}" y="{top_y - 2}" width="260" height="196" rx="3" fill="#11151b"/>',
           f'<rect x="{sx - 2}" y="{bottom_y - 2}" width="260" height="196" rx="3" fill="#11151b"/>',
           f'<rect x="{sx}" y="{top_y}" width="256" height="192" fill="url(#diamonds)"/>']
    svg += _paths(rectangles(rows, 0, 0, 256, 192, skip=KEY), sx, top_y)
    # The bottom screen: its commonest color as one rectangle under the rest
    counts = {}
    for row in rows[192:]:
        for c in row:
            counts[c] = counts.get(c, 0) + 1
    common = max(counts, key=counts.get)
    svg.append(f'<rect x="{sx}" y="{bottom_y}" width="256" height="192" fill="{_hex(common)}"/>')
    svg += _paths(rectangles(rows, 0, 192, 256, 192, skip=common), sx, bottom_y)
    svg.append("</svg>")
    return "\n".join(svg) + "\n"
