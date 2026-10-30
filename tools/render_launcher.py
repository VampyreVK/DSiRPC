"""
render_launcher.py - the README's pictures of the launcher's modern look,
drawn by the launcher's own code on this PC (tests/c/ui's host, built with
gcc: Linux or WSL, like the tests) from a made-up SD card
(tests/helpers/launcher_ui.py), as pixel-art SVGs in docs/images/.

    python tools/render_launcher.py

Run it again when the screens change. Each picture is a DSi: the top
screen's diamonds as an SVG pattern, the rest as rectangles of one color.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from helpers import REPO, launcher_ui as lui  # noqa: E402

PICTURES = {
    "home": ("launcher-home.svg", "The launcher's main screen"),
    "games": ("launcher-games.svg", "The game list, with the picked game's details on the top screen"),
    "achievements": ("launcher-achievements.svg", "A game's achievements"),
    "saves": ("launcher-saves.svg", "The save sync, with the picked save's details on the top screen"),
}


def main():
    out_dir = os.path.join(REPO, "docs", "images")
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        host = lui.build(os.path.join(tmp, "ui_host"), sanitize=False)
        sd = os.path.join(tmp, "sd")
        lui.make_sd(sd)
        shots = os.path.join(tmp, "shots")
        os.makedirs(shots)
        rom = os.path.join(sd, "roms", "nds", "Pokemon Platinum.nds")
        out = lui.run(host, f"render {shots}|{sd}|{rom}|1")
        pattern = next(ln.split()[1:] for ln in out if ln.startswith("pattern "))
        for screen, (name, title) in PICTURES.items():
            svg = lui.to_svg(os.path.join(shots, screen + ".ppm"), pattern, title)
            with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)
            print(f"docs/images/{name}: {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
