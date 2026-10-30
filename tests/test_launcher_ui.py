"""The launcher's modern look (launcher/source/ui.c, topscreen.c and
picker.c, and the screens in main.c, saveui.c, settings.c and update.c),
drawn by its own code on the PC (tests/c/ui/ui_host.c, on a stand-in for
libnds) with the sanitizers on: every screen draws, inside its bounds; the
game list takes the games' names from their banners and keeps them in
games.idx; its orders and favorites; the achievement counts, with the unlocks
waiting for DSiRPC; and its text."""

import os

import pytest

from helpers import launcher_ui as lui

SCREENS = ["connecting", "syncing", "ready", "no_wifi", "home", "home_settings", "home_offline", "starting", "update",
           "update_progress", "update_done", "settings", "settings_address", "settings_music", "games",
           "achievements", "saves", "saves_conflict", "saves_versions", "saves_progress", "saves_done"]

# Palette colors as the DS shows them (5 bits a channel)
GREEN, AMBER, RED, CYAN = (88, 208, 128), (240, 192, 48), (232, 72, 56), (72, 200, 232)
PLATINUM_GOLD = (240, 200, 56)      # in Platinum's banner icon


@pytest.fixture(scope="module")
def host(cc, tmp_path_factory):
    return lui.build(str(tmp_path_factory.mktemp("ui") / "ui_host"))


@pytest.fixture
def sd(tmp_path):
    root = str(tmp_path / "sd")
    lui.make_sd(root)
    return root


def game_path(sd, name):
    return os.path.join(sd, "roms", "nds", name)


def games(host, sd, sort=1):
    """The game list, in this order (0 recent, 1 A-Z, 2 favorites first):
    [code, name, publisher, version, favorite, last played, earned/total]"""
    out = lui.run(host, f"games {sd}|{sort}")
    assert out[-1] == f"games {sum(ln.startswith('game ') for ln in out)}"
    return [ln[5:].split("|") for ln in out if ln.startswith("game ")]


def colors(path):
    """The colors on each screen of a dump: (top, bottom)"""
    with open(path, "rb") as f:
        data = f.read().split(maxsplit=4)[4]
    half = 256 * 192 * 3
    return ({data[i:i + 3] for i in range(0, half, 3)}, {data[i:i + 3] for i in range(half, 2 * half, 3)})


# -- the screens ---------------------------------------------------------------------

def test_every_screen_draws(host, sd, tmp_path):
    shots = tmp_path / "shots"
    shots.mkdir()
    out = lui.run(host, f"render {shots}|{sd}|{game_path(sd, 'Pokemon Platinum.nds')}|0")
    assert out[0] == f"render {len(SCREENS)}"
    drawn = {}
    for name in SCREENS:
        top, bottom = drawn[name] = colors(shots / f"{name}.ppm")
        assert len(top) > 4 and len(bottom) > 4, name      # drawn, not a blank screen
    # Some of what's on them: the picked tile and the Saves badge, the red
    # card when there's no Wi-Fi, the game's icon at twice its size on top,
    # the update's card
    assert bytes(GREEN) in drawn["home"][1] and bytes(AMBER) in drawn["home"][1]
    assert bytes(RED) in drawn["no_wifi"][1]
    assert bytes(PLATINUM_GOLD) in drawn["games"][0] and bytes(PLATINUM_GOLD) in drawn["games"][1]
    assert bytes(CYAN) in drawn["update"][1]


def test_the_key_color_marks_the_top_screens_clear_pixels(host, sd, tmp_path):
    shots = tmp_path / "shots"
    shots.mkdir()
    out = lui.run(host, f"render {shots}|{sd}|{game_path(sd, 'Pokemon Platinum.nds')}|1")
    assert out[1].startswith("pattern ") and len(out[1].split()) == 4
    top, bottom = colors(shots / "home.ppm")
    assert bytes(lui.KEY) in top and bytes(lui.KEY) not in bottom


# -- the game list ---------------------------------------------------------------------

def test_names_come_from_the_banners(host, sd):
    lui.write(game_path(sd, "No Banner.nds"), lui.rom("NBNE", "", banner=False))
    lui.write(game_path(sd, "readme.txt"), b"not a game")
    lui.write(game_path(sd, "._Tetris DS.nds"), b"macOS's")          # hidden
    lui.write(os.path.join(sd, "roms", "nds", "saves", "Old.nds"), lui.rom("OLDE", "Old\nX"))   # not a game folder
    lui.write(os.path.join(sd, "roms", "nds", "RPG", "Layton 2.nds"), lui.rom("YLTE", "Layton 2\nLevel-5"))
    rows = games(host, sd)
    by_code = {r[0]: r for r in rows}
    assert by_code["CPUE"][1:4] == ["Pokemon Platinum Version", "Nintendo", "1"]   # é as e, Rev 1
    assert by_code["ADME"][1:3] == ["Animal Crossing Wild World", "Nintendo"]      # the name's lines joined
    assert by_code["NBNE"][1:3] == ["No Banner", ""]                               # no banner: the file's name
    assert by_code["YLTE"][1] == "Layton 2"                                        # in a folder
    assert "OLDE" not in by_code and len(rows) == len(lui.GAMES) + 2
    assert [r[1].lower() for r in rows] == sorted(r[1].lower() for r in rows)      # A-Z


