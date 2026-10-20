"""The launcher's handling of nds-bootstrap's settings
(launcher/source/bootstrap_ini.c, plain C built for the PC and called with
ctypes): which game nds-bootstrap boots and with which save, keeping the rest
of TWiLight Menu++'s ini as it is, and DS mode for DSi-enhanced games, since
DSiRPC's part of nds-bootstrap only runs in DS mode (a 3DS whose TWiLight
left DSI_MODE on ran Pokemon Black with none of DSiRPC: no connection, no
achievements in the in-game menu).

The C code uses the SD card's paths ("sd:/_nds/..."), which on the PC are
relative: each test runs in its own folder with an "sd:" folder in it."""

import ctypes
import os

import pytest

from helpers import REPO, cbuild

LAUNCHER = os.path.join(REPO, "launcher", "source")
INI = "sd:/_nds/nds-bootstrap.ini"

TWILIGHT_INI = (
    "; TWiLight Menu++ writes this file\r\n"
    "[NDS-BOOTSTRAP]\r\n"
    "DEBUG = 0\r\n"
    "NDS_PATH = sd:/roms/nds/Other Game.nds\r\n"
    "SAV_PATH = sd:/roms/nds/saves/Other Game.sav\r\n"
    "HOMEBREW_ARG = \r\n"
    "MANUAL_PATH = sd:/manuals/Other Game.txt\r\n"
    "LANGUAGE = -1\r\n"
    "DSI_MODE = 1\r\n"
    "BOOST_CPU = 1\r\n"
    "DONOR_SDK_VER = 5\r\n"
    "PATCH_MPU_REGION = 1\r\n"
    "PATCH_MPU_SIZE = 4\r\n"
)


@pytest.fixture(scope="module")
def lib(cc, tmp_path_factory):
    path = str(tmp_path_factory.mktemp("launcher") / "libbootstrap_ini.so")
    cbuild.build(path, [os.path.join(LAUNCHER, "bootstrap_ini.c")], flags=["-std=gnu11", "-I", LAUNCHER],
                 shared=True, sanitize=cbuild.shared_sanitizers())
    lib = ctypes.CDLL(path)
    lib.ini_get.argtypes = [ctypes.c_char_p] * 3 + [ctypes.c_char_p, ctypes.c_size_t]
    lib.ini_set.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p),
                            ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
    lib.find_save.argtypes = [ctypes.c_char_p] * 3 + [ctypes.c_char_p, ctypes.c_size_t]
    lib.find_save.restype = ctypes.c_bool
    lib.nds_unit_code.argtypes = [ctypes.c_char_p]
    lib.bootstrap_ini_prepare.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    return lib


@pytest.fixture
def sd(tmp_path, monkeypatch):
    """An SD card in a folder of its own, the test's working folder."""
    monkeypatch.chdir(tmp_path)

    def put(path, data=b""):
        p = tmp_path / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data.encode() if isinstance(data, str) else data)
        return path
    put.root = tmp_path
    return put


def nds(unit_code):
    """A game file's first bytes: a header with this unit code."""
    header = bytearray(0x200)
    header[0:12] = b"POKEMON B\0\0\0"
    header[0x0C:0x10] = b"IRBO"
    header[0x12] = unit_code
    return bytes(header)


def prepare(lib, game):
    msg = ctypes.create_string_buffer(256)
    r = lib.bootstrap_ini_prepare(game.encode(), msg, len(msg))
    return r, msg.value.decode()


def get(lib, key, path=INI, section="NDS-BOOTSTRAP"):
    out = ctypes.create_string_buffer(512)
    r = lib.ini_get(path.encode(), section.encode(), key.encode(), out, len(out))
    return out.value.decode() if r == 1 else (None if r == 0 else "unreadable")


