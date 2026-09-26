"""
backdrop.py - the battle background, drawn in code (no image files):

    sky       colours by the DS clock (morning, day, evening, night with stars)
    scenery   drifting clouds, distant hills and a treeline
    ground    bands that get taller toward the viewer, for depth, with
              swaying grass tufts
    terrain   field, snow, cave or indoor, guessed from the location name
    weather   rain, thunderstorms, snow, blizzards, sand, hail, ash or fog,
              from the save's weather ID

The parts that don't move are drawn once per (terrain, time of day) and
cached; clouds, stars, grass and weather are drawn every frame.
"""

import math
import random

import pygame

W = 256
HORIZON = 56     # where the ground starts
GROUND_END = 146  # top of the message box

# Sky colours, top to bottom, per time of day.
SKY = {
    'morning': [(150, 190, 236), (176, 206, 240), (204, 222, 240), (232, 232, 224), (248, 236, 208)],
    'day':     [(104, 168, 232), (124, 182, 238), (146, 196, 244), (170, 210, 248), (196, 224, 250)],
    'evening': [(88, 96, 168), (152, 104, 160), (216, 120, 128), (240, 152, 104), (248, 192, 112)],
    'night':   [(16, 20, 48), (24, 32, 64), (32, 44, 84), (44, 58, 100), (58, 74, 116)],
}
# How the ground and scenery are tinted per time of day: (multiply, add).
TINT = {
    'morning': ((1.0, 1.0, 0.96), (6, 4, 0)),
    'day': ((1.0, 1.0, 1.0), (0, 0, 0)),
    'evening': ((0.92, 0.78, 0.72), (18, 4, 0)),
    'night': ((0.45, 0.5, 0.72), (0, 0, 10)),
}
# Ground bands far to near, and the scenery, per terrain.
GROUND = {
    'field': [(112, 168, 96), (120, 176, 100), (128, 186, 104), (138, 194, 110), (146, 202, 116), (154, 208, 122)],
    'snow': [(196, 212, 228), (206, 220, 234), (216, 228, 240), (226, 236, 244), (236, 242, 248), (244, 248, 252)],
    'cave': [(96, 76, 60), (104, 84, 66), (114, 92, 72), (124, 100, 78), (134, 108, 84), (142, 116, 90)],
    'indoor': [(176, 152, 120), (188, 164, 130), (198, 174, 138), (208, 184, 146), (216, 192, 152), (224, 200, 160)],
}
HILLS = {
    'field': [(120, 156, 176), (84, 132, 96)],      # far hills, near treeline
    'snow': [(176, 192, 212), (150, 170, 190)],
}
CAVE_WALL = [(52, 44, 44), (62, 52, 50), (72, 60, 56), (84, 70, 64)]
INDOOR_WALL = [(232, 220, 196), (220, 206, 180)]

CAVE_WORDS = ('cave', 'mt. coronet', 'tunnel', 'ruins', 'mine', 'victory road', 'stark mountain',
              'iron island', 'wayward', 'turnback', 'oreburgh gate', 'distortion')
INDOOR_WORDS = ('gym', 'pokémon center', 'pokemon center', 'mart', 'house', 'building', 'tower', 'lab',
                'hotel', 'mansion', 'chateau', 'department', 'museum', 'condo', 'league', 'hall', 'café',
                'cafe', 'restaurant', 'contest', 'library', 'galactic', 'villa', 'gate', 'store', 'shop',
                'factory', 'poketch', 'pokétch', 'frontier', 'resort area')
SNOW_WORDS = ('snowpoint', 'route 216', 'route 217', 'acuity')


def period(clock):
    """'morning', 'day', 'evening' or 'night' from the DS clock ('YYYY-MM-DD HH:MM')."""
    try:
        hour = int(clock.split(' ')[1].split(':')[0])
    except (AttributeError, IndexError, ValueError):
        return 'day'
    if 4 <= hour < 10:
        return 'morning'
    if 10 <= hour < 17:
        return 'day'
    if 17 <= hour < 20:
        return 'evening'
    return 'night'


def terrain(location):
    text = f"{location.get('name') or ''} {location.get('area') or ''}".lower()
    if any(w in text for w in CAVE_WORDS):
        return 'cave'
    if any(w in text for w in INDOOR_WORDS):
        return 'indoor'
    if any(w in text for w in SNOW_WORDS):
        return 'snow'
    return 'field'


def weather_kind(weather_id, place):
    """Which particles to draw for a saved weather ID (see platinum_data.WEATHER)."""
    if place in ('cave', 'indoor'):
        return None
    return {2: 'rain', 3: 'heavy_rain', 4: 'storm', 5: 'snow', 6: 'heavy_snow', 7: 'blizzard',
            9: 'ash', 10: 'sand', 11: 'hail', 14: 'fog', 15: 'deep_fog',
            32: 'rain', 34: 'snow', 35: 'snow', 36: 'snow'}.get(weather_id)


