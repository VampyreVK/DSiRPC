"""
mkds_voxel.py - the race view's course as voxel terrain (overlay/mkds.py), seen
by a broadcast camera that circles the whole course, and cutting to one
behind the player for a battle or the last lap: the course's map
(overlay/mkds_art.py) as the ground's colours, raised into hills where the
course climbs, with every racer standing on it at their real height.

    VoxelCourse    made once a course, on a thread of its own: a heightmap
                   over the course, from the road's heights (core/mkds_maps.py's
                   HEIGHTS, one a checkpoint) along the road and a smooth
                   fall between them elsewhere, coloured from the map and
                   shaded by its slopes. Where the course crosses over itself
                   (DECKS) the upper road's the ground, raised on banks (the
                   map shows it on top there), and the lower one runs under
                   it through a tunnel, its mouth drawn as a dark arch in the
                   ground's face; racers in it are hidden as behind a hill.
                   Frames of the orbit (one each ORBIT_STEP degrees) are drawn
                   column by column, near to far ("voxel space": a column's
                   ground only shows above what's nearer), as they're needed
                   and kept, so after one time round it costs nothing.
    View           a camera: where it is, which way it looks, how high, and
                   where its horizon is on the screen. orbit_view() is the
                   broadcast camera's at an angle; chase_view() one behind a
                   racer, pulled back to keep a rival in the frame too (drawn
                   live, chase_frame(), at most CHASE_FPS a second).

The racers are drawn over a frame by overlay/mkds.py (place(), hidden()),
each frame, in the view the frame was drawn in.

It's drawn in the canvas's own pixels (SCALE 1), in the overlay's look: the
ground in a few flat colours of the course's map (GROUND_COLOURS of them,
lit or in shade by its slope), the road outlined, fading into the board's
colour (as the Tetris view's board) away from the course. Heights are raised (EXAGGERATE) so a
course's hills show at this distance; loops (Rainbow Road) come out as hills.
"""

import math
import threading
from collections import namedtuple

import pygame

from core.mkds_reader import midpoints

SCALE = 1                   # the frames' pixels to the canvas's
GRID = 200                  # the heightmap's cells along its longer side (the course and the fade round it)
ORBIT_MS = 150000           # once round the course in this long
ORBIT_STEP = 0.25           # degrees between frames of the orbit (a new one every ORBIT_MS / (360 / ORBIT_STEP))
FOV = 48.0                  # the camera's field of view, across
ELEVATION = 58.0            # how far the camera looks down (degrees, at the course's middle)
EXAGGERATE = 0.16           # the course's hills, at most this much of its width high...
MAX_EXAGGERATE = 1.5        # ... and at most this many times as high as they are
ROAD = 0.21                 # the road's half width, of a checkpoint line's length
SINK = 0.08                 # the ground off the road sits this much of the course's (raised) climb below it, and 6 more
AHEAD = 6                   # frames drawn ahead of the one showing (and only those, and two behind, kept)
SKY = (18, 22, 28)          # behind the course: the Tetris board's BOARD_BG (overlay/tetris.py)
GROUND_COLOURS = 4          # the ground's colours, from the course's map
ROAD_FILL = (150, 158, 172)
ROAD_EDGE = (40, 56, 66)    # the road's outline: the theme's panel_border (overlay/ui.py)
SHADE = 0.78                # the ground in shade (facing away from the light), this much as bright
SIDE = 0.55                 # a cliff's face (and the terrain's edge, and a bridge's side), this much as bright
CLIFF_PX = 3                # a column that drops more than this below level ground shows a cliff face
LOWER = 0.3                 # the ground between roads leans to the lower ones: a road this much of the course's
                            # climb above the one below counts e^-1 as much
RARE = 0.03                 # a map colour on less of the ground than this (a kerb's red) gives way to the others
DECK_THICK = 8.0            # an overpass's road over its tunnel (world units, before raising)
TUNNEL_MAX = 45.0           # a tunnel's mouth at most this high (world units): a mouth, not a canyon
TUNNEL = (6, 8, 12)         # the inside of a tunnel
ARCH = 6                    # a tunnel mouth's shape across the road: 2 round, more squarer
JOIN = 2                    # an upper road over a lower one this many segments on or fewer: where it
                            # comes down to meet it, not a tunnel
FINISH = ((248, 248, 248), (24, 24, 24))   # the start/finish line's squares
FINISH_SQUARE = 2           # ... in squares this many cells across (a pixel or so from the orbit, a few up close),
FINISH_CELLS = 4            # ... this many cells deep along the road (two rows of them)
BRIGHT = (64, 120)          # a course's ground near the road is brought into this band of brightness
                            # (0-255): a mostly black map (Waluigi Pinball) up, DK Pass's snow down
