"""The README's banner and icons (docs/images), which tools/readme_art.py
draws from the launcher's own pixel art: they have to be what it draws from
the art as it is now, so a change to the DSi, the colors, the tiles' icons
or the font shows up here until they're drawn again."""

import os
import subprocess
import sys

from helpers import REPO

TOOL = os.path.join(REPO, "tools", "readme_art.py")
IMAGES = os.path.join(REPO, "docs", "images")


def files(root):
    return sorted(os.path.relpath(os.path.join(d, f), root) for d, _, names in os.walk(root) for f in names)


def test_the_readme_art_is_up_to_date(tmp_path):
    subprocess.run([sys.executable, TOOL, "--out", str(tmp_path)], check=True, capture_output=True)
    assert files(tmp_path) == files(IMAGES), "docs/images: python tools/readme_art.py"
    for name in files(tmp_path):
        path = os.path.join(IMAGES, name)
        with open(tmp_path / name, encoding="utf-8") as fresh, open(path, encoding="utf-8") as kept:
            assert fresh.read() == kept.read(), f"docs/images/{name} is out of date: python tools/readme_art.py"


def test_the_banner_moves_only_for_those_who_want_it():
    with open(os.path.join(IMAGES, "banner.svg"), encoding="utf-8") as f:
        svg = f.read()
    assert "@media (prefers-reduced-motion: reduce)" in svg
    # Still, it's connected: the chip that says so shows, the other doesn't
    assert '<g class="connecting" opacity="0">' in svg and '<g class="connected">' in svg
    # Nothing a README's picture can't have (GitHub serves it as an image)
    assert "<script" not in svg and "href=\"http" not in svg
