#!/usr/bin/env python3
"""
make_pixel_dsi.py - the pixel DSi from the overlay's waiting screen
(overlay/ui.py's dsi()) as animated GIFs, looking for a connection: the
Wi-Fi sign light grey, its arcs lighting up one by one.

  Assets/Consoles/Pixel.gif   Discord's "Pixel DSi" console picture: the
                              35x40 DSi at 9x, with the bottom screen's
                              lines as fine as the overlay draws them, in
                              the middle of a clear 512x512 square so it
                              sits inside Discord's round picture
  launcher/icon.gif           the launcher's icon (BlocksDS's ndstool makes
                              it the DSi's animated icon): the same DSi
                              redrawn 31x32 to fill the 32x32 icon, its
                              six lines as four (each brighter than the
                              one above, as the bottom screen has 9 rows)

Run it again after changing the DSi in overlay/ui.py:
  python tools/make_pixel_dsi.py
Needs pygame and Pillow.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from overlay import ui  # noqa: E402

FRAME_MS = 400                      # as the waiting screen's arcs
LIT = [4, 1, 2, 3]                  # parts lit a frame (the dot, then each arc); all of them first
WIFI_DIM = (46, 56, 70)             # an arc that isn't lit yet

DISCORD_SIZE, DISCORD_SCALE = 512, 9

# The DSi redrawn 31x32 for the launcher's icon: the same parts as
# overlay/ui.py's _DSI (same letters and colours), shorter screens and
# bodies, still mirrored left to right.
ICON = [
    "..ooooooooooooooooooooooooooo..",
    ".obbbbbbbbbbbbbbbbbbbbbbbbbbbo.",
    "obbbbbkkkkkkkkkkkkkkkkkkkbbbbbo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obebebkssssssssssssssssskbebebo",
    "obbebbkssssssssssssssssskbbebbo",
    "obebebkssssssssssssssssskbebebo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obbbbbkssssssssssssssssskbbbbbo",
    "obbbbbkkkkkkkkkkkkkkkkkkkbbbbbo",
    ".obbbbbbbbbbbbbbbbbbbbbbbbbbbo.",
    "..ooooooooooooooooooooooooooo..",
    "...oHHHHHHHHHHHHHHHHHHHHHHHo...",
    "..ooooooooooooooooooooooooooo..",
    ".odddddddddddddddddddddddddddo.",
    "oddddddkkkkkkkkkkkkkkkkkddddddo",
    "oddddddkssssssssssssssskddddddo",
    "odddpddkssssssssssssssskddpdddo",
    "oddpppdkssssssssssssssskdpdpddo",
    "odddpddkssssssssssssssskddpdddo",
    "oddddddkssssssssssssssskddddddo",
    "oddddddkssssssssssssssskddddddo",
    "oddddddkssssssssssssssskdpddddo",
    "oddddddkssssssssssssssskddddddo",
    "oddddpdkssssssssssssssskdpddddo",
    "oddddddkkkkkkkkkkkkkkkkkddddddo",
    ".odddddddddddddddddddddddddddo.",
    "..ooooooooooooooooooooooooooo..",
]
ICON_WIFI = (-2, -2)                # the Wi-Fi sign's offset from where ui.DSI_WIFI has it
# The bottom screen's lines: (row, how far from the screen's colour to the
# lines' colour), each 11 pixels wide from column 10.
ICON_LINES = [(21, 0.35), (23, 0.55), (25, 0.8), (27, 1.0)]
ICON_LINES_X = (10, 21)


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _ds(c):
    """The colour the DS shows for `c` (15-bit, each channel rounded), as
    ndstool turns it back into that (it drops each channel's low 3 bits)."""
    return tuple(round(v * 31 / 255) * 255 // 31 for v in c) + (255,)


def discord_frame(lit):
    """One frame of the Discord picture (RGBA, DISCORD_SIZE square)."""
    s = DISCORD_SCALE
    icon = pygame.Surface((ui.DSI_W, ui.DSI_H), pygame.SRCALPHA)
    ui.dsi(icon, 0, 0)
    ui.dsi_wifi(icon, 0, 0, lit=lit, off=WIFI_DIM)
    big = pygame.transform.scale(icon, (ui.DSI_W * s, ui.DSI_H * s))
    bx, by, _, _ = ui.DSI_BOTTOM_SCREEN
    big.blit(ui.dsi_lines(s), (bx * s, by * s))
    out = pygame.Surface((DISCORD_SIZE, DISCORD_SIZE), pygame.SRCALPHA)
    out.blit(big, ((DISCORD_SIZE - big.get_width()) // 2, (DISCORD_SIZE - big.get_height()) // 2))
    return Image.frombytes('RGBA', out.get_size(), pygame.image.tobytes(out, 'RGBA'))


def icon_frame(lit):
    """One frame of the launcher's icon (RGBA, 32x32), in the DS's colours."""
    pal = ui._DSI_PALETTE
    im = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    for y, row in enumerate(ICON):
        for x, ch in enumerate(row):
            if ch in pal:
                im.putpixel((x, y), _ds(pal[ch]))
    for i, part in enumerate(ui.DSI_WIFI):
        c = ui.DSI_WIFI_OFF if i < lit else WIFI_DIM
        for x, y in part:
            im.putpixel((x + ICON_WIFI[0], y + ICON_WIFI[1]), _ds(c))
    for y, t in ICON_LINES:
        for x in range(*ICON_LINES_X):
            im.putpixel((x, y), _ds(_mix(pal['s'], ui.DSI_LINES_COLOR, t)))
    return im


def save_gif(frames, path):
    """Frames (RGBA) as a looping GIF with one palette, index 0 clear. The
    clear pixels are the same in every frame and only opaque ones change,
    so each frame is drawn over the last (disposal 1)."""
    colours = []
    for f in frames:
        for _, c in f.getcolors(1 << 20):
            if c[3] and c[:3] not in colours:
                colours.append(c[:3])
    assert len(colours) <= 255, f"{len(colours)} colours"
    index = {c: i + 1 for i, c in enumerate(colours)}
    palette = [0, 0, 0] + [v for c in colours for v in c]
    out = []
    for f in frames:
        p = Image.new('P', f.size, 0)
        p.putpalette(palette)
        rgba = f.tobytes()
        p.frombytes(bytes(index[tuple(rgba[i:i + 3])] if rgba[i + 3] else 0 for i in range(0, len(rgba), 4)))
        out.append(p)
    out[0].save(path, save_all=True, append_images=out[1:], duration=FRAME_MS, loop=0,
                transparency=0, disposal=1, optimize=False)
    return len(colours)


def main():
    pygame.init()
    jobs = [(os.path.join(ROOT, "Assets", "Consoles", "Pixel.gif"), discord_frame),
            (os.path.join(ROOT, "launcher", "icon.gif"), icon_frame)]
    for path, frame in jobs:
        n = save_gif([frame(lit) for lit in LIT], path)
        print(f"{os.path.relpath(path, ROOT)}: {len(LIT)} frames, {n} colours")


if __name__ == "__main__":
    main()