LIFT_MAX = 2.6              # ... but a dark one at most this many times brighter
ROAD_FLOOR = 96             # and its road at least this bright, so it reads
FADE_FROM, FADE_OVER = 2.0, 0.22  # the ground fades to the background from this many road widths off
                                  # the road, over this much of the course's radius
DECK_ALPHA = 215
EDGE = (8, 10, 14)
CHASE_FPS = 15              # the chase camera's frames a second (drawn live)
CHASE_BACK = 9.0            # it sits this many road widths behind the racer (or further, for a rival)...
CHASE_PITCH = 45.0          # ... this far up (degrees, looking down at the racer)
CHASE_AT = 0.62             # ... with the racer this far down the frame

# A camera: at (x, z) and height h (raised), looking along (fx, fz), the
# screen's right along (rx, rz); the horizon at `horizon` on the screen; the
# ground drawn from `near` to `far` (world units ahead)
View = namedtuple("View", "x z fx fz rx rz h horizon near far")


def _segment_distance(px, pz, ax, az, bx, bz):
    """(distance from p to the segment ab, how far along it, 0-1)."""
    dx, dz = bx - ax, bz - az
    seg = dx * dx + dz * dz
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / seg)) if seg else 0.0
    cx, cz = ax + dx * t, az + dz * t
    return math.hypot(px - cx, pz - cz), t


