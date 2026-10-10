"""
unova_backdrop.py - Pokemon Black and White's battle background and
platforms ("turfs"), drawn in code on top of the Diamond and Pearl skies in
Assets/PokemonBlackUI (overlay/unova_art.py), with the detail Black and
White's own backgrounds have:

    ground       below the sky's horizon, its own colours stretched toward
                 the viewer in blocks that grow with depth (a 3D floor), with
                 faint streaks fanning out from a point above the horizon
                 and soft bands for depth
    skyline      a distant silhouette per place: treelines (field, forest),
                 snowy ridges (mountain, snow), islands (ocean), stalactites
                 (cave), a wall with windows and a railing (indoors)
    light        a haze band along the horizon, sun shafts (day and
                 evening), a vignette, and drifting particles (pollen, or
                 fireflies at night; snowflakes; bubbles; cave dust)
    turfs        platforms with thickness, a radial glow and a shadow, and
                 a rim dressed per terrain: grass tufts, a snow ring, water
                 caustics, sand ripples, rocks, an indoor ring line; tinted
                 for evening and night

The still parts are drawn once per (sky, time of day) and turf size, and
cached; particles move every frame. Random details use fixed seeds, so a
place always looks the same.
"""

import math
import random

import pygame

W, H = 256, 192
BOX_TOP = 146                     # the battle view's message band

# Where the platforms sit (centre, size), like Black and White's: the far
# one right of centre, the near one big and mostly under the message band.
FAR_TURF = (186, 96, 132, 34)
NEAR_TURF = (72, 166, 220, 70)
FOE_FEET = (186, 101)
YOUR_FEET = (70, 154)

SKYLINE = {'field': 'trees', 'forest': 'trees', 'ocean': 'islands', 'mountain': 'ridges', 'snow': 'ridges',
           'cave': 'ceiling', 'indoor': 'wall'}
PARTICLES = {'snow': 'snow', 'ocean': 'bubbles', 'cave': 'dust', 'indoor': None}

# Turf colours per terrain: rim, disc, its lit middle, and the decoration.
TURF = {
    'grass': dict(rim=(56, 120, 48), disc=(84, 168, 72), light=(132, 208, 104),
                  deco=[(40, 96, 40), (104, 184, 80), (150, 220, 110)]),
    'field': dict(rim=(150, 112, 64), disc=(196, 160, 104), light=(228, 200, 144), deco=[(120, 88, 48), (172, 136, 84)]),
    'sand': dict(rim=(200, 160, 88), disc=(232, 200, 128), light=(248, 228, 168), deco=[(176, 136, 72), (212, 176, 104)]),
    'snow': dict(rim=(200, 212, 232), disc=(168, 176, 196), light=(224, 228, 240), deco=[(248, 248, 252), (184, 196, 220)]),
    'water': dict(rim=(136, 216, 240), disc=(40, 120, 200), light=(72, 160, 232), deco=[(24, 88, 168), (160, 228, 248)]),
    'cave': dict(rim=(112, 88, 64), disc=(176, 140, 100), light=(212, 180, 136),
                 deco=[(120, 112, 104), (156, 148, 136), (88, 80, 72)]),
    'indoor': dict(rim=(132, 136, 148), disc=(184, 188, 200), light=(220, 224, 232), deco=[(96, 100, 112), (248, 208, 72)]),
}
# How the turfs change with the time of day: (multiply, add).
TIME_TINT = {'day': ((1, 1, 1), (0, 0, 0)), 'morning': ((1, 1, 0.96), (6, 4, 0)),
             'evening': ((1.0, 0.82, 0.70), (24, 6, 0)), 'night': ((0.50, 0.56, 0.86), (0, 0, 12))}
HAZE = {'day': (255, 255, 255), 'morning': (255, 244, 224), 'evening': (255, 214, 160), 'night': (150, 170, 230)}


