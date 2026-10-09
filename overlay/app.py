"""
app.py - the overlay window: draws the 256x192 canvas every frame from a
state hub (core/hub.py) and scales it up by a whole number, so the pixels
stay crisp for window capture in OBS or a Discord screen share. Sprites shown
smaller than their own pixels (the Unova party icons) are drawn after the
scaling, at the window's resolution (Overlay.present).

dsirpc.py opens it with --overlay (or from the tray menu), next to the
Discord Rich Presence; it only shows what the hub already reads, so it never
talks to the DSi itself.

Keys: N next demo scene, V the party screen and back (to the battle in a
      battle, else the main view; a battle starting or ending goes back
      to its own), 1-6 window scale.
"""

import logging
import os
import queue
import threading

import pygame

from .scenes import Overlay, W, H
from .sprites import SpriteBank
from . import ui

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTIONS = {'auto': "DSiRPC", 'battle': "DSiRPC (battle)", 'party': "DSiRPC (party screen: V to go back)"}


def parse_color(text):
    """'00FF00' or '#00FF00' -> (0, 255, 0)."""
    text = text.strip().lstrip('#')
    if len(text) != 6:
        raise ValueError(f"{text!r} isn't an RRGGBB colour")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


class OverlayWindow:
    def __init__(self, hub, scale=3, chroma=None, fps=60, on_scale=None):
        """hub: a StateHub (it may already be running). chroma: 'RRGGBB' to
        fill the background with, for a chroma key. on_scale(n) is called
        when the window size is changed with the 1-6 keys."""
        self.hub = hub
        self.scale = max(1, min(6, int(scale)))
        self.fps = fps
        self.on_scale = on_scale
        self.stop_event = threading.Event()
        ui.THEME['chroma'] = parse_color(chroma) if chroma else None  # ValueError if it isn't RRGGBB
        self._events = queue.Queue()

    def _on_update(self, snap, events):
        for e in events:
            self._events.put(e)

    def stop(self):
        """Closes the window from another thread (run() returns soon after)."""
        self.stop_event.set()

    def run(self):
        """Opens the window and draws until it's closed (or stop() is
        called). Returns True if the user closed it."""
        source = self.hub.source
        self.hub.add_listener(self._on_update)
        pygame.init()
        closed = False
        try:
            scale = self.scale
            window = pygame.display.set_mode((W * scale, H * scale))
            caption = CAPTIONS['auto']
            pygame.display.set_caption(caption)
            canvas = pygame.Surface((W, H)).convert()
            overlay = Overlay(SpriteBank(os.path.join(HERE, "Assets")))
            overlay.hires_ok = True  # present() draws its sprites at the window's resolution
            clock = pygame.time.Clock()
            dt = 0
            while not self.stop_event.is_set():
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        closed = True
                        self.stop_event.set()
                    elif e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_n and hasattr(source, 'next_scene'):
                            source.next_scene()
                        elif e.key == pygame.K_v:
                            overlay.toggle_view()
                        elif pygame.K_1 <= e.key <= pygame.K_6:
                            scale = e.key - pygame.K_0
                            window = pygame.display.set_mode((W * scale, H * scale))
                            if self.on_scale:
                                self.on_scale(scale)

                t_ms = pygame.time.get_ticks()
                evs = []
                while not self._events.empty():
                    evs.append(self._events.get_nowait())
                overlay.handle_events(evs, t_ms)
                overlay.draw(canvas, self.hub.snapshot(), t_ms, dt)
                if CAPTIONS[overlay.view] != caption:   # the view changed (V, or a battle began or ended)
                    caption = CAPTIONS[overlay.view]
                    pygame.display.set_caption(caption)
                overlay.present(window, canvas)
                pygame.display.flip()
                dt = clock.tick(self.fps)
        except Exception:
            logging.exception("The overlay window crashed")
        finally:
            self.hub.remove_listener(self._on_update)
            pygame.quit()
        return closed
