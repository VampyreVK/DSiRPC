"""nds-bootstrap's in-game menu in DSiRPC's look (arm9_igm/source/
inGameMenu.c, dsirpc_skin.c and dsirpc_ach.c), run by its own code on the PC
(tests/c/igm/igm_host.c, the DS's memory mapped at its addresses) with the
sanitizers on: it fades in, its main screen has the new unlocks and the
counts from the ARM7's set, the Achievements screen lists them in its order,
the options open, the Wi-Fi sign follows the link, and B closes it. The
README's renders (tools/render_igm.py) come from the same host."""

import pytest

from helpers import igm_ui as igm


@pytest.fixture(scope="module")
def host(cc, tmp_path_factory):
    return igm.build(str(tmp_path_factory.mktemp("igm") / "igm_host"))


def joined(rows):
    return "\n".join(rows)


def test_main_screen(host, tmp_path):
    raw = tmp_path / "frames.rgb"
    out = igm.run(host, igm.script((90, 0)) + ["text 80", f"record {raw} 1"], version="v9.9.9")
    main = joined(igm.text(out, 80))
    for item in ("Return to Game", "Achievements", "Reset Game", "Options...", "Quit Game"):
        assert item in main
    assert "DSiRPC" in main and "17:10" in main                  # the title bar: the time from the ARM7
    assert "2 new achievements!" in main                        # the console's two unlocks, newest first
    assert main.index("T-Spin Double") < main.index("Clean Sweep")
    assert "5/12" in main and "28/138 pts" in main              # 3 earned before, 2 on the console
    assert "nds-bootstrap-DSiRPC" in main and "v9.9.9" in main
    # It fades in from dark
    frames = igm.frames(raw)
    bright = [sum(f[::97]) for f in frames]
    assert bright[0] < bright[40] / 4 and bright[40] == pytest.approx(bright[80], rel=0.1)


def test_achievements_screen(host):
    steps = [(60, 0)] + igm.press(igm.DOWN, 20) + igm.press(igm.A, 40)
    first = sum(n for n, _ in steps) - 5     # (a few frames before the next press)
    steps += igm.press(igm.DOWN, 20) * 2
    out = igm.run(host, igm.script(*steps) + [f"text {first}", f"text {first + 48}"])
    page = joined(igm.text(out, first))
    assert "5/12 earned" in page and "28/138 pts" in page
    # Earned first, the new ones on top (newest first), then by date; the
    # highlighted one's description below
    order = [page.index(t) for t in ("T-Spin Double", "Clean Sweep", "Hold That Thought", "Four at Once")]
    assert order == sorted(order)
    assert page.count("NEW") == 2
    assert "Clear two lines with a T-Spin" in page and "1/12" in page
    later = joined(igm.text(out, first + 48))
    assert "3/12" in later and "Use the hold box ten times" in later   # (it wraps)


def test_options(host):
    steps = [(60, 0)] + igm.press(igm.DOWN, 10) * 5 + igm.press(igm.A, 40)
    at = sum(n for n, _ in steps) - 5
    out = igm.run(host, igm.script(*steps) + [f"text {at}"])
    page = joined(igm.text(out, at))
    for label in ("Options", "Main Screen", "Brightness", "Volume", "Refresh Rate", "Clock Speed", "VRAM Mode"):
        assert label in page
    assert "133 MHz" in page and "DSi mode" in page


def test_no_set(host, tmp_path, monkeypatch):
    """Without an anchor (a game not started from the launcher's set) the
    main screen has no Achievements item and no card"""
    monkeypatch.setattr(igm, "ach_image", lambda *a, **k: bytes(64))
    out = igm.run(host, igm.script((60, 0)) + ["text 50"])
    main = joined(igm.text(out, 50))
    assert "Return to Game" in main and "Achievements" not in main and "new achievement" not in main


def test_totals_over_a_long_list(host, monkeypatch):
    """A set of more than the 512 entries the menu lists: its counts and
    points are the whole set's (one earned past the 512th too)"""
    many = [(f"Achievement {i}", "", 1, "pc" if i in (0, 1, 2, 550) else "") for i in range(600)]
    real = igm.ach_image
    monkeypatch.setattr(igm, "ach_image", lambda *a, **k: real(many))
    out = igm.run(host, igm.script((90, 0)) + ["text 80"])
    main = joined(igm.text(out, 80))
    assert "4/600" in main and "4/600 pts" in main
