"""
render_igm.py - nds-bootstrap's in-game menu in DSiRPC's look, drawn by its
own code on this PC (tests/c/igm's host, built with gcc: Linux or WSL, like
the tests; tests/helpers/igm_ui.py) with a made-up game's achievements:

    python tools/render_igm.py                 igm-menu.gif and igm-achievements.gif

    igm-menu.gif          the menu opening, its achievements, then the options
    igm-achievements.gif  the menu opening on two new unlocks, then the whole
                          list, scrolled through

Everything goes to renders/ (--out DIR for another folder); --version TEXT
is the version the menu's footer shows (GIT_VER on a console; "dev" if not
given). Needs Pillow. The README shows the GIFs from the renders branch,
which .github/workflows/renders.yml updates when a release comes out.
"""

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import REPO, igm_ui as igm  # noqa: E402

BACKGROUND = (14, 20, 27)   # the launcher's darkest grey, around the screen (render_launcher.py's)
GAP = 8                     # DS pixels around the screen
SCALE = 2
EVERY = 3                   # a GIF frame every 3 of the DS's: 20 a second, 50 ms each


def tour():
    """igm-menu.gif: open, Achievements, a few down, back, Options, a few down, back"""
    steps = [(150, 0)]                                       # the fade in, then the main screen
    steps += igm.press(igm.DOWN, 24) + igm.press(igm.A, 70)  # Achievements
    for _ in range(3):
        steps += igm.press(igm.DOWN, 26)
    steps += igm.press(igm.B, 50)                            # back to the main screen
    for _ in range(4):
        steps += igm.press(igm.DOWN, 12)                     # down to Options
    steps += igm.press(igm.A, 70)
    for _ in range(3):
        steps += igm.press(igm.DOWN, 34)
    steps += igm.press(igm.B, 80)                            # the main screen again, then it closes
    return steps


def achievements():
    """igm-achievements.gif: the two new unlocks on the main screen, then the
    whole list, an entry at a time, a page back up, and out"""
    steps = [(180, 0)]
    steps += igm.press(igm.DOWN, 24) + igm.press(igm.A, 70)
    for _ in range(len(igm.CHEEVOS) - 1):
        steps += igm.press(igm.DOWN, 30)
    steps += igm.press(igm.L, 50) + igm.press(igm.L, 60)
    steps += igm.press(igm.B, 60)
    return steps


def framed(rgb):
    """A frame as the README shows it: the screen with a border, scaled up"""
    from PIL import Image
    shot = Image.frombytes("RGB", (igm.W, igm.H), rgb)
    out = Image.new("RGB", (igm.W + 2 * GAP, igm.H + 2 * GAP), BACKGROUND)
    out.paste(shot, (GAP, GAP))
    return out.resize((out.width * SCALE, out.height * SCALE), Image.NEAREST)


def save_gif(images, path, ms):
    """One palette for every frame (the menu has few colours), no dithering;
    a frame the same as the one before only makes that one last longer"""
    from PIL import Image
    kept, times = [], []
    for im in images:
        if kept and im.tobytes() == kept[-1].tobytes():
            times[-1] += ms
        else:
            kept.append(im)
            times.append(ms)
    sample = Image.new("RGB", (kept[0].width, kept[0].height * len(kept[::6])))
    for n, im in enumerate(kept[::6]):
        sample.paste(im, (0, n * im.height))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    gif = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in kept]
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=times, loop=0, optimize=True)
    print(f"{path}: {sum(times) / 1000:.1f} s, {os.path.getsize(path) // 1024} KB")


def render(host, steps, path, version):
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "frames.rgb")
        igm.run(host, igm.script(*steps) + [f"record {raw} {EVERY}"], version=version)
        save_gif([framed(f) for f in igm.frames(raw)], path, EVERY * 1000 // 60)


def main():
    ap = argparse.ArgumentParser(description="Draw nds-bootstrap's in-game menu (DSiRPC's look) for the README")
    ap.add_argument("--out", default=os.path.join(REPO, "renders"), help="the folder (default: renders/)")
    ap.add_argument("--version", default="dev", help="the version in the menu's footer (default: dev)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        host = igm.build(os.path.join(tmp, "igm_host"), sanitize=False)
        render(host, tour(), os.path.join(args.out, "igm-menu.gif"), args.version)
        render(host, achievements(), os.path.join(args.out, "igm-achievements.gif"), args.version)


if __name__ == "__main__":
    main()
