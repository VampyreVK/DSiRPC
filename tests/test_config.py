"""dsirpc.cfg (utils/config.py): its one Discord application (a release's
default, your own, saved, and only that, and files from when Platinum and
the other games each had one, which still load), and the overlay window's
ambient music."""

import pytest

from utils import config

ONE, TWO, THREE, FOUR, FIVE = ("1" * 18, "2" * 18, "3" * 18, "4" * 18, "5" * 18)


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", str(tmp_path))   # where defaults.cfg is looked for
    return tmp_path


def test_one_application(folder):
    (folder / "defaults.cfg").write_text(f"[connection]\ndiscord_client_id: {ONE}\n")
    path = folder / "dsirpc.cfg"
    cfg = config.Config(str(path))
    assert cfg.discord_client_id == ONE and cfg.has_discord_id   # the release's, while yours is empty
    cfg.save()
    assert "discord_client_id: \n" in path.read_text().replace("\r\n", "\n")   # left to defaults.cfg

    cfg.discord_client_id = TWO
    cfg.save()
    text = path.read_text()
    assert f"discord_client_id: {TWO}" in text and "[discord_apps]" not in text
    assert config.Config(str(path)).discord_client_id == TWO


def test_files_from_when_other_games_had_their_own(folder):
    path = folder / "dsirpc.cfg"
    path.write_text(f"[connection]\ndiscord_client_id: {ONE}\n\n[discord_apps]\ndefault: {TWO}\nAMCE: {THREE}\n")
    assert config.Config(str(path)).discord_client_id == ONE      # Platinum's is the one
    path.write_text(f"[connection]\ndiscord_client_id:\n\n[discord_apps]\ndefault: {TWO}\n")
    assert config.Config(str(path)).discord_client_id == TWO      # else the other games'

    # An older release's defaults.cfg with only the other games' application
    (folder / "defaults.cfg").write_text(f"[connection]\ndiscord_client_id:\n\n[discord_apps]\ndefault: {FOUR}\n")
    path.write_text("[connection]\ndiscord_client_id:\n")
    cfg = config.Config(str(path))
    assert cfg.discord_client_id == cfg.release_client_id == FOUR
    path.write_text(f"[connection]\ndiscord_client_id: {FIVE}\n")
    assert config.Config(str(path)).discord_client_id == FIVE     # yours over the release's


def test_ambient_music(folder):
    path = folder / "dsirpc.cfg"
    cfg = config.Config(str(path))
    assert cfg.ambient_music == "off"           # off at first: the window may be on a stream
    cfg.ambient_music = "subtle"
    cfg.save()
    assert "ambient_music: subtle" in path.read_text()
    assert config.Config(str(path)).ambient_music == "subtle"
    path.write_text("[app]\nambient_music: Bright\n")
    assert config.Config(str(path)).ambient_music == "bright"
    path.write_text("[app]\nambient_music: loud\n")
    assert config.Config(str(path)).ambient_music == "off"
