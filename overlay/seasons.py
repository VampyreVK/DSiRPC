"""
seasons.py - the seasons on Pokemon Black and White's main view
(overlay/unova.py). Unova changes season every month, and the view follows
it, lit by the game's own clock:

    spring    cherry petals flutter across in gusts, some settling on the
              panels for a while; a soft pink light from above
    summer    by day, slow sun rays and drifting motes of light; at night,
              fireflies wandering and blinking
    autumn    leaves in four colours tumble down, some coming to rest on
              the panels' tops; an amber glow from below
    winter    snow in three layers of depth, piling up into caps along the
              panels' tops (and melting when winter ends); an aurora on
              winter nights

    always    the light of the time of day (morning, day, evening, night),
              stars twinkling at night, an animated season icon for the
              header, and a flourish (a banner and a burst) when the season
              turns

The party panels cover nearly all of the view, so everything plays over
them: particles in two depths (far ones dimmer and slower), small and few
enough to keep the text readable, decorations on the panels' tops and the
header's and footer's edges (snow caps, icicles, settled petals and
leaves), and the light of the season and time of day as a gentle wash over
the whole view. In chroma-key mode the see-through light and aurora are
left out (they'd tint the key colour); the rest stays.

    fx = SeasonFX()
    fx.update(season, when, t_ms, panels)     # panels: [(key, rect), ...]
    fx.draw_header(canvas, header_h, t_ms)    # behind the header's text: stars at night
    fx.draw_panels(canvas, panels)            # after the panels: caps, settled leaves
    fx.draw_edges(canvas, header_h, footer_y, t_ms)   # icicles, drifts
    fx.draw_front(canvas, t_ms, chroma)       # last: particles, light
    fx.icon(canvas, x, y, t_ms)               # the header's season icon
"""

import math
import random

import pygame

W, H = 256, 192
NAMES = {'spring': 'Spring', 'summer': 'Summer', 'autumn': 'Autumn', 'winter': 'Winter'}

# Particle shapes ('#' main colour, 'o' its shade), by kind; several frames
# make petals and leaves spin as they fall.
PETAL = [["##", "#o"], [".#", "#o", "#."], ["##o"], ["o#", "##"]]
LEAF = [[".#.", "###", "#o#", ".o."], ["..##", ".###", "##o.", "#..."], ["#.#.", "####", ".o#."],
        ["#...", "##o.", ".###", "..##"]]
FLAKE_BIG = [".#.", "#o#", ".#."]
FLAKE_STAR = ["#.#", ".o.", "#.#"]

PETAL_COLORS = [((255, 184, 210), (232, 128, 168)), ((255, 214, 228), (240, 160, 190)), ((248, 160, 196), (212, 104, 150))]
LEAF_COLORS = [((232, 112, 40), (176, 72, 24)), ((216, 56, 40), (150, 32, 24)), ((240, 184, 48), (190, 132, 24)),
               ((168, 104, 56), (120, 72, 36))]
SNOW = ((250, 252, 255), (200, 216, 240))

# The light per season and time of day: (colour, alpha, where) gradients.
LIGHT = {
    'spring': [((255, 150, 200), 40, 'top')],
    'summer': [((255, 230, 150), 44, 'corner')],
    'autumn': [((255, 140, 40), 46, 'bottom'), ((255, 190, 90), 18, 'top')],
    'winter': [((150, 200, 255), 16, 'top'), ((214, 234, 255), 54, 'edges')],   # frost on the window, a clear middle
}
TIME_LIGHT = {
    'morning': [((255, 220, 170), 30, 'top')],
    'day': [],
    'evening': [((255, 110, 50), 48, 'bottom'), ((110, 50, 140), 30, 'top')],
    'night': [((8, 14, 52), 58, 'all'), ((40, 60, 140), 26, 'top')],
}


def key_hash(key):
    return sum(map(ord, str(key))) * 13


