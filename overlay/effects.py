"""
effects.py - short move animations for the battle view, drawn with plain
pixel shapes (no image files). The move's type picks the style:

    flame    Fire, Dragon                  flames fly over, then flare up
    bubbles  Water, Poison                 wobbling bubbles fly over and pop
    leaves   Grass                         spinning leaves fly over
    swarm    Bug                           a cloud of specks buzzes over
    bolt     Electric                      lightning strikes from above
    shards   Ice                           ice shards close in from all sides
    rocks    Rock, Ground                  rocks drop onto the target
    rings    Psychic, special Normal moves rings ripple out
    wisps    Ghost, special Dark moves     wisps circle the target
    slash    Flying, Steel, physical Dark  claw streaks
    impact   Normal, Fighting              a hit spark
    aura     any status move               sparkles rise around the user

Effects know the battlers only by key ('you0', 'foe0', ...). The scene
passes in where each sprite is drawn this frame, so an effect follows its
Pokemon (and is skipped if one isn't on screen).
"""

import math
import random

import pygame

from . import ui

STYLE_BY_TYPE = {
    'Fire': 'flame', 'Dragon': 'flame', 'Water': 'bubbles', 'Poison': 'bubbles',
    'Grass': 'leaves', 'Bug': 'swarm', 'Electric': 'bolt', 'Ice': 'shards',
    'Rock': 'rocks', 'Ground': 'rocks', 'Psychic': 'rings', 'Ghost': 'wisps',
    'Flying': 'slash', 'Steel': 'slash', 'Normal': 'impact', 'Fighting': 'impact',
}

# style -> (duration ms, fraction of it at which the move reaches the target)
TIMING = {
    'flame': (900, 0.55), 'bubbles': (950, 0.6), 'leaves': (850, 0.6), 'swarm': (900, 0.6),
    'bolt': (650, 0.3), 'shards': (700, 0.5), 'rocks': (800, 0.55), 'rings': (750, 0.3),
    'wisps': (850, 0.5), 'slash': (450, 0.25), 'impact': (420, 0.15), 'aura': (900, 0.5),
}

WHITE = (248, 248, 248)


def style_for(mtype, category):
    if category == 'Status':
        return 'aura'
    if mtype == 'Dark':
        return 'slash' if category == 'Physical' else 'wisps'
    if mtype == 'Normal' and category == 'Special':
        return 'rings'
    return STYLE_BY_TYPE.get(mtype, 'impact')


def _lerp(a, b, k):
    return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k


def _pt(p):
    return int(round(p[0])), int(round(p[1]))


def _blob(surf, pos, r, fill, core, edge):
    """A round flame/energy blob: dark rim, fill, bright core."""
    x, y = _pt(pos)
    pygame.draw.circle(surf, edge, (x, y), r + 1)
    pygame.draw.circle(surf, fill, (x, y), r)
    pygame.draw.circle(surf, core, (x, y + 1), max(1, r - 2))


