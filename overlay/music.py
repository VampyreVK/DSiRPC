"""
music.py - the overlay window's ambient music (the tray's "Ambient music"):
the launcher's menu songs, Bright and Subtle, looped while the window is
open and not minimized. They're the very XM modules the launcher plays
(launcher/audio, made from the M8 songs in launcher/music by
tools/make_music.py), played by pygame's mixer, so the PC and the console
sound alike.

pygame's mixer isn't for several threads, so Music is the window's: the
tray sets what it wants from anywhere (want), and the window's loop calls
tick() every frame to follow it.
"""

import logging
import os

import pygame

from core.paths import ROOT
from utils.config import MUSIC_CHOICES as CHOICES

FOLDER =os.path.join(ROOT, "launcher", "audio")
VOLUME = 0.5        # under a game, a call or a stream
FADE_MS = 400


def choice(text):
    """A config value -> one of CHOICES ('off' for anything else)."""
    text = (text or "").strip().lower()
    return text if text in CHOICES else "off"


def song_path(name):
    return os.path.join(FOLDER, name + ".xm")


class Music:
    def __init__(self, want="off"):
        self.want = choice(want)
        self.now = "off"        # what's loaded (playing, paused or fading out)
        self.fading = False
        self.paused = False
        self.failed = None      # a song that wouldn't play: not tried again until another is wanted

    def tick(self):
        """Follows self.want: fades out what's playing, then starts the new one."""
        if self.fading:
            if pygame.mixer.music.get_busy():
                return
            self.fading = False
            self.now = "off"
        if self.want == self.now or self.want == self.failed:
            return
        if self.now != "off":
            if self.paused:
                pygame.mixer.music.stop()
                self.now = "off"
            else:
                pygame.mixer.music.fadeout(FADE_MS)
                self.fading = True
                return
        if self.want != "off":
            self._start(self.want)

    def _start(self, name):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(song_path(name))
            pygame.mixer.music.set_volume(VOLUME)
            pygame.mixer.music.play(loops=-1, fade_ms=FADE_MS)
        except (pygame.error, OSError) as e:
            logging.warning(f"Ambient music: can't play {name} ({e})")
            self.failed = name
            return
        self.now, self.failed = name, None
        if self.paused:
            pygame.mixer.music.pause()

    def pause(self, yes):
        """While the window's minimized (or hidden): paused, then on again."""
        if yes == self.paused:
            return
        self.paused = yes
        if self.now != "off" and not self.fading:
            if yes:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()

    def close(self):
        """As the window closes: a short fade (the window's thread waits for it)."""
        if self.now != "off" and not self.paused and pygame.mixer.get_init():
            pygame.mixer.music.fadeout(FADE_MS // 2)
            pygame.time.wait(FADE_MS // 2)
        self.now = "off"
