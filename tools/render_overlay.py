"""
render_overlay.py - DSiRPC's overlay window (the desktop app's stream
window), drawn by its own code (overlay/scenes.py) from the demo's made-up
scenes (core/demo.py), without opening a window (SDL's dummy driver):

    python tools/render_overlay.py            the README's pictures, as pixel-art SVGs
    python tools/render_overlay.py --png      and as PNGs

Everything goes to renders/ (--out DIR for another folder). It needs
pygame-ce and Pillow, and the sprites in Assets/ (a checkout has them; any
that aren't there come from GitHub Pages, as in the app, and it stops if one
can't be had). The
README shows the SVGs from the renders branch, which
.github/workflows/renders.yml updates when a release comes out, with the
launcher's.

Each picture plays its scene from the start on a made-up clock (the demo's
time and the window's), so the screen gets there the way it would in the
window (the wipes, the HP sliding, the achievement banner), and the same
picture comes out every time. Each picture is the window at scale 2
(512x384: the Unova party icons are drawn at the window's resolution), the
SVG as rectangles of one color.
"""

import argparse
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

import pygame  # noqa: E402

from core import demo  # noqa: E402
from core.hub import Snapshot, diff_events  # noqa: E402
from helpers import launcher_ui as lui  # noqa: E402
from overlay.scenes import Overlay, W, H  # noqa: E402
from overlay.sprites import SpriteBank  # noqa: E402

# (file, the demo's scene, seconds into it, what it shows)
PICTURES = [
    ("overlay-black.svg", "unova", 12.0,
     "The overlay with Pokemon Black: the trainer, the party, the badges and the latest achievement"),
    ("overlay-black-battle.svg", "unova_battle", 10.5,     # (not as a hit lands: the target blinks)
     "A battle in Pokemon Black, in the rain in Pinwheel Forest, in the game's own style: Dewott's Water Gun"),
    ("overlay-platinum-battle.svg", "rival", 9.0,
     "A battle in Pokemon Platinum: the rival at night, with animated sprites on the right terrain"),
    ("overlay-other.svg", "other", 8.0,
     "The overlay with any other game: what you're doing in it (its rich presence) and its achievements"),
]
FPS = 30
SCALE = 2           # the window's scale


class Clock:
    """The demo's time.time(), moved on a frame at a time"""

    def __init__(self):
        self.now = time.time()

    def time(self):
        return self.now


def scene_start(name):
    """Seconds into the demo's loop that scene `name` first starts"""
    t = 0.0
    for scene, dur in demo.SCENES:
        if scene == name:
            return t
        t += dur
    raise ValueError(f"the demo has no {name!r} scene")


def settle(overlay, bank, canvas, snap, t_ms):
    """Draws the frame again until every sprite it asks for has loaded
    (they load on the bank's own thread)"""
    for _ in range(400):
        overlay.draw(canvas, snap, t_ms, 0)
        if not bank._queued:
            overlay.draw(canvas, snap, t_ms, 0)     # the ones that just loaded
            if not bank._queued:
                return
        time.sleep(0.025)
    raise RuntimeError("the sprites didn't load")


def render(bank, clock, scene, into):
    """The window (at SCALE) `into` seconds into `scene`"""
    source = demo.DemoSource()
    source.t0 = clock.now - scene_start(scene)
    overlay = Overlay(bank)
    overlay.hires_ok = True
    canvas = pygame.Surface((W, H), 0, 32)
    prev, snap, t_ms = None, None, 0
    for i in range(int(into * FPS) + 1):
        data = source.read()
        overlay.handle_events(diff_events(prev, data) if prev is not None else [], t_ms)
        prev = data if data is not None else prev
        snap = Snapshot(data, data is not None, clock.now, source.status)
        t_ms = i * 1000 // FPS
        overlay.draw(canvas, snap, t_ms, 1000 // FPS)
        clock.now += 1 / FPS
    settle(overlay, bank, canvas, snap, t_ms)
    window = pygame.Surface((W * SCALE, H * SCALE), 0, 32)
    overlay.present(window, canvas)
    return window


def rows_of(surface):
    w, h = surface.get_size()
    data = pygame.image.tobytes(surface, "RGB")
    return [[tuple(data[(y * w + x) * 3:(y * w + x) * 3 + 3]) for x in range(w)] for y in range(h)]


def to_svg(window, title):
    """The window as an SVG: its commonest color as one rectangle under the
    rest, which are rectangles of one color"""
    rows = rows_of(window)
    w, h = window.get_size()
    counts = {}
    for row in rows:
        for c in row:
            counts[c] = counts.get(c, 0) + 1
    common = max(counts, key=counts.get)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
           f'shape-rendering="crispEdges" role="img" aria-label="{title}">',
           f'<title>{title}</title>',
           f'<rect width="{w}" height="{h}" fill="{lui._hex(common)}"/>']
    svg += lui._paths(lui.rectangles(rows, 0, 0, w, h, skip=common), 0, 0)
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Draw the overlay window's README pictures from the demo's scenes")
    ap.add_argument("--out", default=os.path.join(REPO, "renders"), help="the folder to write them to")
    ap.add_argument("--png", action="store_true", help="PNGs too")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    pygame.init()
    pygame.display.set_mode((W, H))    # sprites are converted for the screen's format
    clock = Clock()
    demo.time = clock                  # the demo reads the time through its module's `time`
    bank = SpriteBank(os.path.join(REPO, "Assets"))
    for name, scene, into, title in PICTURES:
        window = render(bank, clock, scene, into)
        svg = to_svg(window, title)
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"{os.path.join(args.out, name)}: {len(svg) // 1024} KB")
        if args.png:
            png = os.path.join(args.out, name[:-4] + ".png")
            pygame.image.save(window, png)
            print(png)
    pygame.quit()
    if bank._missing:
        sys.exit(f"Sprites that couldn't be loaded: {sorted(map(str, bank._missing))}")


if __name__ == "__main__":
    main()
