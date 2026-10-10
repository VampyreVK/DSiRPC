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
import sys
import threading

import pygame

from core.paths import DATA, ROOT
from .scenes import Overlay, W, H
from .sprites import SpriteBank
from . import ui

CAPTIONS = {'auto': "DSiRPC", 'battle': "DSiRPC (battle)", 'party': "DSiRPC (party screen: V to go back)"}
MAC = sys.platform == "darwin"
# The macOS app's icon (Assets/icons), for the Dock while the window's open
MAC_ICON = os.path.join(ROOT, "Assets", "icons", "Exports", "DSiRPC-iOS-Default-1024@1x.png")


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

    @staticmethod
    def _set_icon(win):
        """DSiRPC's icon for the window (on a Mac, the Dock's), not pygame's.
        The export is full-bleed, so it's drawn the way macOS lays its icons
        out: 824 of 1024 pixels wide, centred, over a soft shadow."""
        try:
            icon = pygame.image.load(MAC_ICON)
        except (pygame.error, FileNotFoundError) as e:
            logging.info(f"No window icon: {e}")
            return
        size = 512
        body = size * 824 // 1024
        icon = pygame.transform.smoothscale(icon, (body, body))
        at = ((size - body) // 2, (size - body) // 2 - size // 256)
        shadow = pygame.Surface((size, size), pygame.SRCALPHA)
        mask = icon.copy()
        mask.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)  # the icon's shape in black
        mask.fill((255, 255, 255, 76), special_flags=pygame.BLEND_RGBA_MULT)  # at 30%
        shadow.blit(mask, (at[0], at[1] + size * 12 // 1024))
        out = pygame.transform.gaussian_blur(shadow, size * 14 // 1024)
        out.blit(icon, at)
        win.set_icon(out)

    def run(self):
        """Opens the window and draws until it's closed (or stop() is
        called). Returns True if the user closed it."""
        source = self.hub.source
        self.hub.add_listener(self._on_update)
        pygame.init()
        closed = False
        win = None
        try:
            scale = self.scale
            caption = CAPTIONS['auto']
            if MAC:
                # A window in Retina pixels (the canvas scales up by a whole
                # number, so it stays sharp), with DSiRPC's icon in the Dock
                win = pygame.Window(caption, (W * scale, H * scale), allow_high_dpi=True)
                self._set_icon(win)
                window = win.get_surface()
                logging.info(f"Window {win.size[0]}x{win.size[1]}, drawn at {window.get_width()}x{window.get_height()}")
            else:
                window = pygame.display.set_mode((W * scale, H * scale))
                pygame.display.set_caption(caption)
            # No alpha byte, whatever the window's format: a Mac's window has
            # one, and a canvas converted to it got pixels pygame blends onto
            # with alpha 0, which a Mac shows black (Overlay.present copies it)
            canvas = pygame.Surface((W, H), 0, 32)
            overlay = Overlay(SpriteBank(os.path.join(DATA, "Assets")))
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
                            if win:
                                win.size = (W * scale, H * scale)
                            else:
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
                    if win:
                        win.title = caption
                    else:
                        pygame.display.set_caption(caption)
                if win:
                    window = win.get_surface()   # a new one after a resize (or a move to another screen)
                overlay.present(window, canvas)
                if win:
                    win.flip()
                else:
                    pygame.display.flip()
                dt = clock.tick(self.fps)
        except Exception:
            logging.exception("The overlay window crashed")
        finally:
            self.hub.remove_listener(self._on_update)
            if win:
                win.destroy()
            pygame.quit()
        return closed