def test_games_idx_keeps_what_was_read(host, sd):
    games(host, sd)
    with open(os.path.join(sd, "DSiRPC", "games.idx"), encoding="ascii") as f:
        lines = f.read().splitlines()
    assert lines[0] == "DSiRPC games 1" and len(lines) == len(lui.GAMES) + 1
    assert any(ln.endswith("Tetris DS.nds\tTetris DS\tNintendo") for ln in lines)

    # A banner changed behind games.idx's back (same size and time): the
    # index's name stays; once the file's time changes, it's read again
    path = game_path(sd, "Tetris DS.nds")
    st = os.stat(path)
    lui.write(path, lui.rom("ATRE", "Tetris Party\nNintendo", "blocks"))
    os.utime(path, (st.st_atime, st.st_mtime))
    assert {r[0]: r[1] for r in games(host, sd)}["ATRE"] == "Tetris DS"
    os.utime(path, (st.st_atime, st.st_mtime + 10))
    assert {r[0]: r[1] for r in games(host, sd)}["ATRE"] == "Tetris Party"


def test_the_orders(host, sd):
    # Recent: Platinum played two days ago and Black 40 (the PC's playtimes),
    # then the rest A-Z
    rows = games(host, sd, sort=0)
    assert [r[0] for r in rows[:3]] == ["CPUE", "IRBO", "ADME"]
    assert int(rows[0][5]) > int(rows[1][5]) > 0 == int(rows[2][5])

    # A game started from the launcher comes first
    lui.run(host, f"started {sd}|{game_path(sd, 'Tetris DS.nds')}")
    assert games(host, sd, sort=0)[0][0] == "ATRE"

    # Favorites first, and kept
    lui.run(host, f"favorite {sd}|{game_path(sd, 'Zelda PH.nds')}")
    rows = games(host, sd, sort=2)
    assert rows[0][0] == "AZEE" and rows[0][4] == "1" and rows[1][4] == "0"
    assert {r[0]: r[4] for r in games(host, sd, sort=1)}["AZEE"] == "1"


def test_a_game_started_before_the_list_was_ever_opened(host, sd):
    """START on the main screen, with no games.idx yet: a bare entry, its
    name read when the list opens."""
    lui.run(host, f"started {sd}|{game_path(sd, 'Mario Kart DS.nds')}")
    rows = games(host, sd, sort=0)
    assert rows[0][:3] == ["AMCE", "Mario Kart DS", "Nintendo"]


def test_achievement_counts(host, sd):
    by_code = {r[0]: r[6] for r in games(host, sd)}
    assert by_code["CPUE"] == "3/6"      # two earned, and one waiting in RPCUNLK.BIN
    assert by_code["IRBO"] == "0/0"      # no set
    os.remove(os.path.join(sd, "RPCUNLK.BIN"))
    assert {r[0]: r[6] for r in games(host, sd)}["CPUE"] == "2/6"


# -- text --------------------------------------------------------------------------------

def test_text(host):
    long = "The one you don't pick stays in the PC's backups, so nothing is ever lost"
    out = lui.run(host, "text Pokémon|Pokemon", "text \x1b[31;1mRed\x1b[39;0m|Red", f"text {long}|x",
                  "text |x")
    pokemon, red, wrapped, empty = (ln[5:].split("|") for ln in out)
    assert pokemon[0] == pokemon[1] != "0"      # é drawn as e
    assert red[0] == red[1]                     # the console's color codes skipped
    assert int(wrapped[2]) >= 4                 # wrapped at 100 pixels
    assert empty[0] == "0" and empty[2] == "0"


# -- music -------------------------------------------------------------------------------

def test_the_music_setting(host):
    """Music (music.c): settings_apply() starts the song the settings pick,
    in the modern look only, and switching stops the one before; maxmod's
    calls, as the host notes them."""
    fade = ",".join(f"volume {640 * f // 12}" for f in range(11, 0, -1))
    out = lui.run(host,
                  "music 0|1|0",        # Bright, as the launcher started (the default)
                  "music 0|2|0",        # Subtle
                  "music 0|2|0",        # the same: carries on
                  "music 0|0|0",        # Off
                  "music 0|1|1",        # Bright, then a game starts: faded out
                  "music 1|2|0",        # the classic look: none
                  "music 0|2|0")
    assert out == ["music ",
                   "music stop,unload 0,load 1,volume 640,loop 1",
                   "music ",
                   "music stop,unload 1",
                   f"music load 0,volume 640,loop 0,{fade},stop,unload 0",
                   "music ",
                   "music load 1,volume 640,loop 1"]