class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'phase', 'spin', 'frame', 'color', 'layer', 'kind', 'size', 'life')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class SeasonFX:
    MAX_PARTICLES = 90
    CAP_MAX = 4.0           # snow cap height, pixels
    REST_MS = 6000          # how long a petal or leaf stays on a panel

    def __init__(self, toast=None):
        """toast(text, sparkly): announces a change of season."""
        self.toast = toast
        self.rng = random.Random(9)
        self.parts = []
        self.resting = []          # [x, y, kind, frame, colors, until]
        self.caps = {}             # panel key -> [height per x]
        self.season = None
        self.when = 'day'
        self.last_t = None
        self.spawn_debt = 0.0
        self.gust_until = 0
        self.gust_dir = 1
        self.stars = [(self.rng.randrange(W), self.rng.randrange(1, 12), self.rng.random() * 6.28) for _ in range(30)]
        self.flies = [[self.rng.uniform(10, W - 10), self.rng.uniform(30, 150), self.rng.random() * 6.28]
                      for _ in range(14)]
        self._light_cache = {}
        self.footer_y = H - 30
        self.drift = [0.0] * (W // 4 + 1)       # what's piled on the footer's edge, per 4 px
        self.icicles = [(x, self.rng.randrange(1, 5)) for x in range(3, W, 7)]
        # how high snow settles along an edge: smooth lumps, never flat
        self.lump = [0.35 + 0.65 * (0.5 + 0.5 * math.sin(i / 3.1) * math.sin(i / 7.7 + 1)) for i in range(97)]

    # -- update ----------------------------------------------------------------

    def update(self, season, when, t_ms, panels):
        if season not in NAMES:
            season = 'spring'
        dt = 0.033 if self.last_t is None else max(0.0, min(0.1, (t_ms - self.last_t) / 1000.0))
        self.last_t = t_ms
        if self.season is not None and season != self.season:
            if self.toast:
                self.toast(f"{NAMES[season]} has come to Unova!", True)
            self._burst(season)
        self.season, self.when = season, when

        # gusts now and then: everything drifts faster, sideways
        if t_ms > self.gust_until + 9000 and self.rng.random() < dt * 0.08 and season in ('spring', 'autumn', 'winter'):
            self.gust_until = t_ms + 2200
            self.gust_dir = self.rng.choice((-1, 1)) if season == 'winter' else 1
        gust = 1.0 if t_ms < self.gust_until else 0.0

        rate = {'spring': 12.0, 'summer': 8.0 if when != 'night' else 0.0, 'autumn': 7.0, 'winter': 18.0}[season]
        self.spawn_debt += rate * dt
        while self.spawn_debt >= 1 and len(self.parts) < self.MAX_PARTICLES:
            self.spawn_debt -= 1
            self.parts.append(self._spawn(season))
        self.spawn_debt = min(self.spawn_debt, 3)

        alive = []
        tops = [(pygame.Rect(r), key) for key, r in panels]
        for p in self.parts:
            p.phase += dt * (1.5 + p.size * 0.2)
            sway = math.sin(p.phase) * (14 if p.kind in ('petal', 'leaf') else 4)
            p.x += (p.vx + sway * 0.6 + gust * self.gust_dir * (40 if p.layer else 26)) * dt
            p.y += p.vy * dt
            if p.kind in ('petal', 'leaf'):
                p.spin += dt * (3 + abs(p.vx) * 0.05 + gust * 6)
                p.frame = int(p.spin) % 4
            if p.kind == 'mote':
                p.life -= dt
            landed = False
            if p.layer == 1 and p.kind in ('petal', 'leaf', 'snow'):
                for r, key in tops:
                    if r.left + 3 <= p.x < r.right - 3 and r.top - 2 <= p.y <= r.top + 1 and self.rng.random() < 0.18:
                        landed = True
                        if p.kind == 'snow':
                            self._add_snow(key, r, int(p.x) - r.left)
                        else:
                            self.resting.append([p.x, r.top - 1, p.kind, p.frame, p.color, t_ms + self.REST_MS])
                        break
            if not landed and -12 < p.x < W + 12 and -12 < p.y < H + 6 and (p.kind != 'mote' or p.life > 0):
                alive.append(p)
        self.parts = alive
        self.resting = [r for r in self.resting if r[5] > t_ms][-24:]
        # the footer's top edge collects a drift of whatever falls
        for p in self.parts:
            if p.layer == 1 and p.kind in ('petal', 'leaf', 'snow') and self.footer_y - 2 <= p.y <= self.footer_y:
                i = int(p.x) // 4
                if 0 <= i < len(self.drift) and self.rng.random() < 0.05:
                    self.drift[i] = min(3.0, self.drift[i] + 0.6)
        melt = 0.02 if season in ('winter', 'autumn', 'spring') else 0.3
        self.drift = [max(0.0, v - dt * melt) for v in self.drift]

        # snow caps: grow a little all winter, melt the rest of the year
        for key, r in panels:
            caps = self.caps.setdefault(key, [0.0] * pygame.Rect(r).w)
            if len(caps) != pygame.Rect(r).w:
                caps[:] = [0.0] * pygame.Rect(r).w
            if season == 'winter':
                for _ in range(2):
                    if self.rng.random() < dt * 10:
                        self._add_snow(key, pygame.Rect(r), self.rng.randrange(len(caps)), 0.7)
            else:
                for i in range(len(caps)):
                    caps[i] = max(0.0, caps[i] - dt * 0.6)

        for f in self.flies:
            f[2] += dt * 0.7
            f[0] = (f[0] + math.cos(f[2] * 1.3) * 10 * dt) % W
            f[1] = 24 + (f[1] - 24 + math.sin(f[2]) * 8 * dt) % 130

    def _spawn(self, season, x=None, y=None):
        rng = self.rng
        layer = 1 if rng.random() < 0.7 else 0
        if season == 'spring':
            kind, colors = 'petal', rng.choice(PETAL_COLORS)
            vx, vy = rng.uniform(8, 20), rng.uniform(10, 20)
        elif season == 'autumn':
            kind, colors = 'leaf', rng.choice(LEAF_COLORS)
            vx, vy = rng.uniform(-6, 12), rng.uniform(14, 26)
        elif season == 'winter':
            kind, colors = 'snow', SNOW
            depth = rng.random()
            layer = 1 if depth > 0.35 else 0
            vx, vy = rng.uniform(-4, 4), 10 + depth * 18
        else:
            kind, colors = 'mote', ((255, 250, 210), (255, 220, 140))
            vx, vy = rng.uniform(-4, 4), rng.uniform(-8, -3)
        if layer == 0:
            vx, vy = vx * 0.6, vy * 0.6
        size = (2 if layer else 1) if kind == 'snow' else (1 if layer else 2)
        if kind == 'snow' and layer == 1 and rng.random() < 0.3:
            size = 3
        if x is None:
            if kind == 'mote':
                x, y = rng.uniform(0, W), rng.uniform(40, H)
            elif rng.random() < 0.7:
                x, y = rng.uniform(-10, W), -6
            else:
                x, y = -8, rng.uniform(0, H * 0.6)
        return Particle(x=x, y=y, vx=vx, vy=vy, phase=rng.random() * 6.28, spin=rng.random() * 4, frame=0,
                        color=colors, layer=layer, kind=kind, size=size, life=rng.uniform(3, 7))

    def _burst(self, season):
        for _ in range(40):
            p = self._spawn(season, self.rng.uniform(0, W), self.rng.uniform(-10, H * 0.7))
            p.vx *= 2.5
            self.parts.append(p)

    def _add_snow(self, key, rect, x, amount=1.0):
        caps = self.caps.setdefault(key, [0.0] * rect.w)
        for dx in range(-3, 4):
            i = x + dx
            if 0 <= i < len(caps):
                caps[i] = min(self.CAP_MAX, caps[i] + amount * (1 - abs(dx) / 4) * 0.5)

    # -- drawing ---------------------------------------------------------------

    def draw_header(self, canvas, header_h, t_ms):
        """Behind the header's text: the summer sun's glow by day, an aurora
        on winter nights, stars twinkling every night."""
        if self.season == 'summer' and self.when in ('day', 'morning'):
            glow = pygame.Surface((120, header_h), pygame.SRCALPHA)
            for r in range(60, 0, -3):
                pygame.draw.circle(glow, (255, 200, 80, int(90 * (1 - r / 60) ** 1.3)), (118, 2), r)
            canvas.blit(glow, (W - 120, 0))
        if self.season == 'winter' and self.when == 'night':
            t = t_ms / 1000.0
            band = pygame.Surface((W, header_h), pygame.SRCALPHA)
            for x in range(W):
                y = 4 + math.sin(x / 23 + t * 0.6) * 2.5 + math.sin(x / 9 + t * 1.3)
                hue = 0.5 + 0.5 * math.sin(x / 60 + t * 0.3)
                col = (int(80 + 120 * (1 - hue)), int(255 - 90 * (1 - hue)), int(170 + 85 * (1 - hue)))
                for k in range(7):
                    yy = int(y) + k
                    if 0 <= yy < header_h - 1:
                        band.set_at((x, yy), (*col, int(110 * (1 - k / 7))))
            canvas.blit(band, (0, 0))
        if self.when != 'night':
            return
        for x, y, ph in self.stars:
            b = 0.5 + 0.5 * math.sin(t_ms / 700 + ph)
            if b > 0.3 and y < header_h - 1:
                c = int(120 + 135 * b)
                canvas.set_at((x, y), (c, c, min(255, c + 30)))

    def draw_edges(self, canvas, header_h, footer_y, t_ms):
        """Icicles under the header in winter; the drift on the footer's
        top edge (snow, petals or leaves, by season)."""
        self.footer_y = footer_y
        if self.season == 'winter':
            for x, length in self.icicles:
                for k in range(length):
                    canvas.set_at((x, header_h + k), (220, 240, 255) if k < length - 1 else (160, 200, 240))
                if (t_ms // 90 + x) % 97 == 0:  # a glint
                    canvas.set_at((x, header_h + length), (255, 255, 255))
        colors = {'winter': SNOW, 'spring': PETAL_COLORS[0], 'autumn': LEAF_COLORS[0], 'summer': SNOW}[self.season or 'spring']
        for i, v in enumerate(self.drift):
            hh = int(v + 0.5)
            if hh:
                x = i * 4
                pygame.draw.rect(canvas, colors[1], (x, footer_y - hh + 1, 4, hh))
                pygame.draw.line(canvas, colors[0], (x, footer_y - hh + 1), (x + 3, footer_y - hh + 1))
                if self.season == 'autumn':  # a leaf's colour now and then
                    canvas.set_at((x + 1, footer_y - hh + 1), LEAF_COLORS[i % 4][0])

    def draw_panels(self, canvas, panels):
        for key, r in panels:
            r = pygame.Rect(r)
            caps = self.caps.get(key)
            if caps and max(caps) >= 0.5:
                inset = 9 if r.h == 46 else 3   # the flat part of the top edge (the corners are cut)
                prev = 0
                for i in range(inset, len(caps) - inset):
                    hh = int(caps[i] * self.lump[(i + key_hash(key)) % len(self.lump)] + 0.5)
                    if hh:
                        x = r.left + i
                        pygame.draw.line(canvas, SNOW[0], (x, r.top - hh + 1), (x, r.top + 1))
                        canvas.set_at((x, r.top + 1), SNOW[1])
                        if hh > prev:  # a light top on each lump
                            canvas.set_at((x, r.top - hh + 1), (255, 255, 255))
                    prev = hh
        for x, y, kind, frame, colors, _ in self.resting:
            shape = (PETAL if kind == 'petal' else LEAF)[frame % 4]
            self._shape(canvas, shape, int(x), int(y) - len(shape) + 1, colors)

    def draw_front(self, canvas, t_ms, chroma=False):
        """The particles, far then near, then the light over everything."""
        if self.season == 'summer' and self.when == 'night':
            self._fireflies(canvas, t_ms, chroma)
        for layer in (0, 1):
            for p in self.parts:
                if p.layer == layer:
                    self._draw_particle(canvas, p, dim=layer == 0)
        if chroma:
            return
        canvas.blit(self._light(self.season, self.when), (0, 0))
        if self.season == 'summer' and self.when in ('day', 'morning'):
            self._rays(canvas, t_ms)
        if self.season == 'winter' and self.when == 'night':
            self._aurora(canvas, t_ms)

    def icon(self, canvas, x, y, t_ms):
        """The season's icon (9x9) for the header, animated."""
        s = self.season or 'spring'
        cx, cy = x + 4, y + 4
        if s == 'spring':  # a blossom gently turning
            a0 = t_ms / 900
            for k in range(5):
                a = a0 + k * 2 * math.pi / 5
                px, py = cx + round(math.cos(a) * 2.6), cy + round(math.sin(a) * 2.6)
                pygame.draw.circle(canvas, (255, 176, 206), (px, py), 2)
            pygame.draw.circle(canvas, (248, 232, 120), (cx, cy), 1)
        elif s == 'summer':  # a sun, its rays turning
            a0 = t_ms / 1400
            for k in range(8):
                a = a0 + k * math.pi / 4
                pygame.draw.line(canvas, (255, 200, 60), (cx + round(math.cos(a) * 3), cy + round(math.sin(a) * 3)),
                                 (cx + round(math.cos(a) * 4.5), cy + round(math.sin(a) * 4.5)))
            pygame.draw.circle(canvas, (255, 228, 96), (cx, cy), 2)
        elif s == 'autumn':  # a leaf swaying
            frame = int(t_ms / 400) % 2
            shape = LEAF[0] if frame == 0 else LEAF[2]
            self._shape(canvas, shape, cx - 1 + int(math.sin(t_ms / 500) * 1.5), cy - 2, LEAF_COLORS[0])
        else:  # a snowflake, twinkling
            c = (200, 230, 255) if (t_ms // 300) % 5 else (255, 255, 255)
            for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
                pygame.draw.line(canvas, c, (cx - dx * 3, cy - dy * 3), (cx + dx * 3, cy + dy * 3))
            canvas.set_at((cx, cy), (255, 255, 255))

    # -- parts ---------------------------------------------------------------------

    def _draw_particle(self, canvas, p, dim=False):
        colors = p.color
        if dim:  # out of focus, behind the panels
            colors = tuple(tuple(int(v * 0.55 + 20) for v in c) for c in colors)
        x, y = int(p.x), int(p.y)
        if p.kind == 'snow':
            if p.size == 3:
                self._shape(canvas, FLAKE_STAR if (int(p.phase) % 2) else FLAKE_BIG, x - 1, y - 1, colors)
            elif p.size == 2:
                canvas.set_at((x, y), colors[0])
                canvas.set_at((x + 1, y), colors[1])
                canvas.set_at((x, y + 1), colors[1])
            else:
                canvas.set_at((x, y), colors[1])
        elif p.kind == 'mote':
            b = max(0.0, min(1.0, p.life / 2)) * (0.6 + 0.4 * math.sin(p.phase * 3))
            c = tuple(int(v * b) for v in colors[0])
            canvas.set_at((x, y), c)
            if p.layer:
                canvas.set_at((x + 1, y), tuple(v // 2 for v in c))
        else:
            shape = (PETAL if p.kind == 'petal' else LEAF)[p.frame]
            if p.size == 2 and p.kind == 'petal':
                shape = [row.replace('o', '#') for row in shape[:2]]
            self._shape(canvas, shape, x, y, colors)

    @staticmethod
    def _shape(canvas, shape, x, y, colors):
        for yy, row in enumerate(shape):
            for xx, ch in enumerate(row):
                if ch == '#':
                    canvas.set_at((x + xx, y + yy), colors[0])
                elif ch == 'o':
                    canvas.set_at((x + xx, y + yy), colors[1])

    def _light(self, season, when):
        key = (season, when)
        surf = self._light_cache.get(key)
        if surf is None:
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            lights = LIGHT.get(season, [])
            if when == 'night':  # no sun at night
                lights = [lt for lt in lights if lt[2] != 'corner']
            for color, alpha, where in lights + TIME_LIGHT.get(when, []):
                if season == 'winter' and when == 'night':
                    alpha = alpha * 3 // 5  # the snow keeps winter nights bright (and the aurora's enough)
                self._gradient(surf, color, alpha, where)
            self._light_cache[key] = surf
        return surf

    @staticmethod
    def _gradient(surf, color, alpha, where):
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        if where == 'all':
            layer.fill((*color, alpha))
        elif where in ('top', 'bottom'):
            for i in range(90):
                a = int(alpha * (1 - i / 90) ** 1.6)
                y = i if where == 'top' else H - 1 - i
                pygame.draw.line(layer, (*color, a), (0, y), (W, y))
        elif where == 'edges':  # a frosty border, thickest in the corners
            depth = 30
            for i in range(depth):
                a = int(alpha * (1 - i / depth) ** 2.2)
                pygame.draw.rect(layer, (*color, a), (i, i, W - 2 * i, H - 2 * i), 1)
            for cx, cy in ((0, 0), (W, 0), (0, H), (W, H)):
                for r in range(40, 0, -3):
                    pygame.draw.circle(layer, (*color, int(alpha * 0.22 * (1 - r / 40) ** 1.5)), (cx, cy), r)
        else:  # corner: a glow from the top right
            for rr in range(150, 0, -6):
                a = int(alpha * (1 - rr / 150) ** 1.4)
                pygame.draw.circle(layer, (*color, a), (W - 10, -10), rr)
        surf.blit(layer, (0, 0))

    def _rays(self, canvas, t_ms):
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        ox, oy = W + 10, -20
        for k in range(5):
            a = math.radians(115 + k * 13 + math.sin(t_ms / 4000 + k) * 3)
            w = math.radians(4 + (k % 2) * 3)
            pts = [(ox, oy), (ox + math.cos(a - w) * 330, oy + math.sin(a - w) * 330),
                   (ox + math.cos(a + w) * 330, oy + math.sin(a + w) * 330)]
            pygame.draw.polygon(layer, (255, 244, 200, 26 + (k % 2) * 10), pts)
        canvas.blit(layer, (0, 0))

    def _aurora(self, canvas, t_ms):
        layer = pygame.Surface((W, 70), pygame.SRCALPHA)
        t = t_ms / 1000.0
        for band, (col, base, amp) in enumerate((((80, 255, 170), 22, 8), ((120, 160, 255), 34, 6),
                                                 ((200, 120, 255), 16, 5))):
            for x in range(0, W, 2):
                y = base + math.sin(x / 34 + t * (0.4 + band * 0.15)) * amp + math.sin(x / 13 + t) * 2
                for k in range(14):
                    a = int(64 * (1 - k / 14) * (0.6 + 0.4 * math.sin(x / 50 + t * 0.7 + band)))
                    if a > 0:
                        layer.set_at((x, int(y) + k), (*col, a))
                        layer.set_at((x + 1, int(y) + k), (*col, a))
        canvas.blit(layer, (0, 10))

    def _fireflies(self, canvas, t_ms, chroma):
        for i, (x, y, ph) in enumerate(self.flies):
            on = math.sin(t_ms / 480 + i * 1.7) > -0.2
            if not on:
                continue
            if not chroma:
                glow = pygame.Surface((9, 9), pygame.SRCALPHA)
                pygame.draw.circle(glow, (200, 255, 120, 60), (4, 4), 4)
                canvas.blit(glow, (int(x) - 4, int(y) - 4))
            canvas.set_at((int(x), int(y)), (230, 255, 150))