def _tint(c, when):
    mul, add = TIME_TINT.get(when, TIME_TINT['day'])
    return tuple(max(0, min(255, int(v * m + a))) for v, m, a in zip(c, mul, add))


def _lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def horizon_row(sky):
    """The row where a sky tile's colour changes most: its horizon."""
    best, row = -1, 56
    for y in range(30, min(100, sky.get_height() - 4)):
        a = [sky.get_at((x, y - 3)) for x in range(0, W, 16)]
        b = [sky.get_at((x, y + 3)) for x in range(0, W, 16)]
        d = sum(abs(p[i] - q[i]) for p, q in zip(a, b) for i in range(3))
        if d > best:
            best, row = d, y
    return row


class UnovaBackdrop:
    def __init__(self, art):
        self.art = art
        self._still = {}
        self._turfs = {}

    # -- public --------------------------------------------------------------

    def draw(self, canvas, sky_kind, when, t_ms, particles=True):
        """The background for a battle under `sky_kind` skies at `when`."""
        still = self._still.get((sky_kind, when))
        if still is None:
            still = self._make_still(sky_kind, when)
            if not self.art.pending():  # not the plain stand-in while the sheet downloads
                self._still[(sky_kind, when)] = still
        canvas.blit(still, (0, 0))
        if particles:
            self._particles(canvas, PARTICLES.get(sky_kind, 'pollen'), when, t_ms)

    def draw_turfs(self, canvas, ground, when, far_dx, near_dx):
        """Both platforms, slid by the intro's offsets. Returns where each
        side's Pokemon stand (feet): {'foe': (x, y), 'you': (x, y)}."""
        for (cx, cy, w, h), dx in ((FAR_TURF, far_dx), (NEAR_TURF, near_dx)):
            img = self._turf(ground, when, w, h)
            canvas.blit(img, (cx + dx - img.get_width() // 2, cy - img.get_height() // 2))
        return {'foe': (FOE_FEET[0] + far_dx, FOE_FEET[1]), 'you': (YOUR_FEET[0] + near_dx, YOUR_FEET[1])}

    # -- the still background ----------------------------------------------------

    def _make_still(self, sky_kind, when):
        surf = pygame.Surface((W, H))
        sky = self.art.sky(sky_kind, when)
        if sky is None:
            surf.fill((24, 32, 48))
            return surf
        surf.blit(sky, (0, 0))
        for y in range(sky.get_height(), H):  # down to the bottom
            surf.blit(sky, (0, y), (0, sky.get_height() - 1, W, 1))
        hy = horizon_row(sky)
        self._ground(surf, sky, hy)
        self._bands(surf, hy)
        self._skyline(surf, SKYLINE.get(sky_kind), hy, sky, when)
        self._haze(surf, hy, when)
        self._shafts(surf, when, sky_kind)
        self._vignette(surf)
        return surf

    def _ground(self, surf, sky, hy):
        r = random.Random(1)
        bottom = BOX_TOP + 30
        for y in range(hy, bottom):
            depth = (y - hy) / max(1, bottom - hy)
            src_y = min(sky.get_height() - 1, hy + int((y - hy) * 0.55))
            block = 4 + int(depth * 40)  # texels grow toward the viewer
            x = -r.randrange(block)
            while x < W:
                c = sky.get_at((max(0, min(W - 1, x + block // 2)), src_y))
                k = r.choice((-3, -1, 0, 0, 0, 1, 2))
                pygame.draw.line(surf, tuple(max(0, min(255, v + k)) for v in c[:3]), (x, y), (x + block, y))
                x += block
        # streaks fanning out from a point above the horizon
        vx, vy = W // 2 + 10, hy - 60
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        bx = -420
        while bx < W + 420:
            wid = r.randrange(6, 26)
            col = (255, 255, 255, r.randrange(6, 13)) if r.random() < 0.55 else (0, 0, 0, r.randrange(8, 15))
            pygame.draw.polygon(layer, col, [(vx, vy), (bx, H + 40), (bx + wid, H + 40)])
            bx += wid + r.randrange(10, 46)
        clip = surf.get_clip()
        surf.set_clip((0, hy, W, H - hy))
        surf.blit(layer, (0, 0))
        surf.set_clip(clip)

    def _bands(self, surf, hy):
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        y, h, k = hy, 2, 0
        while y < BOX_TOP:
            pygame.draw.rect(layer, (0, 0, 0, 14) if k % 2 else (255, 255, 255, 8), (0, y, W, h))
            y += h
            h = int(h * 1.45) + 1
            k += 1
        surf.blit(layer, (0, 0))

    def _skyline(self, surf, kind, hy, sky, when):
        r = random.Random(3)
        base = sky.get_at((W // 2, max(0, hy - 2)))[:3]
        far = _lerp(base, (40, 60, 70), 0.35)
        near = _lerp(base, (20, 40, 40), 0.6)
        if kind == 'trees':
            for color, top, step in ((far, hy - 12, 7), (near, hy - 7, 9)):
                x = -r.randrange(step)
                while x < W:
                    h, rad = r.randrange(4, 11), r.randrange(4, 8)
                    pygame.draw.circle(surf, color, (x, top + 12 - h), rad)
                    pygame.draw.rect(surf, color, (x - rad, top + 12 - h, rad * 2, h + 2))
                    x += step
                pygame.draw.rect(surf, color, (0, top + 8, W, hy - top - 6))
        elif kind == 'ridges':
            for color, amp, step, off in ((far, 26, 34, 0), (near, 14, 22, 9)):
                pts = [(0, hy + 2)]
                x = -off
                while x < W + step:
                    pts.append((x, hy - r.randrange(amp // 3, amp)))
                    pts.append((x + step // 2, hy - r.randrange(2, amp // 2)))
                    x += step
                pts.append((W, hy + 2))
                pygame.draw.polygon(surf, color, pts)
                if color is far:  # snowy peaks on the far range
                    cap = _lerp(color, (250, 250, 255), 0.55)
                    for i in range(1, len(pts) - 1, 2):
                        px, py = pts[i]
                        pygame.draw.polygon(surf, cap, [(px, py), (px - 5, py + 6), (px + 5, py + 6)])
        elif kind == 'islands':
            for _ in range(4):
                cx, w = r.randrange(W), r.randrange(30, 70)
                pygame.draw.ellipse(surf, far, (cx - w // 2, hy - 6, w, 12))
            pygame.draw.rect(surf, sky.get_at((W // 2, hy + 1))[:3], (0, hy, W, 2))
        elif kind == 'ceiling':
            dark = _lerp(base, (10, 10, 16), 0.7)
            pygame.draw.rect(surf, dark, (0, 0, W, 10))
            x = 0
            while x < W:
                w, h = r.randrange(6, 16), r.randrange(6, 26)
                pygame.draw.polygon(surf, dark, [(x, 9), (x + w, 9), (x + w // 2 + r.randrange(-2, 3), 9 + h)])
                x += w - 2
            for _ in range(5):  # boulders on the horizon
                cx, w = r.randrange(W), r.randrange(16, 40)
                pygame.draw.ellipse(surf, _lerp(base, (30, 26, 24), 0.6), (cx, hy - 8, w, 14))
        elif kind == 'wall':
            wall = _lerp(base, (90, 80, 70), 0.5)
            shade = _lerp(wall, (0, 0, 0), 0.4)
            pygame.draw.rect(surf, wall, (0, 0, W, hy - 4))
            pygame.draw.rect(surf, _lerp(wall, (0, 0, 0), 0.3), (0, hy - 6, W, 3))
            lit = (250, 230, 160) if when == 'night' else _lerp(wall, (220, 236, 250), 0.6)
            for x in range(8, W, 40):
                pygame.draw.rect(surf, shade, (x, 10, 22, 22))
                pygame.draw.rect(surf, lit, (x + 2, 12, 18, 18))
                pygame.draw.line(surf, shade, (x + 11, 12), (x + 11, 29))
            rail = _lerp(wall, (255, 255, 255), 0.35)
            for x in range(0, W, 8):
                pygame.draw.line(surf, rail, (x, hy - 14), (x, hy - 7))
            pygame.draw.line(surf, _lerp(wall, (255, 255, 255), 0.45), (0, hy - 14), (W, hy - 14))

    def _haze(self, surf, hy, when):
        glow = HAZE.get(when, HAZE['day'])
        layer = pygame.Surface((W, 14), pygame.SRCALPHA)
        for i in range(14):
            pygame.draw.line(layer, (*glow, int(150 * math.exp(-((i - 6) / 3.0) ** 2))), (0, i), (W, i))
        surf.blit(layer, (0, hy - 7))

    def _shafts(self, surf, when, sky_kind):
        if when == 'night' or sky_kind == 'indoor':
            return
        col = (255, 200, 140) if when == 'evening' else (255, 250, 230)
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        for x, w, a in ((-30, 30, 34), (34, 14, 26), (78, 40, 22), (160, 20, 18)):
            pygame.draw.polygon(layer, (*col, a), [(x + 60, -10), (x + 60 + w, -10), (x + w + 10, H), (x + 10, H)])
        surf.blit(layer, (0, 0))

    def _vignette(self, surf):
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(18):
            pygame.draw.rect(layer, (0, 0, 20, int(70 * (1 - i / 18) ** 2)), (i, i, W - 2 * i, BOX_TOP + 10 - 2 * i), 1)
        surf.blit(layer, (0, 0))

    # -- particles -----------------------------------------------------------------

    def _particles(self, canvas, kind, when, t_ms):
        if not kind:
            return
        r = random.Random(7)
        t = t_ms / 1000.0
        for i in range(26):
            x0, y0, sp = r.randrange(W), r.randrange(BOX_TOP), r.uniform(0.6, 1.4)
            if kind == 'snow':
                x, y, c = (x0 + math.sin(t * sp + i) * 6) % W, (y0 + t * 14 * sp) % BOX_TOP, (250, 250, 255)
            elif kind == 'bubbles':
                x, y, c = x0, (y0 - t * 10 * sp) % BOX_TOP, (200, 240, 255)
            elif kind == 'dust':
                x, y, c = (x0 + t * 3 * sp) % W, (y0 + math.sin(t + i) * 3) % BOX_TOP, (200, 170, 120)
            else:  # pollen by day, fireflies at night
                x, y = (x0 + t * 8 * sp) % W, (y0 + math.sin(t * sp + i) * 4) % BOX_TOP
                c = (180, 255, 160) if when == 'night' else (255, 250, 200)
            canvas.set_at((int(x), int(y)), c)
            if i % 3 == 0:
                canvas.set_at((int(x) + 1, int(y)), c)

    # -- turfs ---------------------------------------------------------------------

    def _turf(self, kind, when, w, h):
        key = (kind, when, w, h)
        img = self._turfs.get(key)
        if img is None:
            img = self._turfs[key] = self._make_turf(kind if kind in TURF else 'grass', when, w, h)
        return img

    def _make_turf(self, kind, when, w, h):
        pad = 10
        surf = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2
        p = {k: (_tint(v, when) if isinstance(v, tuple) else [_tint(c, when) for c in v]) for k, v in TURF[kind].items()}
        r = random.Random(5 + w)
        shadow = pygame.Surface((w + 16, h + 12), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 80), (4, 6, w + 8, h + 4))
        surf.blit(shadow, (cx - w // 2 - 6, cy - h // 2 + 2))
        rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        side = max(3, h // 9)  # the platform's thickness, then its top
        pygame.draw.ellipse(surf, _lerp(p['rim'], (0, 0, 0), 0.55), rect.move(0, side))
        pygame.draw.ellipse(surf, _lerp(p['rim'], (0, 0, 0), 0.3), rect.move(0, side // 2))
        pygame.draw.ellipse(surf, p['rim'], rect)
        disc = rect.inflate(-max(6, w // 12), -max(4, h // 6)).move(0, -1)
        pygame.draw.ellipse(surf, p['disc'], disc)
        for k in range(1, 4):  # a glow toward the middle
            g = disc.inflate(-disc.w * k // 5, -disc.h * k // 5).move(-k * w // 60, -k * h // 40)
            pygame.draw.ellipse(surf, _lerp(p['disc'], p['light'], k / 3), g)
        deco = p['deco']
        n = max(14, w // 4)
        if kind in ('grass', 'field'):
            # tufts of three blades all round the rim, taller at the back
            for i in range(n + n // 2):
                a = i / (n + n // 2) * 2 * math.pi + r.random() * 0.1
                x, y = cx + math.cos(a) * w / 2 * 0.97, cy + math.sin(a) * h / 2 * 0.97
                back = math.sin(a) < 0
                tall = r.randrange(3, 7) if back else r.randrange(2, 4)
                for dx, lean in ((-2, -1), (0, 0), (2, 1)):
                    c = deco[0] if dx else deco[1 if back else 0]
                    pygame.draw.line(surf, c, (int(x + dx), int(y)), (int(x + dx + lean), int(y - tall + abs(dx) // 2)))
                surf.set_at((int(x), int(y - tall)), deco[-1])
        elif kind == 'snow':
            pygame.draw.ellipse(surf, deco[0], rect, max(2, w // 30))
            for i in range(n // 2):
                a = i / (n // 2) * 2 * math.pi
                x, y = cx + math.cos(a) * w / 2 * 0.9, cy + math.sin(a) * h / 2 * 0.85
                pygame.draw.ellipse(surf, deco[0], (int(x) - 4, int(y) - 2, 8, 4))
            for _ in range(w // 6):
                surf.set_at((r.randrange(disc.left + 4, disc.right - 4), r.randrange(disc.top + 2, disc.bottom - 2)), deco[0])
        elif kind == 'water':
            net = pygame.Surface(rect.size, pygame.SRCALPHA)  # caustics, clipped to the disc
            for _ in range(w * h // 60):
                x, y = r.randrange(rect.w), r.randrange(rect.h)
                pygame.draw.ellipse(net, (*p['light'], 255), (x, y, r.randrange(6, 14), r.randrange(3, 6)), 1)
            mask = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(mask, (255, 255, 255, 255), disc.move(-rect.x, -rect.y))
            net.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surf.blit(net, rect.topleft)
            pygame.draw.ellipse(surf, deco[1], rect, 2)
            pygame.draw.ellipse(surf, _tint((248, 252, 255), when), rect, 1)
        elif kind == 'sand':
            for k in range(4):  # wind ripples
                yy = disc.top + (k + 1) * disc.h // 5
                half = math.sqrt(max(0.0, 1 - ((yy - cy) / (h / 2)) ** 2)) * disc.w / 2 - 4
                pts = [(int(cx + xx), int(yy + 1.5 * math.sin(xx / 5 + k))) for xx in range(-int(half), int(half), 2)]
                if len(pts) > 1:
                    pygame.draw.lines(surf, deco[0], False, pts)
        elif kind == 'cave':
            for i in range(n // 3):
                a = math.pi + r.random() * math.pi
                x, y = cx + math.cos(a) * w / 2 * 0.95, cy + math.sin(a) * h / 2 * 0.9
                s = r.randrange(3, 7)
                pygame.draw.ellipse(surf, deco[r.randrange(2)], (int(x) - s // 2, int(y) - s, s, s))
                pygame.draw.ellipse(surf, deco[2], (int(x) - s // 2, int(y) - s, s, s), 1)
        elif kind == 'indoor':
            pygame.draw.ellipse(surf, deco[1], disc.inflate(-w // 5, -h // 4), 1)
            pygame.draw.ellipse(surf, deco[0], disc, 1)
        return surf
