"""
mkds.py - the overlay's view for Mario Kart DS during a race (core/mkds_reader.py's
state, as the game card's 'mkds'). It keeps the game card's header and footer
(overlay/gamecard.py), with in between:

    left      the racers in order, first to last: place, head and name, the
              player's row lit. When places change the rows slide to their
              new places (RankMotion), as the game's bottom screen has them.
    middle    the whole course from above on a dark panel, like the Tetris
              view's board, as a race's position overview on TV has it: the
              course's map (overlay/mkds_art.py, placed in the game's world
              by core/mkds_maps.py; a wide course turned a quarter turn to
              fill the tall panel) under the line through its checkpoints,
              a dot for each racer with its place, the leader's ringed in
              gold and the player's head on top of the rest. Dots glide from
              read to read (MapMotion). With no map for the course (or the
              console's checkpoints not matching the one the map was placed
              by) it's the line alone.
    right     the player's place and lap, the race's time, then achievements
              as in the Tetris view

A racer whose character isn't known shows as a dot in a colour of its own
with its number. Outside a race (the menus, Battle, Missions) the game card
shows instead.
"""

import math

import pygame

from core.mkds_maps import MAPS
from core.mkds_reader import COURSES, midpoints, short_name

from . import ui
from .gamecard import FOOTER_Y, HEADER_H, W
from .tetris import BOARD_BG, BOARD_FRAME, BOARD_GRID, TetrisView

TOP = HEADER_H + 2
HEIGHT = FOOTER_Y - HEADER_H - 4
RANK = (3, TOP, 66, HEIGHT)                  # the racers in order
MAP = (72, TOP, 104, HEIGHT)                 # the course
RIGHT = (179, TOP, W - 3 - 179, HEIGHT)      # place, lap, achievements
RACE_H = 62                                  # the place and lap panel's height
ROW_H = 17
STRIP_H = 9                                  # the map panel's course name and mode strips

SLIDE_MS = 300                               # a row's slide to its new place
MAP_DIM = 0.45                               # the map under the line, this much darker
MATCH_WITHIN = 60.0                          # world units: the console's finish line this near the map's
TURN_GAIN = 1.15                             # a wide course is turned when that makes it this much bigger

PLACE_COLORS = {1: (240, 196, 48), 2: (196, 204, 216), 3: (212, 136, 72)}
# A dot's colour by character (their colours in the game), and by slot for one not known
CHARACTER_COLORS = {
    "Mario": (224, 48, 40), "Donkey Kong": (156, 92, 44), "Toad": (60, 112, 232), "Bowser": (240, 152, 32),
    "Peach": (248, 128, 184), "Wario": (244, 212, 40), "Yoshi": (88, 200, 72), "Luigi": (32, 136, 64),
    "Dry Bones": (208, 208, 196), "Daisy": (248, 156, 40), "Waluigi": (128, 64, 184), "R.O.B.": (148, 152, 164),
    "Shy Guy": (216, 40, 56),
}
SLOT_COLORS = [(224, 48, 40), (60, 112, 232), (88, 200, 72), (244, 212, 40), (248, 128, 184),
               (156, 92, 44), (128, 64, 184), (208, 208, 196)]
TRACK, TRACK_EDGE = (168, 176, 188), (8, 10, 14)
STRIP_TEXT = (128, 140, 156)


def ordinal(n):
    """1 -> '1st', 2 -> '2nd', 11 -> '11th'."""
    if n is None:
        return "-"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def race_time(ms):
    """83456 -> '1:23.45'."""
    ms = max(0, int(ms or 0))
    return f"{ms // 60000}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}"


def color_of(racer):
    return CHARACTER_COLORS.get(racer.get('character')) or SLOT_COLORS[racer['slot'] % len(SLOT_COLORS)]


def name_of(racer):
    return short_name(racer.get('character')) or ("YOU" if racer.get('player') else f"CPU {racer['slot']}")