def test_unit_code(lib, sd):
    for code in (0, 2, 3):
        sd(f"sd:/g{code}.nds", nds(code))
        assert lib.nds_unit_code(f"sd:/g{code}.nds".encode()) == code
    sd("sd:/short.nds", b"\0" * 5)
    assert lib.nds_unit_code(b"sd:/short.nds") == -1
    assert lib.nds_unit_code(b"sd:/missing.nds") == -1


def test_a_dsi_enhanced_game_runs_in_ds_mode(lib, sd):
    sd(INI, TWILIGHT_INI)
    game = sd("sd:/roms/nds/Pokemon Black.nds", nds(2))
    save = sd("sd:/roms/nds/saves/Pokemon Black.sav", b"save")
    sd("sd:/_nds/nds-bootstrap/cheatData.bin", b"cheats")
    sd("sd:/_nds/nds-bootstrap/wideCheatData.bin", b"wide")
    assert prepare(lib, game) == (0, "")
    assert (get(lib, "NDS_PATH"), get(lib, "SAV_PATH"), get(lib, "DSI_MODE")) == (game, save, "0")
    # The last game's own values reset, TWiLight's settings kept, as written
    assert (get(lib, "MANUAL_PATH"), get(lib, "DONOR_SDK_VER"), get(lib, "PATCH_MPU_REGION")) == ("", "0", "0")
    text = (sd.root / INI).read_bytes()
    assert b"BOOST_CPU = 1\r\n" in text and b"LANGUAGE = -1\r\n" in text and b"DEBUG = 0\r\n" in text
    assert text.startswith(b"; TWiLight Menu++ writes this file\r\n") and b"\n" not in text.replace(b"\r\n", b"")
    assert text.count(b"DSI_MODE") == 1
    # The last game's cheats are gone
    assert not (sd.root / "sd:/_nds/nds-bootstrap/cheatData.bin").exists()
    assert not (sd.root / "sd:/_nds/nds-bootstrap/wideCheatData.bin").exists()


def test_the_same_game_switched_back_to_dsi_mode(lib, sd):
    """TWiLight launched it in DSi mode since: only DSI_MODE changes."""
    game = sd("sd:/roms/nds/Pokemon Black.nds", nds(2))
    sd("sd:/roms/nds/saves/Pokemon Black.sav", b"save")
    sd(INI, TWILIGHT_INI.replace("Other Game.nds", "Pokemon Black.nds"))
    sd("sd:/_nds/nds-bootstrap/cheatData.bin", b"cheats")
    before = (sd.root / INI).read_bytes()
    assert prepare(lib, game) == (0, "")
    after = (sd.root / INI).read_bytes()
    assert after == before.replace(b"DSI_MODE = 1", b"DSI_MODE = 0")
    assert (sd.root / "sd:/_nds/nds-bootstrap/cheatData.bin").exists()   # TWiLight's, for this game
    # Already in DS mode: the file isn't touched at all
    os.utime(sd.root / INI, (1000, 1000))
    assert prepare(lib, game) == (0, "")
    assert (sd.root / INI).read_bytes() == after and os.stat(sd.root / INI).st_mtime == 1000


def test_no_dsi_mode_key_means_dsi_mode(lib, sd):
    """nds-bootstrap's own default is DSi mode, so a missing key is added, for
    a new game and for the one already set up."""
    no_key = TWILIGHT_INI.replace("DSI_MODE = 1\r\n", "")
    game = sd("sd:/Pokemon White.nds", nds(2))
    sd("sd:/Pokemon White.sav", b"save")
    sd(INI, no_key)
    assert prepare(lib, game) == (0, "")
    assert get(lib, "DSI_MODE") == "0" and get(lib, "SAV_PATH") == "sd:/Pokemon White.sav"
    sd(INI, no_key.replace("sd:/roms/nds/Other Game.nds", game))
    assert prepare(lib, game) == (0, "")
    assert get(lib, "DSI_MODE") == "0"


