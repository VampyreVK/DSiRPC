"""
mkds_tilt.py - the race view's course in 2.5D (overlay/mkds.py), as a race's
overview on TV has it: the course tilted away from you with its ups and downs
raised, and under it a strip of the lap's heights.

    TiltedCourse   the course's map (overlay/mkds_art.py) as the ground, seen
                   from above at TILT, and the road on it as a ribbon at its
                   own height (core/mkds_maps.py's HEIGHTS, one a checkpoint),
                   with a shadow on the ground under any raised stretch.
                   Racers stand at their height (the console's, +0x84) over
                   a shadow on the ground. Where the course crosses over
                   itself (DECKS) the upper road is drawn after the lower,
                   and again, see-through, over the racers below it.
    HeightStrip    the lap from the finish line, left to right, by distance,
                   and the course's height along it, filled; a dot for each
                   racer where it is on the lap and how high.

Heights are raised so the course's whole range rises about RISE_PX on the
screen, but never more than EXAGGERATE times the map's own scale, so a flat
course stays flat; one whose heights hardly change (FLAT_BELOW) gets no
strip. Both are made once a course (the ground and the road, the strip's
profile) and only the racers drawn each frame. The flat view in
overlay/mkds.py is the fallback: no heights for the course, or a course the
console has otherwise than its file.
"""

import math

import pygame

from core.mkds_reader import midpoints

TILT = 0.56                 # the ground's depth on the screen, of its width (about cos 56 degrees)
RISE_PX = 20                # the course's whole range of heights rises about this many pixels
EXAGGERATE = 4.0            # ... but heights at most this many times the map's own scale
FLAT_BELOW = 60.0           # world units: a course whose heights range less has no strip
ROAD = 0.42                 # the road ribbon, this much of each checkpoint line's length
ROAD_INNER = 0.28            # ... and its fill inside the dark edge
SHADOW_ABOVE = 20.0         # a stretch this far over the ground casts a shadow
STRIP_H = 26                # the height strip's height in pixels
DECK_ALPHA = 170
PAD = 0.05

ROAD_FILL, ROAD_HI, ROAD_EDGE = (150, 158, 172), (196, 204, 214), (10, 12, 16)
SHADOW = (0, 0, 0, 90)
STRIP_BG, STRIP_FILL, STRIP_TOP, STRIP_GRID = (18, 22, 28), (52, 64, 80), (150, 166, 188), (30, 36, 46)


def turned(x, z, turn):
    return (-z, x) if turn else (x, z)


def lap_lengths(mids):
    """The distance round the lap at each checkpoint's middle, and the lap's length."""
    at, total = [], 0.0
    for i, m in enumerate(mids):
        at.append(total)
        total += math.dist(m, mids[(i + 1) % len(mids)])
    return at, total


def lap_fraction(x, z, cp, mids, at, total):
    """How far round the lap (0-1) a racer at (x, z) is, its last checkpoint
    `cp`: along the stretch from that checkpoint's middle to the next one's."""
    n = len(mids)
    if not n or not total:
        return 0.0
    cp %= n
    (ax, az), (bx, bz) = mids[cp], mids[(cp + 1) % n]
    dx, dz = bx - ax, bz - az
    seg = dx * dx + dz * dz
    t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / seg)) if seg else 0.0
    return ((at[cp] + t * math.sqrt(seg)) / total) % 1.0


def usable(checkpoints, heights):
    """Whether the course can be drawn tilted: its heights, one for each of
    the console's checkpoints."""
    return bool(checkpoints) and bool(heights) and len(heights) == len(checkpoints)


