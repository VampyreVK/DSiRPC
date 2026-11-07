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
                   (DECKS) the ground keeps the lower road, and the upper one
                   is drawn over it each frame, so racers pass underneath.
                   Frames of the orbit (one each ORBIT_STEP degrees) are drawn
                   column by column, near to far ("voxel space": a column's
                   ground only shows above what's nearer), as they're needed
                   and kept, so after one time round it costs nothing.
    View           a camera: where it is, which way it looks, how high, and
                   where its horizon is on the screen. orbit_view() is the
                   broadcast camera's at an angle; chase_view() one behind a
                   racer, pulled back to keep a rival in the frame too (drawn
                   live, chase_frame(), at most CHASE_FPS a second).

The racers are drawn over a frame by overlay/mkds.py (place(), hidden(),
deck_polygons()), each frame, in the view the frame was drawn in.

It's drawn at twice the canvas's resolution (SCALE) and shown at the window's
(the overlay's blit_hires). Heights are raised (EXAGGERATE) so a course's
hills show at this distance; loops (Rainbow Road) come out as hills.
"""

import math
import threading
from collections import namedtuple

import pygame

from core.mkds_reader import midpoints

SCALE = 2                   # the frames' pixels to the canvas's
GRID = 200                  # the heightmap's cells along its longer side (the course and the fade round it)
ORBIT_MS = 60000            # once round the course in this long
ORBIT_STEP = 1              # degrees between frames of the orbit (a new one every ORBIT_MS / 360)
FOV = 48.0                  # the camera's field of view, across
ELEVATION = 58.0            # how far the camera looks down (degrees, at the course's middle)
EXAGGERATE = 0.16           # the course's hills, at most this much of its width high...
MAX_EXAGGERATE = 3.0        # ... and at most this many times as high as they are
ROAD = 0.21                 # the road's half width, of a checkpoint line's length
SINK = 0.08                 # the ground off the road sits this much of the course's (raised) climb below it, and 6 more
AHEAD = 6                   # frames drawn ahead of the one showing (and only those, and two behind, kept)
SKY = (24, 31, 42)          # behind the course, and what the ground fades into
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
        for cz in range(ch + 1):
            for cx in range(cw + 1):
                wx, wz = self.x0 + cx * gw * cell / cw, self.z0 + cz * gh * cell / ch
                away.append(min(math.hypot(wx - mx, wz - mz) for mx, mz in self.mids))
                num = den = 0.0
                for sx, sz, sy in samples:
                    w = 1.0 / ((wx - sx) ** 2 + (wz - sz) ** 2 + (cell * 4) ** 2) ** 1.5      # (mostly the nearest road)
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
                        road[k] = y if road[k] is None else min(road[k], y)
                    else:                                       # (the bank: down to the ground)
                        f = (d - self.half_road) / (bank - self.half_road)
                        hm[k] = max(hm[k], y - sink * f - (y - hm[k]) * f * f)
        for k, y in enumerate(road):
            if y is not None:
                hm[k] = y
        flat = min(hm)
        for k, f in enumerate(fade):
            if f <= 0 and road[k] is None:
                hm[k] = flat                     # (faded right out: flat, so nothing at the edge stands up)
        self.hm, self.road, self.near, self.fade = hm, road, near, fade

    def _colour_map(self):
        gw, gh, cell = self.gw, self.gh, self.cell
        cols = [None] * (gw * gh)
        src = self.colours
        for gz in range(gh):
            wz = self.z0 + (gz + 0.5) * cell
            for gx in range(gw):
                wx = self.x0 + (gx + 0.5) * cell
                k = gz * gw + gx
                rgb = None
                if src:
                    data, sw, sh, mk, mox, moy, mirror = src
                    px, py = int(mox + (-wx if mirror else wx) / mk), int(moy + wz / mk)
                    px, py = min(sw - 1, max(0, px)), min(sh - 1, max(0, py))
                    o = (py * sw + px) * 3
                    rgb = data[o], data[o + 1], data[o + 2]
                elif self.road[k] is not None:
                    rgb = (150, 158, 172)
                else:
                    rgb = (58, 92, 64)
                # shading: lit from the far left, darker down a slope
                left = self.hm[k - 1] if gx else self.hm[k]
                up = self.hm[k - gw] if gz else self.hm[k]
                shade = max(0.55, min(1.35, 1.0 + (self.hm[k] - left) * 0.035 + (self.hm[k] - up) * 0.02))
                cols[k] = tuple(c * shade * 0.9 for c in rgb)
        # the course's brightness near the road into BRIGHT (a black map up, a white one down), the road
        # at least ROAD_FLOOR; then the fade into the background
        lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]   # noqa: E731
        near = [lum(cols[k]) for k in range(gw * gh) if self.fade[k] > 0.5]
        mean = sum(near) / len(near) if near else BRIGHT[0]
        gain = min(LIFT_MAX, BRIGHT[0] / mean) if mean < BRIGHT[0] else BRIGHT[1] / mean if mean > BRIGHT[1] else 1.0
        for k in range(gw * gh):
            c = [v * gain for v in cols[k]]
            if self.road[k] is not None and lum(c) < ROAD_FLOOR:
                lift = (ROAD_FLOOR - lum(c)) / ROAD_FLOOR
                c = [v + (r - v) * lift for v, r in zip(c, (150, 158, 172))]
            f = self.fade[k]
            cols[k] = tuple(max(0, min(255, int(v * f + sky * (1 - f)))) for v, sky in zip(c, SKY))
        self.cols = cols
        self.gain = gain

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
                        i = (self._want + k) % (360 // ORBIT_STEP)
                        if i not in self.frames:
                            todo = i
                            break
                if todo is None:
                    threading.Event().wait(0.05)
                    continue
                frame = self._render(self.orbit_view(todo * ORBIT_STEP))
                with self._lock:
                    self.frames[todo] = frame
                    self._prune()
        except Exception:
            import logging
            logging.exception("Mario Kart DS: the voxel course couldn't be made")
            self.failed = True

    def _prune(self):
        """Keeps only the frames about to show (AHEAD) and the two before."""
        count = 360 // ORBIT_STEP
        keep = {(self._want + k) % count for k in range(-2, AHEAD)}
        for i in [i for i in self.frames if i not in keep]:
            del self.frames[i]

    def frame(self, t_ms):
        """(the orbit's frame for `t_ms`, its View), or None while it isn't
        drawn yet (or the nearest one drawn before it)."""
        count = 360 // ORBIT_STEP
        i = int(t_ms / ORBIT_MS * count) % count
        if not self.threaded:
            if not self.ready:
                self._build()
            if i not in self.frames:
                self.frames[i] = self._render(self.orbit_view(i * ORBIT_STEP))
        with self._lock:
            self._want = i
            if not self.threaded:
                self._prune()
            for back in range(count):
                j = (i - back) % count
                if j in self.frames:
                    return self.frames[j]
        return None

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
        ybuf = [h] * w
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
                gx, gz = int(gxf + dgx * i), int(gzf + dgz * i)
                if 0 <= gx < gw and 0 <= gz < gh:
                    k = gz * gw + gx
                    y = int(horizon + (cam_h - hm[k]) * scale)
                    if y < ybuf[i]:
                        fill(cols[k], (i, y, 1, ybuf[i] - y))
                        ybuf[i] = y
            d += step
            step *= 1.012
        return surf, view

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
        px, pz, fx, fz, rx, rz = view.x, view.z, view.fx, view.fz, view.rx, view.rz
        half = self.w / 2
        dd = view.near
        cam_h, horizon = view.h, view.horizon
        while dd < d - self.cell * 2:
            lx = px + fx * dd - rx * dd * half / self.fx + rx * dd / self.fx * i
            lz = pz + fz * dd - rz * dd * half / self.fx + rz * dd / self.fx * i
            gx, gz = int((lx - self.x0) / self.cell), int((lz - self.z0) / self.cell)
            if 0 <= gx < self.gw and 0 <= gz < self.gh and not self.near[gz * self.gw + gx]:
                if horizon + (cam_h - self.hm[gz * self.gw + gx]) * self.fx / dd < sy - 6:
                    return True                                  # (ground, not road or its banks: a road in front is a deck)
            dd += self.cell * 2
        return False

    def deck_polygons(self, view):
        """The upper decks' road, as screen polygons (far first) with a colour each."""
        n = len(self.mids)
        out = []
        for i in self.upper:
            j = (i + 1) % n
            quad = []
            for k, side in ((i, 0), (i, 1), (j, 1), (j, 0)):
                x1, z1, x2, z2 = self.lines[k]
                mx, mz = self.mids[k]
                ex, ez = ((x1, z1) if side == 0 else (x2, z2))
                f = ROAD * 2
                quad.append(self.project((mx + (ex - mx) * f, mz + (ez - mz) * f, self.raised(self.heights[k])),
                                         view))
            if min(q[2] for q in quad) <= 1:
                continue                                         # (behind the camera)
            depth = sum(q[2] for q in quad) / 4
            gx = int(((self.mids[i][0] + self.mids[j][0]) / 2 - self.x0) / self.cell)
            gz = int(((self.mids[i][1] + self.mids[j][1]) / 2 - self.z0) / self.cell)
            colour = self.cols[gz * self.gw + gx] if 0 <= gx < self.gw and 0 <= gz < self.gh else (150, 158, 172)
            out.append((depth, [(q[0], q[1]) for q in quad], colour))
        out.sort(key=lambda o: -o[0])
        return out


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