@pytest.mark.parametrize("unit_code", [0, 3])
def test_ds_and_dsi_exclusive_games_keep_the_setting(lib, sd, unit_code):
    sd(INI, TWILIGHT_INI)
    game = sd("sd:/roms/nds/Game.nds", nds(unit_code))
    sd("sd:/roms/nds/saves/Game.sav", b"save")
    assert prepare(lib, game) == (0, "")
    assert get(lib, "NDS_PATH") == game and get(lib, "DSI_MODE") == "1"


def test_no_ini_or_no_save(lib, sd):
    game = sd("sd:/roms/nds/Pokemon Black.nds", nds(2))
    r, msg = prepare(lib, game)
    assert r == -1 and msg.startswith("Can't read sd:/_nds/nds-bootstrap.ini")
    sd(INI, TWILIGHT_INI)
    r, msg = prepare(lib, game)
    assert r == -1 and "no save file" in msg
    assert get(lib, "NDS_PATH") == "sd:/roms/nds/Other Game.nds"   # left alone


def test_where_saves_are_found(lib, sd):
    def find(game, prev_nds="", prev_sav=""):
        out = ctypes.create_string_buffer(512)
        ok = lib.find_save(game.encode(), prev_nds.encode(), prev_sav.encode(), out, len(out))
        return out.value.decode() if ok else None

    game = sd("sd:/roms/nds/Black.nds", nds(2))
    assert find(game) is None
    sd("sd:/_nds/TWiLightMenu/saves/Black.sav", b"s")
    assert find(game) == "sd:/_nds/TWiLightMenu/saves/Black.sav"
    sd("sd:/roms/nds/Black.sav", b"s")
    assert find(game) == "sd:/roms/nds/Black.sav"
    sd("sd:/roms/nds/saves/Black.sav", b"s")
    assert find(game) == "sd:/roms/nds/saves/Black.sav"
    # TWiLight's per-game save slot (save 2 is .sav2; the games folder's is
    # always .sav)
    game = sd("sd:/roms/nds/White.nds", nds(2))
    sd("sd:/_nds/TWiLightMenu/gamesettings/White.nds.ini", "[GAMESETTINGS]\nSAVE_NUMBER = 2\n")
    sd("sd:/roms/nds/saves/White.sav", b"s")
    assert find(game) is None
    sd("sd:/roms/nds/saves/White.sav2", b"s")
    assert find(game) == "sd:/roms/nds/saves/White.sav2"
    # The last game's save was in a "saves" folder: this one's is looked for there first
    sd("sd:/roms/nds/White.sav", b"s")
    assert find(game, "sd:/roms/gba/x.nds", "sd:/roms/gba/saves/x.sav") == "sd:/roms/nds/saves/White.sav2"
    assert find(game, "sd:/roms/nds/x.nds", "sd:/roms/nds/x.sav") == "sd:/roms/nds/White.sav"


def test_ini_set_keeps_the_file(lib, sd):
    sd("sd:/a.ini", "; notes\n[OTHER]\nNDS_PATH = keep\n[NDS-BOOTSTRAP]\nA = 1\nB = 2")
    keys = (ctypes.c_char_p * 2)(b"B", b"C")
    values = (ctypes.c_char_p * 2)(b"20", b"30")
    assert lib.ini_set(b"sd:/a.ini", b"NDS-BOOTSTRAP", keys, values, 2) == 0
    assert (sd.root / "sd:/a.ini").read_text() == \
        "; notes\n[OTHER]\nNDS_PATH = keep\n[NDS-BOOTSTRAP]\nA = 1\nB = 20\nC = 30\n"
    assert get(lib, "NDS_PATH", "sd:/a.ini", "OTHER") == "keep"
    # A section that isn't there yet is added at the end
    assert lib.ini_set(b"sd:/a.ini", b"NEW", keys, values, 1) == 0
    assert (sd.root / "sd:/a.ini").read_text().endswith("C = 30\n[NEW]\nB = 20\n")
    assert lib.ini_set(b"sd:/missing.ini", b"NEW", keys, values, 1) == -1