class TiltedCourse:
    def __init__(self, checkpoints, heights, size, decks=(), upper=None):
        """checkpoints: the console's ((x1, z1, x2, z2, key), ...); heights:
        one for each (core/mkds_maps.py's HEIGHTS); size: the map's (w, h)
        on the screen; decks: the course's DECKS as the console has it;
        upper: a function (racer-like dict, decks) -> on an upper deck."""
        self.size = size
        self.heights = heights
        self.decks = decks
        self.base, top = min(heights), max(heights)
        self.range = top - self.base
        mids = midpoints(checkpoints)
        self.lines = [(x1, z1, x2, z2) for x1, z1, x2, z2, _ in checkpoints]
        self.mids = mids
        self.edges = self._edges(ROAD)
        self._fit(checkpoints)
        self.on_upper = upper
        self.upper_segments = [i for i in range(len(mids)) if self._segment_up(i)]
        self.ground = None       # the map, the shadows and the road: made by build()
        self.bridges = None      # the upper decks' road, see-through: drawn over the racers below

    # -- where things go -----------------------------------------------------------

    def _fit(self, checkpoints):
        """The quarter turn (or not) and scale that fit the course biggest,
        and how much a world unit of height raises a point."""
        w, h = self.size
        pts = [p for c in checkpoints for p in ((c[0], c[1]), (c[2], c[3]))]
        best = None
        for turn in (False, True):
            uv = [turned(x, z, turn) for x, z in pts]
            u0, u1 = min(p[0] for p in uv), max(p[0] for p in uv)
            v0, v1 = min(p[1] for p in uv), max(p[1] for p in uv)
            pad = PAD * max(u1 - u0, v1 - v0, 400.0)
            u0, u1, v0, v1 = u0 - pad, u1 + pad, v0 - pad, v1 + pad
            rise = 0.0
            for _ in range(3):              # (the rise takes room the scale depends on)
                scale = min(w / (u1 - u0), (h - rise) / ((v1 - v0) * TILT))
                rise = min(RISE_PX, self.range * scale * EXAGGERATE)
            if best is None or scale > best[0] * 1.05:
                best = (scale, turn, (u0, v0, u1, v1), rise)
        self.scale, self.turn, (u0, v0, u1, v1), self.rise = best
        self.lift = self.rise / self.range if self.range else 0.0
        # the ground's top left on the screen, the course in the middle of what's left
        self.gx = (w - (u1 - u0) * self.scale) / 2 - u0 * self.scale
        self.gy = self.rise + (h - self.rise - (v1 - v0) * self.scale * TILT) / 2 - v0 * self.scale * TILT

    def ground_point(self, x, z):
        u, v = turned(x, z, self.turn)
        return self.gx + u * self.scale, self.gy + v * self.scale * TILT

    def point(self, x, z, y):
        """A world point on the screen (relative to the map's top left)."""
        gx, gy = self.ground_point(x, z)
        return gx, gy - (y - self.base) * self.lift

    def window(self):
        """The world the ground shows (u0, v0, u1, v1, in turned()'s terms)."""
        w, h = self.size
        s = self.scale
        return (-self.gx / s, -self.gy / (s * TILT), (w - self.gx) / s, (h - self.gy) / (s * TILT))

    def _segment_up(self, i):
        """Whether the road from checkpoint i to the next is an upper deck."""
        if not self.decks:
            return False
        n = len(self.mids)
        (ax, az), (bx, bz) = self.mids[i], self.mids[(i + 1) % n]
        y = (self.heights[i] + self.heights[(i + 1) % n]) / 2
        for x, z, reach, low, high, _ in self.decks:
            near = min(math.hypot(ax - x, az - z), math.hypot(bx - x, bz - z),
                       math.hypot((ax + bx) / 2 - x, (az + bz) / 2 - z))
            if near <= 1.5 * reach and abs(y - high) < abs(y - low):
                return True
        return False

    # -- the static part ------------------------------------------------------------

    def _edges(self, k):
        """Each checkpoint line shortened to k of itself, about its middle:
        the road's two sides, as ((x, z), (x, z))."""
        return [((mx + (x1 - mx) * k, mz + (z1 - mz) * k), (mx + (x2 - mx) * k, mz + (z2 - mz) * k))
                for (x1, z1, x2, z2), (mx, mz) in zip(self.lines, self.mids)]

    def _quad(self, i, y_of, edges=None):
        edges = edges or self.edges
        n = len(self.mids)
        (l1, r1), (l2, r2) = edges[i], edges[(i + 1) % n]
        ya, yb = y_of(i), y_of((i + 1) % n)
        return [self.point(*l1, ya), self.point(*r1, ya), self.point(*r2, yb), self.point(*l2, yb)]

    def build(self, ground=None):
        """Draws the ground (the map, or None for a plain one), the shadows
        and the road, and the upper decks' see-through copy."""
        w, h = self.size
        surf = pygame.Surface(self.size)
        if ground is not None:
            surf.blit(ground, (0, 0))
        else:
            surf.fill(STRIP_BG)
            for gx in range(8, w, 8):
                pygame.draw.line(surf, STRIP_GRID, (gx, 0), (gx, h - 1))
            for gy in range(8, h, 8):
                pygame.draw.line(surf, STRIP_GRID, (0, gy), (w - 1, gy))
        n = len(self.mids)
        shadows = pygame.Surface(self.size, pygame.SRCALPHA)
        for i in range(n):
            if max(self.heights[i], self.heights[(i + 1) % n]) - self.base > SHADOW_ABOVE:
                pygame.draw.polygon(shadows, SHADOW, self._quad(i, lambda j: self.base))
        surf.blit(shadows, (0, 0))
        order = sorted(range(n), key=lambda i: (i in self.upper_segments, self._depth(i)))
        for i in order:
            self._road(surf, i)
        self._finish(surf)
        self.ground = surf
        bridges = pygame.Surface(self.size, pygame.SRCALPHA)
        for i in self.upper_segments:
            self._road(bridges, i)
        if self.upper_segments:
            bridges.set_alpha(DECK_ALPHA)      # (per-pixel alpha surface: blended through a copy below)
            fade = pygame.Surface(self.size, pygame.SRCALPHA)
            fade.fill((255, 255, 255, DECK_ALPHA))
            bridges.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.bridges = bridges
        return self

    def _depth(self, i):
        n = len(self.mids)
        return (self.ground_point(*self.mids[i])[1] + self.ground_point(*self.mids[(i + 1) % n])[1]) / 2

    def _road(self, surf, i):
        """The road from checkpoint i to the next: a dark edge, the fill
        inside it, and the fill's middle line lit."""
        if not hasattr(self, '_inner'):
            self._inner = self._edges(ROAD_INNER)
        height = lambda j: self.heights[j]   # noqa: E731
        pygame.draw.polygon(surf, ROAD_EDGE, self._quad(i, height), 0)
        pygame.draw.polygon(surf, ROAD_FILL, self._quad(i, height, self._inner), 0)
        n = len(self.mids)
        a, b = self.mids[i], self.mids[(i + 1) % n]
        pygame.draw.line(surf, ROAD_HI, self.point(*a, self.heights[i]), self.point(*b, self.heights[(i + 1) % n]))

    def _finish(self, surf):
        (l1, r1) = self.edges[0]
        a, b = self.point(*l1, self.heights[0]), self.point(*r1, self.heights[0])
        pygame.draw.line(surf, ROAD_EDGE, a, b, 3)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        pygame.draw.line(surf, (255, 255, 255), a, (mx, my), 1)
        pygame.draw.line(surf, (24, 24, 24), (mx, my), b, 1)

    # -- each frame ----------------------------------------------------------------------

    def racer_point(self, x, z, y):
        """(the racer on the screen, its shadow on the ground): heights kept
        to a little past the course's own, so a bad read can't fling a dot."""
        y = max(self.base - 40, min(self.base + self.range + 120, y if y is not None else self.base))
        return self.point(x, z, y), self.ground_point(x, z)