class RankMotion:
    """Where each racer's row is drawn: a row whose place changed slides from
    where it was drawn to its new place over SLIDE_MS (eased), so passes
    play out the way the game's bottom screen shows them."""

    def __init__(self):
        self.rows = {}      # slot -> (from y, to y, start t_ms)

    def take(self, order, t_ms):
        for i, slot in enumerate(order):
            to = i * ROW_H
            row = self.rows.get(slot)
            if row is None:
                self.rows[slot] = (to, to, t_ms)
            elif row[1] != to:
                self.rows[slot] = (self.y(slot, t_ms), to, t_ms)
        for slot in list(self.rows):
            if slot not in order:
                del self.rows[slot]

    def y(self, slot, t_ms):
        start_y, to, start = self.rows[slot]
        f = min(1.0, max(0.0, (t_ms - start) / SLIDE_MS))
        return start_y + (to - start_y) * ui.ease_out(f)

    def moving(self, slot, t_ms):
        start_y, to, start = self.rows[slot]
        return start_y != to and t_ms - start < SLIDE_MS


class MapMotion:
    """Where each racer's dot is drawn between reads (a few a second): from
    where the read before had it to where the latest has it, over about the
    time between reads (so a read behind), the way TetrisMotion steps the
    falling piece."""

    def __init__(self):
        self.taken = None
        self.was = {}       # slot -> (x, z) the read before
        self.now = {}       # slot -> (x, z) the latest
        self.arrived = 0
        self.interval = 200

    def take(self, race, t_ms):
        if race is self.taken:
            return
        if self.taken is not None:
            self.interval = max(60, min(500, t_ms - self.arrived))
        self.taken = race
        self.was = {slot: self.at(slot, t_ms) for slot in self.now}
        self.now = {r['slot']: (r['x'], r['z']) for r in race['racers']}
        self.arrived = t_ms

    def at(self, slot, t_ms):
        x, z = self.now[slot]
        if slot not in self.was:
            return x, z
        f = min(1.0, (t_ms - self.arrived) / self.interval)
        wx, wz = self.was[slot]
        return wx + (x - wx) * f, wz + (z - wz) * f


