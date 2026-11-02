"""tools/render_overlay.py, the overlay window's README pictures, which the
Renders workflow only draws when a release comes out (or it's run by hand):
the first picture's scene drawn the same way here, so a change to the
overlay or the demo that breaks them shows up with the other tests. Sprites
that aren't in the checkout (the Pokemon, in CI) are left out, without
downloading them."""

import os
import sys

import pytest

pygame = pytest.importorskip("pygame")
pytest.importorskip("PIL")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import render_overlay as ro  # noqa: E402


def test_every_picture_is_a_scene_of_the_demo():
    for name, scene, into, _ in ro.PICTURES:
        ro.scene_start(scene)       # (raises if the demo has no such scene)
        dur = next(d for s, d in ro.demo.SCENES if s == scene)   # its first time, as scene_start()
        assert 0 <= into < dur, f"{name}: {into} s into {scene!r}, which is {dur} s long"


def test_a_picture_draws(monkeypatch):
    no_download = lambda rel, dest, timeout=15.0: False  # noqa: E731
    monkeypatch.setattr("overlay.sprites._download", no_download)
    monkeypatch.setattr("overlay.unova_art._download", no_download)
    clock = ro.Clock()
    monkeypatch.setattr(ro.demo, "time", clock)
    name, scene, into, title = ro.PICTURES[0]
    pygame.init()
    try:
        pygame.display.set_mode((ro.W, ro.H))
        bank = ro.SpriteBank(os.path.join(ro.REPO, "Assets"))
        window = ro.render(bank, clock, scene, into)
        assert window.get_size() == (ro.W * ro.SCALE, ro.H * ro.SCALE)
        svg = ro.to_svg(window, title)
    finally:
        pygame.quit()
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert f"<title>{title}</title>" in svg
    assert svg.count("<path ") > 50       # a whole screen, not a blank one