def _tint(c, when):
    mul, add = TINT[when]
    return tuple(max(0, min(255, int(v * m + a))) for v, m, a in zip(c, mul, add))


def _bands(surf, y0, heights, colors):
    y = y0
    for i, (h, c) in enumerate(zip(heights, colors)):
        pygame.draw.rect(surf, c, (0, y, W, h))
        if i > 0:  # checkerboard dither into the band above
            prev = colors[i - 1]
            for x in range(0, W, 2):
                surf.set_at((x, y), prev)
                surf.set_at((x + 1, y + 1), prev)
        y += h


def _ground_heights(total, n):
    """Band heights that grow toward the viewer and add up to `total`."""
    weights = [i + 2 for i in range(n)]
    s = sum(weights)
    hs = [max(2, total * w // s) for w in weights]
    hs[-1] += total - sum(hs)
    return hs


class Backdrop:
    def __init__(self):
        self._static = {}
        rng = random.Random(7)
        self.stars = [(rng.randrange(W), rng.randrange(2, HORIZON - 14), rng.randrange(1000)) for _ in range(34)]
        self.clouds = [(rng.randrange(W + 80), rng.randrange(4, 26), rng.choice([1, 2, 3]), rng.uniform(2.0, 5.0))
                       for _ in range(4)]
        # Grass tufts: more and closer together toward the viewer.
        self.tufts = []
        for _ in range(46):
            depth = rng.random() ** 0.6            # 0 far .. 1 near
            y = HORIZON + 4 + int(depth * (GROUND_END - HORIZON - 6))
            self.tufts.append((rng.randrange(W), y, 1 + int(depth * 2), rng.randrange(1000)))
        self.particles = [(rng.randrange(W), rng.randrange(GROUND_END), rng.random()) for _ in range(140)]

    # -- static layer ----------------------------------------------------------

    def _static_layer(self, place, when):
        key = (place, when)
        surf = self._static.get(key)
        if surf is not None:
            return surf
        surf = pygame.Surface((W, GROUND_END))
        heights = _ground_heights(GROUND_END - HORIZON, 6)
        ground = [_tint(c, when) for c in GROUND[place]]

        if place in ('field', 'snow'):
            sky = SKY[when]
            if place == 'snow':
                sky = [tuple(int(v * 0.8 + 48) for v in c) for c in sky]
            _bands(surf, 0, _ground_heights(HORIZON, len(sky))[::-1], sky)
            far, near = [_tint(c, when) for c in HILLS[place]]
            for x in range(W):  # rolling far hills, then a bumpy treeline in front
                h1 = int(9 + 5 * math.sin(x / 23.0) + 3 * math.sin(x / 7.3 + 1.2))
                pygame.draw.line(surf, far, (x, HORIZON - h1), (x, HORIZON - 1))
                h2 = int(4 + 2 * math.sin(x / 5.1) + 2 * abs(math.sin(x / 13.7)))
                pygame.draw.line(surf, near, (x, HORIZON - h2), (x, HORIZON - 1))
            for tx in range(6, W, 29):  # a few pine trees on the treeline
                th = 9 + (tx * 7) % 5
                for i in range(th):
                    half = i // 2
                    pygame.draw.line(surf, near, (tx - half, HORIZON - th + i), (tx + half, HORIZON - th + i))
        elif place == 'cave':
            _bands(surf, 0, _ground_heights(HORIZON, 4)[::-1], [_tint(c, 'day') for c in CAVE_WALL])
            rng = random.Random(3)
            for _ in range(70):  # rocky texture
                x, y = rng.randrange(W), rng.randrange(HORIZON)
                pygame.draw.rect(surf, (44, 36, 36), (x, y, rng.randrange(2, 6), 1))
            for sx in range(8, W, 22):  # stalactites
                length = 6 + (sx * 13) % 11
                for i in range(length):
                    half = max(0, (length - i) // 4)
                    pygame.draw.line(surf, (40, 32, 32), (sx - half, i), (sx + half, i))
        else:  # indoor: panelled wall and a baseboard
            pygame.draw.rect(surf, INDOOR_WALL[0], (0, 0, W, HORIZON))
            for x in range(0, W, 16):
                pygame.draw.line(surf, INDOOR_WALL[1], (x, 0), (x, HORIZON - 1))
            pygame.draw.rect(surf, (150, 118, 88), (0, HORIZON - 5, W, 5))
            pygame.draw.line(surf, (190, 156, 120), (0, HORIZON - 5), (W - 1, HORIZON - 5))

        _bands(surf, HORIZON, heights, ground)
        pygame.draw.line(surf, tuple(min(255, v + 24) for v in ground[0]), (0, HORIZON), (W - 1, HORIZON))
        if place == 'indoor':  # floor tiles in perspective
            y = HORIZON
            for i, h in enumerate(heights):
                step = 8 + i * 4
                for x in range((i % 2) * step // 2, W, step):
                    surf.set_at((x, y + h // 2), tuple(max(0, v - 18) for v in ground[i]))
                y += h
        self._static[key] = surf
        return surf

    # -- per frame -------------------------------------------------------------

    def draw(self, canvas, place, when, t_ms, chroma=None):
        if chroma:
            canvas.fill(chroma)
            return
        canvas.blit(self._static_layer(place, when), (0, 0))

        if place in ('field', 'snow'):
            if when == 'night':
                for x, y, ph in self.stars:
                    if ((t_ms + ph * 7) // 400) % 5:
                        canvas.set_at((x, y), (248, 240, 200) if (x + y) % 3 else (200, 216, 248))
            cloud = {'night': (72, 80, 112), 'evening': (248, 200, 184)}.get(when, (248, 248, 252))
            shade = tuple(max(0, v - 30) for v in cloud)
            for x0, y, size, speed in self.clouds:
                x = int((x0 + t_ms / 1000.0 * speed) % (W + 80)) - 40
                w = 14 + size * 8
                pygame.draw.rect(canvas, shade, (x + 2, y + 5, w - 4, 3))
                pygame.draw.rect(canvas, cloud, (x, y + 3, w, 4))
                pygame.draw.rect(canvas, cloud, (x + 4, y, w // 2, 4))
                pygame.draw.rect(canvas, cloud, (x + w // 2 - 1, y + 1, w // 3, 3))

        if place in ('field', 'snow'):
            sway = (t_ms // 450) % 2
            dark = _tint((64, 128, 64) if place == 'field' else (176, 196, 212), when)
            light = _tint((168, 224, 128) if place == 'field' else (252, 252, 255), when)
            for x, y, size, ph in self.tufts:
                s = sway if (ph % 2) else 1 - sway
                for i in range(size + 1):
                    canvas.set_at((x + i * 2, y), dark)
                    canvas.set_at((x + i * 2 + s, y - 1 - (i % 2)), light)

    def draw_weather(self, canvas, kind, t_ms):
        if not kind:
            return
        t = t_ms / 1000.0
        if kind in ('rain', 'heavy_rain', 'storm'):
            n = {'rain': 60, 'heavy_rain': 110, 'storm': 110}[kind]
            for x0, y0, r in self.particles[:n]:
                x = int(x0 - t * 60 - r * 30) % W
                y = int(y0 + t * (240 + r * 80)) % GROUND_END
                pygame.draw.line(canvas, (176, 200, 232), (x, y), (x - 1, y + 3))
            if kind == 'storm' and int(t_ms) % 5200 < 90:
                flash = pygame.Surface((W, GROUND_END), pygame.SRCALPHA)
                flash.fill((255, 255, 255, 120))
                canvas.blit(flash, (0, 0))
        elif kind in ('snow', 'heavy_snow', 'blizzard', 'ash'):
            n = {'snow': 50, 'heavy_snow': 100, 'blizzard': 140, 'ash': 60}[kind]
            wind = {'blizzard': 90, 'heavy_snow': 20}.get(kind, 6)
            color = (140, 136, 132) if kind == 'ash' else (252, 252, 255)
            for x0, y0, r in self.particles[:n]:
                x = int(x0 + t * wind + math.sin(t * 1.5 + r * 6) * 4) % W
                y = int(y0 + t * (20 + r * 25) * (2.5 if kind == 'blizzard' else 1)) % GROUND_END
                canvas.set_at((x, y), color)
                if r > 0.6:
                    canvas.set_at((x + 1, y), color)
        elif kind == 'sand':
            for x0, y0, r in self.particles[:90]:
                x = int(x0 + t * (160 + r * 80)) % W
                y = int(y0 + math.sin(t * 3 + r * 9) * 3) % GROUND_END
                canvas.set_at((x, y), (216, 184, 120))
        elif kind == 'hail':
            for x0, y0, r in self.particles[:40]:
                x = int(x0 - t * 20) % W
                y = int(y0 + t * (180 + r * 60)) % GROUND_END
                pygame.draw.rect(canvas, (236, 244, 252), (x, y, 2, 2))
        elif kind in ('fog', 'deep_fog'):
            fog = pygame.Surface((W, GROUND_END), pygame.SRCALPHA)
            alpha = 70 if kind == 'fog' else 120
            for i in range(6):
                y = 20 + i * 20
                x = int((t * (6 + i * 2)) % W)
                pygame.draw.rect(fog, (236, 236, 240, alpha), (x - W, y, W * 2, 10))
            canvas.blit(fog, (0, 0))