class MkdsView:
    def __init__(self, font, mini, card, art=None):
        """card: the game card (overlay/gamecard.py), for the header and
        footer. art: an MkdsArt (overlay/mkds_art.py), or None to draw
        without the game's art."""
        self.font = font
        self.mini = mini
        self.card = card
        self.art = art
        self.ranks = RankMotion()
        self.motion = MapMotion()
        self._view = None   # (key, the course's world window, scale, mirror or None)

    def draw(self, canvas, d, t_ms):
        race = d['mkds']
        ra = d.get('ra_set')
        achs = ra.playable_achievements if ra else []
        self.ranks.take(race['order'], t_ms)
        self.motion.take(race, t_ms)
        ui.tiled_background(canvas, t_ms)
        self.card._header(canvas, d)
        self._ranking(canvas, race, t_ms)
        self._map(canvas, race, t_ms)
        self._race(canvas, race)
        x, y, w, h = RIGHT
        self._achievements(canvas, d, achs, t_ms, (x, y + RACE_H + 2, w, h - RACE_H - 2))
        self.card._footer(canvas, d, ra, achs, t_ms)

    # the right column's achievements: as the Tetris view's
    _achievements = TetrisView._achievements

    # -- left: the racers in order ----------------------------------------------

    def _ranking(self, canvas, race, t_ms):
        t = ui.THEME
        x, y, w, h = RANK
        ui.panel(canvas, RANK)
        by_slot = {r['slot']: r for r in race['racers']}
        clip = canvas.get_clip()
        canvas.set_clip((x + 1, y + 1, w - 2, h - 2))
        # (the player's row last, so it's on top while rows pass each other)
        for slot in sorted(race['order'], key=lambda s: by_slot[s]['player']):
            r = by_slot[slot]
            ry = y + 3 + round(self.ranks.y(slot, t_ms))
            if r['player']:
                pygame.draw.rect(canvas, t['lead_fill'], (x + 2, ry, w - 4, ROW_H - 1))
                pygame.draw.rect(canvas, t['lead_border'], (x + 2, ry, w - 4, ROW_H - 1), 1)
            elif self.ranks.moving(slot, t_ms):
                pygame.draw.rect(canvas, t['panel_lo'], (x + 2, ry, w - 4, ROW_H - 1))
            place = r['place']
            color = PLACE_COLORS.get(place)
            if color:
                pygame.draw.rect(canvas, ui.darken(color, 30), (x + 4, ry + 3, 9, 11))
                pygame.draw.rect(canvas, color, (x + 4, ry + 3, 9, 10))
                self.font.draw(canvas, str(place), (x + 9, ry + 4), t['text_light'], t['text_light_shadow'], align='center')
            else:
                self.font.draw(canvas, str(place), (x + 9, ry + 4), t['text'], t['text_shadow'], align='center')
            self._icon(canvas, r, x + 23, ry + ROW_H // 2)
            self.mini.draw(canvas, self.mini.fit(name_of(r), w - 36), (x + 33, ry + 6),
                           t['lead_border'] if r['player'] else t['text_muted'])
        canvas.set_clip(clip)

    def _icon(self, canvas, racer, cx, cy):
        """The racer's head centred on (cx, cy), or its dot when there's no head."""
        head = self.art.head(racer.get('character')) if self.art else None
        if head:
            canvas.blit(head, (cx - head.get_width() // 2, cy - head.get_height() // 2))
        else:
            self._dot(canvas, racer, cx, cy, 5, label=str(racer['slot'] + 1))

    def _dot(self, canvas, racer, cx, cy, radius, ring=None, label=None):
        pygame.draw.circle(canvas, TRACK_EDGE, (cx, cy), radius + 1)
        if ring:
            pygame.draw.circle(canvas, ring, (cx, cy), radius + 1)
            pygame.draw.circle(canvas, TRACK_EDGE, (cx, cy), radius)
        pygame.draw.circle(canvas, color_of(racer), (cx, cy), radius - (1 if ring else 0))
        if label:
            self.mini.draw(canvas, label, (cx + 1, cy - 2), (255, 255, 255), TRACK_EDGE, align='center')

    # -- middle: the course -----------------------------------------------------

    @staticmethod
    def turned(x, z, turn):
        """A world point as the panel has it: (x, z), or with the course a
        quarter turn clockwise, (-z, x)."""
        return (-z, x) if turn else (x, z)

    def _window(self, race, size):
        """(the panel's window on the course (u0, v0, u1, v1, in turned()'s
        terms), pixels a world unit, the map's mirror flag or None for no map,
        and whether the course is turned): the whole course (its checkpoints,
        or the racers before they're read) with a margin, widened to the
        panel's shape. A course wider than it's tall is turned a quarter turn
        when that makes it TURN_GAIN times bigger in the tall panel. Worked
        out once a course."""
        cps = race.get('checkpoints') or ()
        key = (race['course'], len(cps), size)
        if self._view and self._view[0] == key:
            return self._view[1:]
        if cps:
            xs = [v for c in cps for v in (c[0], c[2])]
            zs = [v for c in cps for v in (c[1], c[3])]
        else:
            xs = [r['x'] for r in race['racers']] or [0.0]
            zs = [r['z'] for r in race['racers']] or [0.0]
        w, h = size
        span_x, span_z = max(xs) - min(xs) or 1.0, max(zs) - min(zs) or 1.0
        turn = bool(cps) and min(w / span_z, h / span_x) > TURN_GAIN * min(w / span_x, h / span_z)
        pts = [self.turned(px, pz, turn) for px, pz in zip(xs, zs)]
        u0, u1 = min(p[0] for p in pts), max(p[0] for p in pts)
        v0, v1 = min(p[1] for p in pts), max(p[1] for p in pts)
        pad = 0.05 * max(u1 - u0, v1 - v0, 400.0)
        u0, u1, v0, v1 = u0 - pad, u1 + pad, v0 - pad, v1 + pad
        scale = min(w / (u1 - u0), h / (v1 - v0))
        cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
        window = (cu - w / 2 / scale, cv - h / 2 / scale, cu + w / 2 / scale, cv + h / 2 / scale)
        self._view = (key, window, scale, self._mirror(race) if cps else None, turn)
        return self._view[1:]

    @staticmethod
    def _mirror(race):
        """Whether the map's to be turned over to match the console's course
        (False: as it is, True: x the other way), or None to draw no map: the
        console's finish line is neither where the course file has it nor
        mirrored (core/mkds_maps.py)."""
        course_file = COURSES[race['course']][1]
        if course_file not in MAPS:
            return None
        fx, fz = MAPS[course_file][5]
        (x, z), = midpoints(race['checkpoints'][:1])
        if math.hypot(x - fx, z - fz) <= MATCH_WITHIN:
            return False
        if math.hypot(x + fx, z - fz) <= MATCH_WITHIN:
            return True
        return None

    def _map(self, canvas, race, t_ms):
        t = ui.THEME
        x, y, w, h = MAP
        pygame.draw.rect(canvas, BOARD_FRAME, (x, y, w, h))
        pygame.draw.rect(canvas, t['bar_lo'], (x + 1, y + 1, w - 2, h - 2))
        inner = pygame.Rect(x + 2, y + 2 + STRIP_H, w - 4, h - 4 - 2 * STRIP_H)
        pygame.draw.rect(canvas, BOARD_BG, inner)
        # the course's name above, the mode below
        name = (race.get('course_name') or '').upper()
        self.mini.draw(canvas, self.mini.fit(name, w - 8), (x + w // 2, y + 4), t['text_light'], None, align='center')
        mode = " ".join(v for v in ((race.get('mode') or '').upper(), (race.get('cc') or '').upper(),
                                    "MIRROR" if race.get('mirror') else "") if v)
        self.mini.draw(canvas, self.mini.fit(mode, w - 8), (x + w // 2, y + h - 2 - STRIP_H + 2), STRIP_TEXT,
                       align='center')
        window, scale, mirror, turn = self._window(race, inner.size)

        def to(wx, wz):
            u, v = self.turned(wx, wz, turn)
            return inner.x + (u - window[0]) * scale, inner.y + (v - window[1]) * scale
        clip = canvas.get_clip()
        canvas.set_clip(inner)
        backdrop = None
        if self.art and mirror is not None:
            backdrop = self.art.course_map(COURSES[race['course']][1], window, inner.size, mirror, MAP_DIM, turn)
        if backdrop:
            canvas.blit(backdrop, inner.topleft)
        else:
            for gx in range(inner.x + 8, inner.right, 8):
                pygame.draw.line(canvas, BOARD_GRID, (gx, inner.y), (gx, inner.bottom - 1))
            for gy in range(inner.y + 8, inner.bottom, 8):
                pygame.draw.line(canvas, BOARD_GRID, (inner.x, gy), (inner.right - 1, gy))
        self._track(canvas, race, to, thin=bool(backdrop))
        self._markers(canvas, race, to, t_ms)
        canvas.set_clip(clip)

    def _track(self, canvas, race, to, thin):
        """The line through the checkpoints' middles, and the finish line
        across it (checkpoint 0) in black and white."""
        cps = race.get('checkpoints') or ()
        if len(cps) < 3:
            return
        pts = [to(mx, mz) for mx, mz in midpoints(cps)]
        if not thin:
            pygame.draw.lines(canvas, TRACK_EDGE, True, pts, 5)
            pygame.draw.lines(canvas, TRACK, True, pts, 3)
        else:
            pygame.draw.lines(canvas, TRACK_EDGE, True, pts, 3)
            pygame.draw.lines(canvas, TRACK, True, pts, 1)
        x1, z1, x2, z2, _ = cps[0]
        (ax, ay), (bx, by) = to(x1, z1), to(x2, z2)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n * 4, dy / n * 4
        pygame.draw.line(canvas, TRACK_EDGE, (mx - dx * 1.5, my - dy * 1.5), (mx + dx * 1.5, my + dy * 1.5), 4)
        pygame.draw.line(canvas, (255, 255, 255), (mx - dx, my - dy), (mx, my), 2)
        pygame.draw.line(canvas, (24, 24, 24), (mx, my), (mx + dx, my + dy), 2)

    def _markers(self, canvas, race, to, t_ms):
        """A dot a racer, last place first so the leaders are on top, the
        leader's ringed in gold, and the player's head over everything."""
        t = ui.THEME
        by_place = sorted(race['racers'], key=lambda r: -(r['place'] or 99))
        me = None
        for r in by_place:
            px, py = to(*self.motion.at(r['slot'], t_ms))
            px, py = round(px), round(py)
            if r['player']:
                me = (r, px, py)
                continue
            self._dot(canvas, r, px, py, 3, ring=PLACE_COLORS[1] if r['place'] == 1 else None)
            if r['place']:
                self.mini.draw(canvas, str(r['place']), (px + 5, py - 6), (255, 255, 255), TRACK_EDGE)
        if me:
            r, px, py = me
            head = self.art.head(r.get('character')) if self.art else None
            if head:
                ring = PLACE_COLORS[1] if r['place'] == 1 else t['text_light']
                pygame.draw.circle(canvas, TRACK_EDGE, (px, py), 9)
                pygame.draw.circle(canvas, ring, (px, py), 8, 1)
                canvas.blit(head, (px - head.get_width() // 2, py - head.get_height() // 2))
            else:
                self._dot(canvas, r, px, py, 4, ring=PLACE_COLORS[1] if r['place'] == 1 else t['text_light'])

    # -- right: the player's race -------------------------------------------------

    def _race(self, canvas, race):
        t = ui.THEME
        x, y, w, _ = RIGHT
        ui.panel(canvas, (x, y, w, RACE_H))
        place = race.get('place')
        ui.chip(canvas, self.mini, x + 5, y + 5, "PLACE", PLACE_COLORS.get(place, (104, 120, 132)))
        big = self.font.render(ordinal(place), PLACE_COLORS.get(place, t['text']) if place in PLACE_COLORS
                               else t['text'], t['text_shadow'])
        big = pygame.transform.scale(big, (big.get_width() * 2, big.get_height() * 2))
        if place in PLACE_COLORS:      # (its outline, so the gold and silver read on the panel)
            edge = self.font.render(ordinal(place), ui.darken(PLACE_COLORS[place], 90))
            edge = pygame.transform.scale(edge, (edge.get_width() * 2, edge.get_height() * 2))
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                canvas.blit(edge, (x + w - 5 - big.get_width() + ox, y + 4 + oy))
        canvas.blit(big, (x + w - 5 - big.get_width(), y + 4))
        laps = race.get('laps') or 3
        lap = max(1, min(laps, race.get('lap') or 1))
        ui.chip(canvas, self.mini, x + 5, y + 27, "LAP", (104, 120, 132))
        text = "FINISH" if race.get('finished') else f"{lap}/{laps}"
        self.font.draw(canvas, text, (x + w - 5, y + 26), t['text'], t['text_shadow'], align='right')
        pygame.draw.line(canvas, t['panel_lo'], (x + 5, y + 39), (x + w - 6, y + 39))
        self.mini.draw(canvas, "TIME", (x + 5, y + 44), t['ach_lo'])
        self.font.draw(canvas, race_time(race.get('time_ms')), (x + w - 5, y + 50), t['text'], t['text_shadow'],
                       align='right')