class Effect:
    def __init__(self, mtype, category, src, dst, start):
        """src, dst: battler keys (user and target). start: when it begins (ms)."""
        self.style = style_for(mtype, category)
        self.color = ui.TYPE_COLORS.get(mtype, (200, 200, 200))
        self.src, self.dst = src, dst
        self.start = start
        self.duration, lands = TIMING[self.style]
        self.impact = start + int(self.duration * lands)   # when it reaches the target
        self.lands = lands
        rng = random.Random(start)
        self.parts = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random()) for _ in range(12)]

    def draw(self, surf, t_ms, boxes):
        """boxes: key -> pygame.Rect of each battler's sprite this frame.
        Returns False once the effect is over."""
        p = (t_ms - self.start) / self.duration
        if p >= 1:
            return False
        src, dst = boxes.get(self.src), boxes.get(self.dst)
        if p < 0 or src is None or (dst is None and self.style != 'aura'):
            return True
        getattr(self, '_' + self.style)(surf, p, t_ms, src, dst)
        return True

    # Each style gets p (0..1 through the effect), the time, and the user's
    # and target's sprite boxes.

    def _travel(self, p, src, dst, i, stagger, arc=10):
        """Where particle i is on its way from src to dst (None if not
        launched yet or already there)."""
        k = (p / self.lands - i * stagger) / (1 - stagger * 3)
        if not 0 <= k <= 1:
            return None
        x, y = _lerp(src.center, dst.center, k)
        return x, y - math.sin(math.pi * k) * arc, k

    def _flame(self, surf, p, t_ms, src, dst):
        c, hot, edge = self.color, ui.lighten(self.color, 110), ui.darken(self.color, 90)
        flick = (t_ms // 60) % 2
        if p < self.lands:
            for i in range(3):
                pos = self._travel(p, src, dst, i, 0.12, arc=14)
                if pos:
                    _blob(surf, pos[:2], 6 - i * 2 + flick, c, hot, edge)
            return
        q = (p - self.lands) / (1 - self.lands)
        for dx, dy, s in self.parts[:6]:
            rise = q * (16 + s * 14)
            x, y = dst.centerx + dx * 16, dst.bottom - 6 - rise + dy * 3
            _blob(surf, (x, y), max(1, int((1 - q) * (5 + s * 3))) + flick, c, hot, edge)

    def _bubbles(self, surf, p, t_ms, src, dst):
        rim = ui.darken(self.color, 50)
        fill = ui.lighten(self.color, 50)
        for i in range(6):
            pos = self._travel(p, src, dst, i, 0.09, arc=8)
            if pos:
                x, y, k = pos
                y += math.sin(k * 12 + i) * 4
                r = 3 + (i % 2) * 2
                pygame.draw.circle(surf, fill, _pt((x, y)), r)
                pygame.draw.circle(surf, rim, _pt((x, y)), r, 1)
                pygame.draw.rect(surf, WHITE, (int(x) - r // 2, int(y) - r // 2, 2, 2))
        if p >= self.lands:
            q = (p - self.lands) / (1 - self.lands)
            if q < 0.7:
                for dx, dy, s in self.parts[:5]:
                    x, y = dst.centerx + dx * 14, dst.centery + dy * 12
                    a, b = 2 + q * 4, 4 + q * 7
                    for ux, uy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        pygame.draw.line(surf, rim, _pt((x + ux * a, y + uy * a)), _pt((x + ux * b, y + uy * b)))

    def _leaves(self, surf, p, t_ms, src, dst):
        c, vein = self.color, ui.darken(self.color, 80)
        for i in range(4):
            pos = self._travel(p, src, dst, i, 0.1, arc=18 - i * 4)
            if not pos:
                continue
            x, y, k = pos
            a = k * 4 * math.pi + i
            ux, uy = math.cos(a), math.sin(a)
            pts = [_pt(q) for q in ((x + ux * 6, y + uy * 6), (x - uy * 3, y + ux * 3),
                                    (x - ux * 6, y - uy * 6), (x + uy * 3, y - ux * 3))]
            pygame.draw.polygon(surf, c, pts)
            pygame.draw.polygon(surf, vein, pts, 1)
            pygame.draw.line(surf, vein, pts[0], pts[2])
        if p >= self.lands:
            self._burst(surf, dst.center, (p - self.lands) / (1 - self.lands), ui.lighten(c, 60), 16)

    def _swarm(self, surf, p, t_ms, src, dst):
        c = ui.darken(self.color, 40)
        for i, (dx, dy, s) in enumerate(self.parts):
            k = min(1.0, max(0.0, p / self.lands - s * 0.3) / 0.7)
            if k <= 0:
                continue
            x, y = _lerp(src.center, dst.center, k)
            buzz = t_ms / 45 + i * 2
            x += dx * 10 + math.sin(buzz) * 3
            y += dy * 10 + math.cos(buzz * 1.3) * 3
            size = 3 if i % 3 else 2
            pygame.draw.rect(surf, ui.darken(c, 60), (int(x) - 1, int(y) - 1, size + 2, size + 2))
            pygame.draw.rect(surf, ui.lighten(c, 40) if i % 2 else c, (int(x), int(y), size, size))

    def _bolt(self, surf, p, t_ms, src, dst):
        if p < 0.7 and (t_ms // 50) % 3:
            rng = random.Random(t_ms // 70)
            x, y = dst.centerx + rng.randint(-4, 4), max(0, dst.top - 60)
            pts = [(x, y)]
            steps = 6
            for j in range(1, steps + 1):
                ty = y + (dst.centery - y) * j / steps
                tx = dst.centerx + (rng.randint(-7, 7) if j < steps else 0)
                pts.append((tx, ty))
            pts = [_pt(q) for q in pts]
            pygame.draw.lines(surf, self.color, False, pts, 3)
            pygame.draw.lines(surf, WHITE, False, pts, 1)
        if p >= self.lands:
            self._burst(surf, dst.center, (p - self.lands) / (1 - self.lands), ui.darken(self.color, 40), 18, width=2)

    def _shards(self, surf, p, t_ms, src, dst):
        ice, edge = ui.lighten(self.color, 30), ui.darken(self.color, 110)
        cx, cy = dst.center
        if p < self.lands:
            k = p / self.lands
            r = 38 * (1 - ui.ease_out(k)) + 4
            for i in range(6):
                a = i * math.pi / 3 + 0.3
                ux, uy = math.cos(a), math.sin(a)
                tip = (cx + ux * r, cy + uy * r)
                back = (cx + ux * (r + 11), cy + uy * (r + 11))
                side = (-uy * 3, ux * 3)
                pts = [_pt(q) for q in (tip, (back[0] + side[0], back[1] + side[1]), (back[0] - side[0], back[1] - side[1]))]
                pygame.draw.polygon(surf, ice, pts)
                pygame.draw.polygon(surf, edge, pts, 1)
                surf.set_at(_pt(_lerp(tip, back, 0.35)), WHITE)
        else:
            self._burst(surf, (cx, cy), (p - self.lands) / (1 - self.lands), edge, 20, width=2)

    def _rocks(self, surf, p, t_ms, src, dst):
        c = ui.darken(self.color, 30)
        hi, dust = ui.lighten(self.color, 40), (200, 190, 170)
        for i, (dx, dy, s) in enumerate(self.parts[:4]):
            k = (p - i * 0.08) / self.lands
            x = dst.centerx + dx * 14
            ground = dst.bottom - 4 + dy * 2
            if 0 <= k < 1:
                y = dst.top - 40 + (ground - dst.top + 40) * k * k
                size = 6 + int(s * 4)
                rx, ry = int(x) - size // 2, int(y) - size // 2
                pygame.draw.rect(surf, ui.darken(c, 70), (rx - 1, ry - 1, size + 2, size + 2))
                pygame.draw.rect(surf, c, (rx, ry, size, size))
                pygame.draw.line(surf, hi, (rx, ry), (rx + size - 2, ry))
                pygame.draw.line(surf, hi, (rx, ry), (rx, ry + size - 2))
            elif k >= 1:
                q = (p - i * 0.08 - self.lands) / 0.25   # dust puffs for a quarter of the effect
                if q < 1:
                    for side in (-1, 1):
                        pygame.draw.circle(surf, dust, (int(x + side * (3 + q * 8)), int(ground - q * 3)),
                                           max(1, int(3 * (1 - q))))

    def _rings(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        for i in range(3):
            k = (p - i * 0.18) / 0.6
            if 0 <= k < 1:
                r = int(4 + 28 * k)
                c = ui.lighten(self.color, 40) if i % 2 else self.color
                pygame.draw.ellipse(surf, c, (cx - r, cy - r * 2 // 3, 2 * r, r * 4 // 3), 1)

    def _wisps(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        c, pale, dark = self.color, ui.lighten(self.color, 90), ui.darken(self.color, 60)
        for i in range(5):
            a = i * 2 * math.pi / 5 + p * 3 * math.pi
            r = 28 * (1 - p * 0.7)
            for trail in range(4):
                b = a - trail * 0.22
                x, y = cx + math.cos(b) * r, cy + math.sin(b) * r * 0.6
                size = 5 - trail
                if trail == 0:
                    pygame.draw.rect(surf, dark, (int(x) - 1, int(y) - 1, size + 2, size + 2))
                pygame.draw.rect(surf, pale if trail == 0 else c, (int(x), int(y), size, size))

    def _slash(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        edge = ui.darken(self.color, 40) if self.color[0] + self.color[1] + self.color[2] > 480 else self.color
        for i in range(3):
            k = (p - i * 0.15) / 0.55
            if not 0 <= k < 1:
                continue
            ox = (i - 1) * 8
            a = (cx + ox - 12, cy - 14)
            b = (cx + ox + 10, cy + 12)
            head = min(1.0, k * 2)
            tail = max(0.0, k * 2 - 1)
            s, e = _pt(_lerp(a, b, tail)), _pt(_lerp(a, b, head))
            pygame.draw.line(surf, edge, s, e, 3)
            pygame.draw.line(surf, WHITE, s, e, 1)

    def _impact(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        cx += int(self.parts[0][0] * 6)
        cy += int(self.parts[0][1] * 6)
        self._burst(surf, (cx, cy), p, ui.darken(self.color, 40), 20, width=2)
        if p < 0.5:
            r = 2 + int(4 * math.sin(math.pi * p * 2))
            pygame.draw.circle(surf, ui.darken(self.color, 60), (cx, cy), r + 1)
            pygame.draw.circle(surf, WHITE, (cx, cy), r)

    def _aura(self, surf, p, t_ms, src, dst):
        cx, bottom = src.centerx, src.bottom
        c = ui.lighten(self.color, 50)
        r = int(6 + 20 * p)
        if p < 0.8:
            pygame.draw.ellipse(surf, c, (cx - r, bottom - 4 - r // 4, 2 * r, r // 2), 1)
        for i, (dx, dy, s) in enumerate(self.parts[:6]):
            k = (p * 1.3 - s * 0.3)
            if 0 <= k < 1:
                ui.sparkle(surf, int(cx + dx * 16), int(bottom - 6 - k * (src.height * 0.8)), t_ms + i * 90, c)

    def _burst(self, surf, center, q, color, reach, width=1):
        """Eight short rays flying out from center (q: 0..1 through it)."""
        if not 0 <= q < 1:
            return
        cx, cy = center
        inner, outer = reach * q * 0.6, reach * (0.3 + q * 0.7)
        for i in range(8):
            a = i * math.pi / 4 + 0.2
            ux, uy = math.cos(a), math.sin(a)
            length = outer if i % 2 == 0 else outer * 0.7
            s = _pt((cx + ux * inner, cy + uy * inner))
            e = _pt((cx + ux * length, cy + uy * length))
            pygame.draw.line(surf, color, s, e, width + 1 if i % 2 == 0 else width)
            pygame.draw.line(surf, WHITE, s, e, 1)