class HeightStrip:
    def __init__(self, checkpoints, heights, size):
        self.size = size
        self.mids = midpoints(checkpoints)
        self.at, self.total = lap_lengths(self.mids)
        self.heights = heights
        self.base, self.top = min(heights), max(heights)
        self.surface = None

    def y(self, height):
        h = self.size[1]
        span = (self.top - self.base) or 1.0
        return (h - 3) - (min(max(height, self.base), self.top) - self.base) / span * (h - 7)

    def x(self, fraction):
        return 1 + fraction * (self.size[0] - 3)

    def build(self):
        w, h = self.size
        surf = pygame.Surface(self.size)
        surf.fill(STRIP_BG)
        for gy in range(h - 3, 0, -6):
            pygame.draw.line(surf, STRIP_GRID, (0, gy), (w - 1, gy))
        pts = [(self.x(a / self.total), self.y(hgt)) for a, hgt in zip(self.at, self.heights)]
        pts.append((self.x(1.0), self.y(self.heights[0])))
        pygame.draw.polygon(surf, STRIP_FILL, [(1, h - 1)] + pts + [(w - 2, h - 1)])
        pygame.draw.lines(surf, STRIP_TOP, False, pts, 1)
        for fx in (self.x(0.0), self.x(1.0)):      # the finish line, at both ends
            for k, yy in enumerate(range(1, h - 1, 2)):
                surf.set_at((round(fx), yy), (255, 255, 255) if k % 2 else (24, 24, 24))
        self.surface = surf
        return self

    def place(self, x, z, cp, height):
        """Where a racer goes in the strip (relative to its top left)."""
        f = lap_fraction(x, z, cp, self.mids, self.at, self.total)
        return self.x(f), self.y(height if height is not None else self.base)
