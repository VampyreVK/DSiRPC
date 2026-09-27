"""
markers.py - small looping markers around a battler for its conditions,
drawn with pixel shapes like effects.py (no image files):

    Asleep                  Z's drifting up from its head
    Paralyzed               yellow sparks flickering around it
    Poisoned, Badly poisoned  purple bubbles rising from it
    Burned                  little flames at its feet
    Frozen                  ice crystals twinkling around it (scenes.py
                            also tints the sprite icy blue)
    Confused                three stars circling its head
    Infatuated              pink hearts floating up
    Leech Seed              green sprouts at its feet
    Cursed                  a purple flame above it

The status comes from the parser's `status`, the rest from `conditions`.
"""

import math

import pygame

from . import ui

FROZEN_TINT = (170, 210, 255)

_HEART = [".#.#.", "#####", "#####", ".###.", "..#.."]


def draw(surf, rect, mon, t_ms, font):
    """rect: where the battler's sprite is drawn this frame."""
    status = mon.get('status')
    conditions = mon.get('conditions') or []
    if status == 'Asleep':
        _sleep(surf, rect, t_ms, font)
    elif status == 'Paralyzed':
        _sparks(surf, rect, t_ms)
    elif status in ('Poisoned', 'Badly poisoned'):
        _bubbles(surf, rect, t_ms, (176, 96, 208) if status == 'Poisoned' else (136, 64, 176))
    elif status == 'Burned':
        _flames(surf, rect, t_ms)
    elif status == 'Frozen':
        _ice(surf, rect, t_ms)
    if 'Confused' in conditions:
        _stars(surf, rect, t_ms)
    if 'Infatuated' in conditions:
        _hearts(surf, rect, t_ms)
    if 'Leech Seed' in conditions:
        _sprouts(surf, rect, t_ms)
    if 'Cursed' in conditions:
        _curse(surf, rect, t_ms)


def _sleep(surf, rect, t_ms, font):
    for i in range(3):
        p = (t_ms / 1800 + i / 3) % 1
        x = rect.right - 8 + int(p * 12)
        y = rect.top + 4 - int(p * 16)
        font.draw(surf, "Z" if p > 0.4 else "z", (x, y), (248, 248, 248), (64, 72, 96))


def _sparks(surf, rect, t_ms):
    step = t_ms // 170
    if step % 4 == 3:
        return  # a short gap, so it flickers
    for i in range(3):
        # A new spot every step, spread over the sprite.
        h = (step * 7 + i * 13) % 17
        x = rect.left + 4 + (h * 37 + i * 11) % max(1, rect.width - 8)
        y = rect.top + 4 + (h * 23 + i * 29) % max(1, rect.height - 8)
        pts = [(x, y), (x + 2, y + 2), (x, y + 3), (x + 2, y + 5)]
        pygame.draw.lines(surf, (248, 208, 48), False, pts, 2)
        pygame.draw.lines(surf, (255, 255, 200), False, pts, 1)


def _bubbles(surf, rect, t_ms, color):
    rim = ui.darken(color, 60)
    for i in range(4):
        p = (t_ms / 1600 + i / 4) % 1
        x = rect.centerx + int(math.sin(i * 2.1 + p * 6) * (rect.width * 0.3))
        y = rect.centery - int(p * (rect.height * 0.7))
        r = 2 + (i % 2)
        if p < 0.9:
            pygame.draw.circle(surf, color, (x, y), r)
            pygame.draw.circle(surf, rim, (x, y), r, 1)
            surf.set_at((x - 1, y - 1), (248, 232, 255))


def _flames(surf, rect, t_ms):
    flick = (t_ms // 90) % 3
    for i in range(3):
        x = rect.left + (i + 1) * rect.width // 4
        y = rect.bottom - 3
        h = 3 + (flick + i) % 3
        pygame.draw.circle(surf, (200, 72, 32), (x, y), h + 1)
        pygame.draw.circle(surf, (240, 136, 48), (x, y - 1), h)
        pygame.draw.circle(surf, (255, 224, 128), (x, y), max(1, h - 2))


def _ice(surf, rect, t_ms):
    for i in range(4):
        corner_x = rect.left + 3 if i % 2 == 0 else rect.right - 4
        corner_y = rect.top + 6 if i < 2 else rect.bottom - 6
        size = 2 + ((t_ms // 200 + i) % 3)
        c = (224, 244, 255)
        pygame.draw.polygon(surf, (96, 160, 216), [(corner_x, corner_y - size - 1), (corner_x + size + 1, corner_y),
                                                   (corner_x, corner_y + size + 1), (corner_x - size - 1, corner_y)])
        pygame.draw.polygon(surf, c, [(corner_x, corner_y - size), (corner_x + size, corner_y),
                                      (corner_x, corner_y + size), (corner_x - size, corner_y)])


def _stars(surf, rect, t_ms):
    cx, cy = rect.centerx, rect.top + 2
    for i in range(3):
        a = t_ms / 400 + i * 2 * math.pi / 3
        x, y = int(cx + math.cos(a) * 12), int(cy + math.sin(a) * 4)
        ui.sparkle(surf, x, y, t_ms + i * 150, (248, 216, 64))


def _hearts(surf, rect, t_ms):
    for i in range(2):
        p = (t_ms / 1500 + i / 2) % 1
        x = rect.centerx - 8 + i * 12 + int(math.sin(p * 6 + i) * 2)
        y = rect.top + 6 - int(p * 14)
        if p > 0.85:
            continue
        for r, row in enumerate(_HEART):
            for c, ch in enumerate(row):
                if ch == '#':
                    surf.set_at((x + c, y + r), (240, 96, 152) if r else (255, 176, 208))


def _sprouts(surf, rect, t_ms):
    sway = 1 if (t_ms // 400) % 2 else 0
    for x in (rect.left + rect.width // 3, rect.right - rect.width // 3):
        y = rect.bottom - 2
        pygame.draw.line(surf, (64, 128, 48), (x, y), (x + sway, y - 4))
        pygame.draw.rect(surf, (120, 200, 80), (x + sway - 2, y - 6, 2, 2))
        pygame.draw.rect(surf, (120, 200, 80), (x + sway + 1, y - 5, 2, 2))


def _curse(surf, rect, t_ms):
    flick = (t_ms // 110) % 2
    x, y = rect.centerx, rect.top - 4
    pygame.draw.circle(surf, (72, 40, 104), (x, y), 3 + flick)
    pygame.draw.circle(surf, (152, 96, 200), (x, y - flick), 2)
