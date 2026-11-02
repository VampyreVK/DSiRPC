"""The overlay window's ambient music (overlay/music.py, the tray's "Ambient
music"): the launcher's own XM modules played by pygame's mixer (here with
SDL's dummy audio driver), following the tray's choice between frames: a
fade from one song to the next, a pause while the window's minimized, a
short fade as it closes, and a song that won't play left alone."""

import os
import time

import pytest

from conftest import need
from helpers import REPO
from utils import config

os.environ["SDL_AUDIODRIVER"] = "dummy"


@pytest.fixture
def music():
    try:
        import pygame
    except ImportError:
        need(False, "pygame isn't installed (tests/requirements.txt has it)")
    from overlay import music as m
    pygame.mixer.init()
    yield m
    pygame.mixer.quit()


def follow(player, until, seconds=3):
    """Ticks the player as the window would until until() holds."""
    end = time.monotonic() + seconds
    while not until():
        assert time.monotonic() < end, f"stuck: now {player.now}, want {player.want}"
        player.tick()
        time.sleep(0.01)


def test_the_songs_are_the_launchers(music):
    assert music.CHOICES == config.MUSIC_CHOICES == ("off", "bright", "subtle")
    for name in music.CHOICES[1:]:
        assert os.path.samefile(music.song_path(name), os.path.join(REPO, "launcher", "audio", name + ".xm"))
    assert music.choice("Subtle ") == "subtle" and music.choice("loud") == "off" and music.choice(None) == "off"


def test_playing_switching_and_stopping(music):
    import pygame
    player = music.Music("off")
    player.tick()
    assert player.now == "off" and not pygame.mixer.music.get_busy()

    player.want = "bright"
    player.tick()
    assert player.now == "bright" and pygame.mixer.music.get_busy()
    assert pygame.mixer.music.get_volume() == pytest.approx(music.VOLUME, abs=0.01)

    # Another song: Bright fades out first, then Subtle starts
    player.want = "subtle"
    player.tick()
    assert player.fading and player.now == "bright"
    follow(player, lambda: player.now == "subtle")
    assert pygame.mixer.music.get_busy()

    player.want = "off"
    follow(player, lambda: player.now == "off")
    assert not pygame.mixer.music.get_busy()


def test_minimized_and_closed(music):
    import pygame
    player = music.Music("bright")
    player.tick()
    player.pause(True)
    assert not pygame.mixer.music.get_busy()        # paused
    # A new song while minimized starts paused too
    player.want = "subtle"
    follow(player, lambda: player.now == "subtle")
    assert not pygame.mixer.music.get_busy()
    player.pause(False)
    assert pygame.mixer.music.get_busy()

    start = time.monotonic()
    player.close()
    assert time.monotonic() - start >= music.FADE_MS / 2000 * 0.9    # it waited for its fade
    assert player.now == "off"


def test_a_song_that_wont_play(music, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(music, "FOLDER", str(tmp_path))     # no songs there
    player = music.Music("bright")
    player.tick()
    player.tick()
    assert player.now == "off" and player.failed == "bright"
    assert sum("can't play bright" in r.message for r in caplog.records) == 1    # tried once
    monkeypatch.undo()
    player.want = "subtle"
    player.tick()
    assert player.now == "subtle" and player.failed is None