class VoxelCourse:
    def __init__(self, checkpoints, heights, size, decks=(), colours=None, threaded=True):
        """checkpoints: the console's ((x1, z1, x2, z2, key), ...); heights:
        one for each; size: the panel's (w, h) in canvas pixels; decks: the
        course's DECKS as the console has it; colours: (RGB bytes, width,
        height, k, ox, oy, mirror) of the course's map (core/mkds_maps.py's
        placement), or None for plain ground. threaded: make it on a thread
        (else as it's asked for, for pictures and tests)."""
        self.size = size
        self.w, self.h = size[0] * SCALE, size[1] * SCALE
        self.mids = midpoints(checkpoints)
        self.lines = [c[:4] for c in checkpoints]
        self.heights = list(heights)
        self.decks = decks
        self.colours = colours
        self.base = min(heights)
        widths = sorted(math.dist(c[:2], c[2:4]) for c in self.lines)
        self.half_road = ROAD * widths[len(widths) // 2]
        span = self._bounds()
        rise = max(heights) - self.base
        self.exaggerate = min(MAX_EXAGGERATE, EXAGGERATE * span / rise) if rise > 1 else 1.0
        self.upper = [i for i in range(len(self.mids)) if self._segment_up(i)]
        self.frames = {}          # angle index -> (frame, horizon)
        self._last_frame = None   # the most recent completed frame while the next one is drawn
        self.ready = False
        self.failed = False
        self._want = 0
        self._stop = False
        self._lock = threading.Lock()
        self.threaded = threaded
        if threaded:
            threading.Thread(target=self._run, name="mkds-voxel", daemon=True).start()
        else:
            self._build()

    def close(self):
        self._stop = True

    # -- the heightmap --------------------------------------------------------------

    def _bounds(self):
        xs = [v for c in self.lines for v in (c[0], c[2])]
        zs = [v for c in self.lines for v in (c[1], c[3])]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        self.centre = ((x0 + x1) / 2, (z0 + z1) / 2)
        self.radius = 0.5 * math.hypot(x1 - x0, z1 - z0)
        # (room for the ground to fade out all the way before the heightmap ends: no edge to see)
        fades = FADE_FROM * 2 * self.half_road + FADE_OVER * self.radius
        pad = max(0.08 * max(x1 - x0, z1 - z0, 400.0), fades * 1.1)
        self.x0, self.z0 = x0 - pad, z0 - pad
        span = max(x1 - x0, z1 - z0) + 2 * pad
        self.cell = span / GRID
        self.gw = int((x1 - x0 + 2 * pad) / self.cell) + 1
        self.gh = int((z1 - z0 + 2 * pad) / self.cell) + 1
        return span

    def _segment_up(self, i):
        n = len(self.mids)
        (ax, az), (bx, bz) = self.mids[i], self.mids[(i + 1) % n]
        y = (self.heights[i] + self.heights[(i + 1) % n]) / 2
        for x, z, reach, low, high, _ in self.decks:
            near = min(math.hypot(ax - x, az - z), math.hypot(bx - x, bz - z),
                       math.hypot((ax + bx) / 2 - x, (az + bz) / 2 - z))
            if near <= 1.5 * reach and abs(y - high) < abs(y - low):
                return True
        return False

    def raised(self, y):
        """A world height as the heightmap has it (from the course's lowest, raised)."""
        return (y - self.base) * self.exaggerate

    def _heightmap(self):
        n, gw, gh, cell = len(self.mids), self.gw, self.gh, self.cell
        lower = [i for i in range(n) if i not in self.upper] or list(range(n))
        # the ground between: a smooth field from the road's heights (coarse, then filled in)
        cw, ch = max(2, gw // 8), max(2, gh // 8)
        samples = [((self.mids[i][0] + self.mids[(i + 1) % n][0]) / 2, (self.mids[i][1] + self.mids[(i + 1) % n][1]) / 2,
                    self.raised((self.heights[i] + self.heights[(i + 1) % n]) / 2)) for i in lower]
        coarse, away = [], []
        low = min(sy for _, _, sy in samples)
        soft = max(1.0, LOWER * (max(sy for _, _, sy in samples) - low))
        for cz in range(ch + 1):
            for cx in range(cw + 1):
                wx, wz = self.x0 + cx * gw * cell / cw, self.z0 + cz * gh * cell / ch
                away.append(min(math.hypot(wx - mx, wz - mz) for mx, mz in self.mids))
                num = den = 0.0
                for sx, sz, sy in samples:
                    # mostly the nearest road, and the lower roads most: the ground's at their level, so a
                    # road raised above it (an overpass, a ramp up to it) stands on an embankment
                    w = 1.0 / ((wx - sx) ** 2 + (wz - sz) ** 2 + (cell * 4) ** 2) ** 1.5 * math.exp(-(sy - low) / soft)
                    num += w * sy
                    den += w
                coarse.append(num / den)
        sink = SINK * self.raised(max(self.heights)) + 6
        hm = [0.0] * (gw * gh)
        fade = [1.0] * (gw * gh)
        fade_from, fade_over = FADE_FROM * 2 * self.half_road, FADE_OVER * self.radius
        for gz in range(gh):
            fz = gz * ch / gh
            iz = min(ch - 1, int(fz))
            tz = fz - iz
            for gx in range(gw):
                fx = gx * cw / gw
                ix = min(cw - 1, int(fx))
                tx = fx - ix
                a = coarse[iz * (cw + 1) + ix] * (1 - tx) + coarse[iz * (cw + 1) + ix + 1] * tx
                b = coarse[(iz + 1) * (cw + 1) + ix] * (1 - tx) + coarse[(iz + 1) * (cw + 1) + ix + 1] * tx
                hm[gz * gw + gx] = a * (1 - tz) + b * tz - sink
                a = away[iz * (cw + 1) + ix] * (1 - tx) + away[iz * (cw + 1) + ix + 1] * tx
                b = away[(iz + 1) * (cw + 1) + ix] * (1 - tx) + away[(iz + 1) * (cw + 1) + ix + 1] * tx
                fade[gz * gw + gx] = max(0.0, min(1.0, 1 - (a * (1 - tz) + b * tz - fade_from) / fade_over))
        # the road at its own height, the lower one where it crosses itself, banks either side
        road = [None] * (gw * gh)
        from_seg = [None] * (gw * gh)       # (the segment each road cell's height is from)
        near = [False] * (gw * gh)          # (the road and its banks: never what hides a racer)
        bank = self.half_road * 2.2
        for i in lower:
            (ax, az), (bx, bz) = self.mids[i], self.mids[(i + 1) % n]
            ya, yb = self.raised(self.heights[i]), self.raised(self.heights[(i + 1) % n])
            gx0 = max(0, int((min(ax, bx) - bank - self.x0) / cell))
            gx1 = min(gw - 1, int((max(ax, bx) + bank - self.x0) / cell) + 1)
            gz0 = max(0, int((min(az, bz) - bank - self.z0) / cell))
            gz1 = min(gh - 1, int((max(az, bz) + bank - self.z0) / cell) + 1)
            for gz in range(gz0, gz1 + 1):
                wz = self.z0 + (gz + 0.5) * cell
                for gx in range(gx0, gx1 + 1):
                    wx = self.x0 + (gx + 0.5) * cell
                    d, t = _segment_distance(wx, wz, ax, az, bx, bz)
                    if d > bank:
                        continue
                    y = ya + (yb - ya) * t
                    k = gz * gw + gx
                    near[k] = True
                    if d <= self.half_road:
                        if road[k] is None or y < road[k]:
                            road[k], from_seg[k] = y, i
                    else:                                       # (the bank: down to the ground)
                        f = (d - self.half_road) / (bank - self.half_road)
                        hm[k] = max(hm[k], y - sink * f - (y - hm[k]) * f * f)
        # the upper roads: raised, on banks down to the ground (but not over the lower road, which
        # runs through them as a cutting), and over the lower road where they cross it, which
        # carries on under them as a tunnel: (its floor, how far off its middle, 0-1)
        lateral = [None] * (gw * gh)
        for i in lower:
            (ax, az), (bx, bz) = self.mids[i], self.mids[(i + 1) % n]
            for k in self._cells_near(ax, az, bx, bz, self.half_road):
                wx, wz = self.x0 + (k % gw + 0.5) * cell, self.z0 + (k // gw + 0.5) * cell
                d = _segment_distance(wx, wz, ax, az, bx, bz)[0]
                if d <= self.half_road and (lateral[k] is None or d / self.half_road < lateral[k]):
                    lateral[k] = d / self.half_road
        over = [None] * (gw * gh)
        over_seg = [None] * (gw * gh)
        for i in (self.upper if len(self.upper) < n else ()):
            (ax, az), (bx, bz) = self.mids[i], self.mids[(i + 1) % n]
            ya, yb = self.raised(self.heights[i]), self.raised(self.heights[(i + 1) % n])
            for k in self._cells_near(ax, az, bx, bz, bank):
                wx, wz = self.x0 + (k % gw + 0.5) * cell, self.z0 + (k // gw + 0.5) * cell
                d, t = _segment_distance(wx, wz, ax, az, bx, bz)
                if d > bank:
                    continue
                y = ya + (yb - ya) * t
                if d <= self.half_road:
                    if over[k] is None or y > over[k]:
                        over[k], over_seg[k] = y, i
                elif road[k] is None:
                    f = (d - self.half_road) / (bank - self.half_road)
                    hm[k] = max(hm[k], y - sink * f - (y - hm[k]) * f * f)
                    near[k] = False                      # (an embankment: it hides what's behind it)
        # a tunnel where an upper road's over a lower one that isn't where it comes down to meet it
        # (a ramp's end, where the two are the same road a segment or two apart, isn't one: no
        # mouth or wall across the road there, just the road)
        tunnel = [None] * (gw * gh)
        deck = DECK_THICK * self.exaggerate
        for k, y in enumerate(over):
            if y is None:
                continue
            apart = (min((from_seg[k] - over_seg[k]) % n, (over_seg[k] - from_seg[k]) % n)
                     if road[k] is not None else 0)
            if road[k] is not None and y > road[k] + deck and apart > JOIN:
                tunnel[k] = (road[k], lateral[k] if lateral[k] is not None else 0.0)
            road[k], near[k] = y, False
        for k, y in enumerate(road):
            if y is not None:
                hm[k] = y
        self.tunnel = tunnel
        flat = min(hm)
        for k, f in enumerate(fade):
            if f <= 0 and road[k] is None:
                hm[k] = flat                     # (faded right out: flat, so nothing at the edge stands up)
        self.hm, self.road, self.near, self.fade = hm, road, near, fade

    def _cells_near(self, ax, az, bx, bz, reach):
        """The cells within `reach` of the segment's bounding box."""
        gw, gh, cell = self.gw, self.gh, self.cell
        gx0 = max(0, int((min(ax, bx) - reach - self.x0) / cell))
        gx1 = min(gw - 1, int((max(ax, bx) + reach - self.x0) / cell) + 1)
        gz0 = max(0, int((min(az, bz) - reach - self.z0) / cell))
        gz1 = min(gh - 1, int((max(az, bz) + reach - self.z0) / cell) + 1)
        return [gz * gw + gx for gz in range(gz0, gz1 + 1) for gx in range(gx0, gx1 + 1)]

    def _colour_map(self):
        """Each cell's colour, in the overlay's flat look: the road ROAD_FILL
        with an outline (ROAD_EDGE) where it meets the ground; the ground the
        nearest of GROUND_COLOURS colours picked from the course's map
        (k-means), cleaned of specks (the colour most of its neighbours
        have), lit or in shade by its slope; then everything blended into the
        board's colour (SKY) by how far it's faded away from the course, the
        faces under each cell (`sides`) too, so the edge melts into it."""
        gw, gh, cell = self.gw, self.gh, self.cell
        n = gw * gh
        src = self.colours
        raw = [None] * n
        for gz in range(gh):
            wz = self.z0 + (gz + 0.5) * cell
            for gx in range(gw):
                k = gz * gw + gx
                if self.fade[k] <= 0 or self.road[k] is not None:
                    continue
                if src:
                    data, sw, sh, mk, mox, moy, mirror = src
                    wx = self.x0 + (gx + 0.5) * cell
                    px, py = int(mox + (-wx if mirror else wx) / mk), int(moy + wz / mk)
                    px, py = min(sw - 1, max(0, px)), min(sh - 1, max(0, py))
                    o = (py * sw + px) * 3
                    raw[k] = (data[o], data[o + 1], data[o + 2])
                else:
                    raw[k] = (58, 92, 64)
        palette = self._palette([c for c, f in zip(raw, self.fade) if c is not None and f >= 0.5])
        nearest = lambda c: min(range(len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(c, palette[i])))  # noqa: E731
        index = [nearest(c) if c is not None else None for c in raw]
        counts = [index.count(i) for i in range(len(palette))]
        common = [c for c, m in zip(palette, counts) if m >= RARE * sum(counts)] or palette
        if len(common) < len(palette):                 # (rare ones, the kerbs' red, say: the nearest common one)
            palette = common
            index = [nearest(c) if c is not None else None for c in raw]
        clean = list(index)
        for gz in range(1, gh - 1):                     # (specks: the colour most of the neighbours have)
            for gx in range(1, gw - 1):
                k = gz * gw + gx
                if index[k] is None:
                    continue
                around = [index[k + d] for d in (-gw - 1, -gw, -gw + 1, -1, 1, gw - 1, gw, gw + 1)]
                best = max(set(around), key=around.count)
                if best is not None and around.count(best) >= 5:
                    clean[k] = best
        # the course's ground into BRIGHT (a black map up, a white one down)
        lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]   # noqa: E731
        used = [palette[i] for i in clean if i is not None]
        mean = sum(lum(c) for c in used) / len(used) if used else BRIGHT[0]
        gain = min(LIFT_MAX, BRIGHT[0] / mean) if mean < BRIGHT[0] else BRIGHT[1] / mean if mean > BRIGHT[1] else 1.0
        lit = [tuple(min(255, int(v * gain)) for v in c) for c in palette]
        shade = [tuple(int(v * SHADE) for v in c) for c in lit]
        cols = [None] * n
        deck = DECK_THICK * self.exaggerate
        for gz in range(gh):
            for gx in range(gw):
                k = gz * gw + gx
                if self.road[k] is not None:
                    # (its edge: any of its eight neighbours off the road, so the outline's joined at the
                    # corners too and doesn't break into dashes on a diagonal)
                    # (a road well under it counts as off it: an overpass keeps its outline over a tunnel, the
                    # road going into one doesn't get one across it at the mouth)
                    edge = any(0 <= gx + dx < gw and 0 <= gz + dz < gh
                               and (self.road[(gz + dz) * gw + gx + dx] is None
                                    or self.road[k] - self.road[(gz + dz) * gw + gx + dx] > deck)
                               for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz)
                    cols[k] = ROAD_EDGE if edge else ROAD_FILL
                elif clean[k] is not None:
                    left = self.hm[k - 1] if gx else self.hm[k]
                    up = self.hm[k - gw] if gz else self.hm[k]
                    cols[k] = shade[clean[k]] if (self.hm[k] - left) + (self.hm[k] - up) < -2 else lit[clean[k]]
                else:
                    cols[k] = SKY                                   # (faded right out)
        # the faces under the road (an overpass's over a tunnel, a ramp's edge): wall, in the nearest
        # ground's colour, not the road's, so no road's seen climbing a wall
        faces = list(cols)
        todo = [k for k in range(n) if self.road[k] is None]
        done = [r is None for r in self.road]
        while todo:                                    # (out from the ground across the road, a cell a step)
            step = []
            for k in todo:
                gx, gz = k % gw, k // gw
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if 0 <= gx + dx < gw and 0 <= gz + dz < gh and not done[k + dz * gw + dx]:
                        done[k + dz * gw + dx] = True
                        faces[k + dz * gw + dx] = faces[k]
                        step.append(k + dz * gw + dx)
            todo = step
        blend = lambda c, f: tuple(int(v * f + b * (1 - f)) for v, b in zip(c, SKY))   # noqa: E731
        self.sides = [blend(tuple(int(v * SIDE) for v in c), f) for c, f in zip(faces, self.fade)]
        self.cols = cols = [blend(c, f) for c, f in zip(cols, self.fade)]
        self._finish_line(cols)                             # (last: no fade, no colour rule on it)
        self.gain = gain

    def _finish_line(self, cols):
        """The start/finish line (checkpoint 0) painted on the road: two rows
        of white and near-black squares (FINISH_SQUARE cells each) across the
        road's fill, its outline carrying on either side, in the ground's
        colours so it's drawn in perspective and hidden by what's in front."""
        x1, z1, x2, z2 = self.lines[0]
        mx, mz = self.mids[0]
        ux, uz = x2 - x1, z2 - z1
        length = math.hypot(ux, uz) or 1.0
        ux, uz = ux / length, uz / length                   # (across the road)
        gw, cell = self.gw, self.cell
        reach = self.half_road
        for k in self._cells_near(mx - ux * reach, mz - uz * reach, mx + ux * reach, mz + uz * reach,
                                  cell * FINISH_CELLS):
            if self.road[k] is None or cols[k] != ROAD_FILL:
                continue                                        # (the road's fill only: its outline stays)
            gx, gz = k % gw, k // gw
            wx, wz = self.x0 + (gx + 0.5) * cell - mx, self.z0 + (gz + 0.5) * cell - mz
            across, along = wx * ux + wz * uz, -wx * uz + wz * ux
            if abs(across) <= reach and abs(along) <= cell * FINISH_CELLS / 2:
                cols[k] = FINISH[(int((across + reach) / cell) // FINISH_SQUARE
                                  + int((along + cell * FINISH_CELLS / 2) / cell) // FINISH_SQUARE) % 2]

    @staticmethod
    def _palette(colours):
        """GROUND_COLOURS colours that stand for `colours` (k-means, from an even sample)."""
        if not colours:
            return [(58, 92, 64)]
        sample = colours[::max(1, len(colours) // 1500)]
        centres = [sample[i * len(sample) // GROUND_COLOURS] for i in range(GROUND_COLOURS)]
        for _ in range(8):
            groups = [[] for _ in centres]
            for c in sample:
                groups[min(range(len(centres)), key=lambda i: sum((a - b) ** 2 for a, b in zip(c, centres[i])))].append(c)
            centres = [tuple(sum(v[j] for v in g) // len(g) for j in range(3)) if g else centres[i]
                       for i, g in enumerate(groups)]
        return list(dict.fromkeys(centres))

    # -- the camera -------------------------------------------------------------------

    def _fit(self):
        """The orbit's distance and the camera's height, so the whole course
        stays in the frame all the way round."""
        pts = []
        for i, (x1, z1, x2, z2) in enumerate(self.lines):
            y = self.raised(self.heights[i])
            pts += [(x1, z1, y), (x2, z2, y)]
        self.fx = self.w / 2 / math.tan(math.radians(FOV / 2))
        r = self.radius
        fitted = []
        for a in range(0, 360, 30):                     # (each angle as close as it fits; eased between)
            for k in [0.8 + 0.05 * i for i in range(200)]:
                self.dists = [r * k] * 12               # (the orbit at this distance, whatever the angle)
                view = self.orbit_view(a, horizon=0.0)
                xs, ys = zip(*(self.project(p, view)[:2] for p in pts))
                if min(xs) >= 4 and max(xs) <= self.w - 4 and max(ys) - min(ys) <= self.h * 0.9:
                    break
            fitted.append(r * k)
        self.dists = fitted
        self.dist = sum(fitted) / len(fitted)

    def distance(self, angle):
        """How far the camera is from the course's middle at `angle`: as
        close as the course fits at every 30 degrees, eased between."""
        a = (angle % 360) / 30
        i = int(a)
        t = (1 - math.cos((a - i) * math.pi)) / 2
        return self.dists[i % 12] * (1 - t) + self.dists[(i + 1) % 12] * t

    def cam_height(self, angle):
        return self.distance(angle) * math.tan(math.radians(ELEVATION)) + self.raised(max(self.heights))

    def camera(self, angle):
        """(x, z, forward x, forward z, right x, right z) for the orbit at `angle` degrees."""
        a = math.radians(angle)
        fx, fz = math.cos(a), math.sin(a)
        cx, cz = self.centre
        d = self.distance(angle)
        return cx - fx * d, cz - fz * d, fx, fz, -fz, fx

    def project(self, p, view):
        """A world point (x, z, raised height) -> (screen x, screen y, depth) in `view`."""
        x, z, y = p
        d = max(1.0, (x - view.x) * view.fx + (z - view.z) * view.fz)
        side = (x - view.x) * view.rx + (z - view.z) * view.rz
        return self.w / 2 + side / d * self.fx, view.horizon + (view.h - y) / d * self.fx, d

    def orbit_view(self, angle, horizon=None):
        """The broadcast camera at `angle`, its horizon putting the course in
        the middle of the frame (or `horizon`)."""
        px, pz, fx, fz, rx, rz = self.camera(angle)
        dist = self.distance(angle)
        view = View(px, pz, fx, fz, rx, rz, self.cam_height(angle), 0.0,
                    max(self.cell, dist - self.radius * 1.4), dist + self.radius * 1.4)
        if horizon is None:
            ys = [self.project((x, z, self.raised(self.heights[i])), view)[1] for i, (x, z) in enumerate(self.mids)]
            horizon = self.h / 2 - (min(ys) + max(ys)) / 2
        return view._replace(horizon=horizon)

    def chase_view(self, x, z, y, heading, rival=None):
        """A camera behind the racer at (x, z), height y, looking along
        `heading` (an angle, radians), far enough back that `rival` ((x, z,
        y) or None) is in the frame too."""
        fx, fz = math.cos(heading), math.sin(heading)
        rx, rz = -fz, fx
        back = CHASE_BACK * 2 * self.half_road
        ry = self.raised(y)
        for _ in range(12):
            h = ry + back * math.tan(math.radians(CHASE_PITCH))
            view = View(x - fx * back, z - fz * back, fx, fz, rx, rz, h, 0.0, self.cell,
                        back + self.radius * 1.6)
            sy = self.project((x, z, ry), view)[1]
            view = view._replace(horizon=self.h * CHASE_AT - sy)
            if rival is None:
                return view
            ox, oy, od = self.project((rival[0], rival[1], self.raised(rival[2])), view)
            if od > 1 and 6 <= ox <= self.w - 6 and 6 <= oy <= self.h - 6:
                return view
            back *= 1.25
        return view

    # -- the frames ---------------------------------------------------------------------

    def _build(self):
        self._heightmap()
        self._colour_map()
        self._fit()
        self.ready = True

    def _run(self):
        try:
            self._build()
            while not self._stop:
                todo = None
                with self._lock:
                    for k in range(AHEAD):
                        i = (self._want + k) % round(360 / ORBIT_STEP)
                        if i not in self.frames:
                            todo = i
                            break
                if todo is None:
                    threading.Event().wait(0.05)
                    continue
                frame = self._render(self.orbit_view(todo * ORBIT_STEP))
                with self._lock:
                    self.frames[todo] = frame
                    self._last_frame = frame
                    self._prune()
        except Exception:
            import logging
            logging.exception("Mario Kart DS: the voxel course couldn't be made")
            self.failed = True

    def _prune(self):
        """Keeps only the frames about to show (AHEAD) and the two before."""
        count = round(360 / ORBIT_STEP)
        keep = {(self._want + k) % count for k in range(-2, AHEAD)}
        for i in [i for i in self.frames if i not in keep]:
            del self.frames[i]

    def frame(self, t_ms):
        """(the orbit's frame for `t_ms`, its View), or the latest completed
        frame while the requested one is being drawn."""
        count = round(360 / ORBIT_STEP)
        i = int(t_ms / ORBIT_MS * count) % count
        if not self.threaded:
            if not self.ready:
                self._build()
            if i not in self.frames:
                self.frames[i] = self._render(self.orbit_view(i * ORBIT_STEP))
                self._last_frame = self.frames[i]
        with self._lock:
            self._want = i
            if not self.threaded:
                self._prune()
            for back in range(count):
                j = (i - back) % count
                if j in self.frames:
                    return self.frames[j]
            return self._last_frame

    def chase_frame(self, view, t_ms):
        """A frame in the chase camera's `view` (live), or the last one when
        the one before was drawn less than 1/CHASE_FPS ago."""
        last = getattr(self, '_chase', None)
        if last and t_ms - last[0] < 1000 / CHASE_FPS and t_ms >= last[0]:
            return last[1]
        frame = self._render(view)
        self._chase = (t_ms, frame)
        return frame

    def _render(self, view):
        """One frame in `view`, voxel space: depth by depth from the
        nearest, each column's ground drawn where it shows above what's
        nearer (a y-buffer). -> (the frame, the view)."""
        w, h = self.w, self.h
        surf = pygame.Surface((w, h))
        surf.fill(SKY)
        horizon = view.horizon
        px, pz, fx, fz, rx, rz = view.x, view.z, view.fx, view.fz, view.rx, view.rz
        hm, cols, gw, gh, cell, x0, z0 = self.hm, self.cols, self.gw, self.gh, self.cell, self.x0, self.z0
        cam_h, focal = view.h, self.fx
        sides, tunnel = self.sides, self.tunnel
        mouth_cap, deck = self.raised(self.base + TUNNEL_MAX) - self.raised(self.base), DECK_THICK * self.exaggerate
        ybuf = [h] * w
        mouths = [None] * w                 # (each column's nearest tunnel mouth: its top and bottom on screen)
        near, far = view.near, view.far
        d = near
        step = cell * 0.7
        fill = surf.fill
        half = w / 2
        while d < far:
            lx, lz = px + fx * d - rx * d * half / focal, pz + fz * d - rz * d * half / focal
            sx, sz = rx * d / focal, rz * d / focal
            gxf, gzf = (lx - x0) / cell, (lz - z0) / cell
            dgx, dgz = sx / cell, sz / cell
            scale = focal / d
            for i in range(w):
                gx, gz = int(gxf), int(gzf)
                gxf += dgx
                gzf += dgz
                if 0 <= gx < gw and 0 <= gz < gh and cols[gz * gw + gx] is not None:
                    k = gz * gw + gx
                    y = int(horizon + (cam_h - hm[k]) * scale)
                    yb = ybuf[i]
                    if y < yb:
                        # the cell's top (what level ground covers this deep on the screen), then, where it
                        # drops more than CLIFF_PX below that (a cliff), its face in the side colour, faded as
                        # its top is; a gentle slope's all top colour, so no stripes
                        flat = (cam_h - hm[k]) * scale * step / d
                        top = min(yb, y + max(1, int(flat) + 1))
                        if yb - top > CLIFF_PX:
                            fill(cols[k], (i, y, 1, max(1, top - y)))
                            fill(sides[k], (i, top, 1, yb - top))
                            mouth = tunnel[k]
                            if mouth:                     # (a tunnel's mouth in the face: dark, under an arch)
                                floor, off = mouth
                                # (squared off: open across the road's whole width, its outline too, the
                                # wall's face only either side of it, not coming down onto the road's edges)
                                arch = min(hm[k] - deck - floor, mouth_cap) * max(0.0, 1 - min(1.0, off) ** ARCH) ** (1 / ARCH)
                                a_top = max(top, int(horizon + (cam_h - floor - arch) * scale))
                                a_bot = min(yb, int(horizon + (cam_h - floor) * scale) + 1)   # (down onto the road: no gap)
                                if a_bot > a_top:                 # (a pixel taller than the arch: it reads)
                                    a_top = max(top, a_top - 1)
                                    fill(TUNNEL, (i, a_top, 1, a_bot - a_top))
                                    if mouths[i] is None:
                                        mouths[i] = (a_top, a_bot)
                        else:
                            fill(cols[k], (i, y, 1, yb - y))
                        ybuf[i] = y
            d += step
            step = min(step * 1.015, cell)
        self._frame_mouths(surf, mouths)
        return surf, view

    @staticmethod
    def _frame_mouths(surf, mouths):
        """The tunnel mouths finished: the dark down onto the road (over
        the row or two of a nearer face that can be left under it), then
        framed in the road's outline colour, a pixel wide, along the top
        (stepping with it, never broken) and down either side, not along
        the bottom where it meets the road."""
        w, h = surf.get_size()
        road = (ROAD_FILL, ROAD_EDGE)
        for i, m in enumerate(mouths):
            if m:
                top, bot = m
                while bot < h and bot - m[1] < 2 and tuple(surf.get_at((i, bot)))[:3] not in road:
                    surf.fill(TUNNEL, (i, bot, 1, 1))
                    bot += 1
                mouths[i] = (top, bot)
        for i, m in enumerate(mouths):
            if not m:
                continue
            top, bot = m
            left = mouths[i - 1] if i else None
            right = mouths[i + 1] if i + 1 < w else None
            rise = min([top] + [n[0] for n in (left, right) if n])   # (up to a neighbour's top: one line)
            surf.fill(ROAD_EDGE, (i, rise - 1, 1, top - rise + 1))
            for side, n in ((i - 1, left), (i + 1, right)):
                if n is None and 0 <= side < w:
                    surf.fill(ROAD_EDGE, (side, top - 1, 1, bot - top + 1))

    # -- each frame ---------------------------------------------------------------------

    def place(self, x, z, y, view):
        """(screen x, y, depth) of a racer at world (x, z), height y (or None: on the ground)."""
        if y is None:
            y = self.ground(x, z) / self.exaggerate + self.base
        return self.project((x, z, self.raised(y)), view)

    def ground(self, x, z):
        """The heightmap's height (raised) under world (x, z)."""
        gx, gz = int((x - self.x0) / self.cell), int((z - self.z0) / self.cell)
        if 0 <= gx < self.gw and 0 <= gz < self.gh:
            return self.hm[gz * self.gw + gx]
        return 0.0

    def hidden(self, x, z, y, view):
        """Whether the ground's in front of a racer: along its column, nearer
        than it, ground that shows above where it's drawn."""
        sx, sy, d = self.place(x, z, y, view)
        i = int(sx)
        if not 0 <= i < self.w:
            return False
        gx, gz = int((x - self.x0) / self.cell), int((z - self.z0) / self.cell)
        if 0 <= gx < self.gw and 0 <= gz < self.gh and y is not None:
            k = gz * self.gw + gx                    # (in a tunnel: under the overpass, whichever way it's seen)
            if self.tunnel[k] and self.raised(y) < self.hm[k] - DECK_THICK * self.exaggerate:
                return True
        px, pz, fx, fz, rx, rz = view.x, view.z, view.fx, view.fz, view.rx, view.rz
        half = self.w / 2
        dd = view.near
        cam_h, horizon = view.h, view.horizon
        while dd < d - self.cell * 2:
            lx = px + fx * dd - rx * dd * half / self.fx + rx * dd / self.fx * i
            lz = pz + fz * dd - rz * dd * half / self.fx + rz * dd / self.fx * i
            gx, gz = int((lx - self.x0) / self.cell), int((lz - self.z0) / self.cell)
            k = gz * self.gw + gx
            if 0 <= gx < self.gw and 0 <= gz < self.gh and not self.near[k] and self.fade[k] >= 0.5:
                if horizon + (cam_h - self.hm[gz * self.gw + gx]) * self.fx / dd < sy - 3:
                    return True                                  # (ground, not road or its banks: a road in front is a deck)
            dd += self.cell * 2
        return False

def map_colours(art, course_file, mirror):
    """The course's map as core/mkds_maps.py places it, for VoxelCourse's
    colours: (RGB bytes, width, height, k, ox, oy, mirror), or None."""
    from core.mkds_maps import ART, MAPS
    if not art or course_file not in MAPS:
        return None
    name, k, ox, oy = MAPS[course_file][:4]
    sheet = art._sheet(ART.format(name))
    if sheet is None:
        return None
    w, h = sheet.get_size()
    return pygame.image.tobytes(sheet, "RGB"), w, h, k, ox, oy, mirror
