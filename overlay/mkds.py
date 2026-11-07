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
              by) it's the line alone. With the course's heights
              (core/mkds_maps.py's HEIGHTS) it's voxel terrain instead,
              circled by a broadcast camera, the racers standing on it at
              their real height (overlay/mkds_voxel.py, at the window's
              resolution), cutting to a camera behind the player for a few
              seconds when a rival's right on them or the last lap starts
              (CutDirector); until that's ready, tilted in 2.5D with a strip
              of the lap's heights under it (overlay/mkds_tilt.py). Where the
              course crosses over itself
              (a bridge, a loop: core/mkds_maps.py's DECKS), the racers on
              the upper deck are drawn over a see-through copy of the upper
              road, and the ones below under it, so they pass underneath.
    right     the item you hold (the game's icon for it, with how many; an
              empty box with none), the lap, in a Grand Prix your points in
              the cup, the race's time, then achievements as in the Tetris
              view. (Your place is in the ranking, and only there.)

A racer whose character isn't known shows as a dot in a colour of its own
with its number. Outside a race (the menus, Battle, Missions) the game card
shows instead.
"""

import math

import pygame

from core.mkds_maps import DECKS, HEIGHTS, MAPS
from core.mkds_reader import COURSES, midpoints, short_name

from . import ui
from .gamecard import FOOTER_Y, HEADER_H, W
from .mkds_tilt import FLAT_BELOW, HeightStrip, TiltedCourse, usable
from .mkds_voxel import SCALE as VOXEL_SCALE
from .mkds_voxel import VoxelCourse, map_colours
from .tetris import BOARD_BG, BOARD_FRAME, BOARD_GRID, TetrisView

TOP = HEADER_H + 2
HEIGHT = FOOTER_Y - HEADER_H - 4
RANK = (3, TOP, 66, HEIGHT)                  # the racers in order
MAP = (72, TOP, 104, HEIGHT)                 # the course
RIGHT = (179, TOP, W - 3 - 179, HEIGHT)      # place, lap, achievements
RACE_H = 66                                  # the item, lap and time panel's height
ITEM_BOX = 24, 20                            # the item's box
ROW_H = 17
STRIP_H = 9                                  # the map panel's course name and mode strips

SLIDE_MS = 300                               # a row's slide to its new place
MAP_DIM = 0.45                               # the map under the line, this much darker
TILT_DIM = 0.6                               # ... and as the tilted view's ground (the road's raised off it)
MATCH_WITHIN = 60.0                          # world units: the console's finish line this near the map's
DECK_ALPHA = 170                             # the upper deck's road over the racers below it (of 255)
DECK_WIDTH = 1.2                             # ... that many times a deck's reach wide
STRIP_GAP = 2                                # between the tilted map and the height strip under it
STRIP_H_PX = 26                              # the height strip's height
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
EDGE_SHADOW = (8, 10, 14)
DECK_VOXEL_ALPHA = 200                       # the voxel course's upper decks, over the racers below
CUT_FADE_MS = 350                            # the wipe into the chase camera and back out
CHIP = (240, 196, 48)                        # "BATTLE FOR 3RD", in the mode's strip during a battle
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
        self.was = {slot: self.at3(slot, t_ms) for slot in self.now}
        self.now = {r['slot']: (r['x'], r['z'], r.get('y')) for r in race['racers']}
        self.arrived = t_ms

    def at3(self, slot, t_ms):
        """(x, z, height) where the racer's drawn now (height None when the read has none)."""
        x, z, y = self.now[slot]
        if slot not in self.was:
            return x, z, y
        f = min(1.0, (t_ms - self.arrived) / self.interval)
        wx, wz, wy = self.was[slot]
        y = y if y is None or wy is None else wy + (y - wy) * f
        return wx + (x - wx) * f, wz + (z - wz) * f, y

    def at(self, slot, t_ms):
        return self.at3(slot, t_ms)[:2]


class CutDirector:
    """When the voxel course's broadcast camera cuts to the chase camera
    behind the player, as a race on TV cuts to a battle:

      - a battle: a racer a place ahead or behind within BATTLE_GAP
        checkpoints of the player, for BATTLE_HOLD_MS without a break
        (so a pass that's over at once doesn't start one);
      - the last lap starting (whatever the cooldown; one under way runs
        on at least LAST_LAP_MS more, and none starts if one ended less than
        LAST_LAP_AFTER_MS before: the FINAL LAP banner has it then).

    A cut lasts CUT_MS, and another battle can't start one until COOLDOWN_MS
    after it ends, so it can't flick between the two. update() each frame
    with the race and the time; then `cut` is None (the broadcast camera) or
    {'kind': 'battle' or 'last lap', 'rival': slot or None, 'for': place,
    'start': t_ms, 'end': t_ms}."""

    BATTLE_GAP = 0.6
    BATTLE_HOLD_MS = 800
    CUT_MS = 7000
    LAST_LAP_MS = 4000
    LAST_LAP_AFTER_MS = 3000
    COOLDOWN_MS = 18000

    def __init__(self):
        self.cut = None
        self.last = None             # (the cut that ended, when): for the wipe out
        self.ready_at = 0            # no battle cut before this (the cooldown)
        self.close = None            # (rival slot, since t_ms) while a battle's building
        self.lap = None

    def rival(self, race):
        """(the slot, how many checkpoints apart) of the racer a place either
        side of the player that's nearest them, or None."""
        me = next((r for r in race['racers'] if r['player']), None)
        if not me or me['place'] is None:
            return None
        best = None
        for r in race['racers']:
            if r['player'] or r['place'] is None or abs(r['place'] - me['place']) != 1:
                continue
            gap = abs(r['progress'] - me['progress'])
            if best is None or gap < best[1]:
                best = (r['slot'], gap)
        return best

    def update(self, race, t_ms):
        if self.cut and t_ms >= self.cut['end']:
            self.last, self.cut = (self.cut, t_ms), None
            self.ready_at = t_ms + self.COOLDOWN_MS
        laps, lap = race.get('laps') or 3, race.get('lap')
        if self.lap is not None and lap is not None and self.lap < laps <= lap and laps > 1 and not race.get('finished'):
            near = self.rival(race)
            if self.cut:
                self.cut['end'] = max(self.cut['end'], t_ms + self.LAST_LAP_MS)
            elif self.last and t_ms - self.last[1] < self.LAST_LAP_AFTER_MS:
                pass                                       # (just back from one: no flick)
            else:
                self._start('last lap', near[0] if near and near[1] < 2 * self.BATTLE_GAP else None, race, t_ms)
        self.lap = lap
        near = self.rival(race)
        if not near or near[1] > self.BATTLE_GAP:
            self.close = None
        elif not self.close or self.close[0] != near[0]:
            self.close = (near[0], t_ms)
        if (not self.cut and self.close and t_ms >= self.ready_at
                and t_ms - self.close[1] >= self.BATTLE_HOLD_MS):
            self._start('battle', self.close[0], race, t_ms)
        return self.cut

    def _start(self, kind, rival, race, t_ms):
        places = [r['place'] for r in race['racers'] if r['player'] or r['slot'] == rival]
        self.cut = {'kind': kind, 'rival': rival, 'for': min(p for p in places if p) if places else None,
                    'start': t_ms, 'end': t_ms + self.CUT_MS}
        self.close = None

    def wipe(self, t_ms):
        """How far a wipe is (0-1, revealing the camera it's going to), and
        which way: (progress, True going in to the chase camera / False out),
        or None when there's none."""
        if self.cut and t_ms - self.cut['start'] < CUT_FADE_MS:
            return (t_ms - self.cut['start']) / CUT_FADE_MS, True
        if self.last and t_ms - self.last[1] < CUT_FADE_MS:
            return (t_ms - self.last[1]) / CUT_FADE_MS, False
        return None


class MkdsView:
    def __init__(self, font, mini, card, art=None, hires=None):
        """card: the game card (overlay/gamecard.py), for the header and
        footer. art: an MkdsArt (overlay/mkds_art.py), or None to draw
        without the game's art. hires: the overlay's blit_hires, to show the
        voxel course at the window's resolution (else it's shrunk onto the
        canvas)."""
        self.font = font
        self.mini = mini
        self.card = card
        self.art = art
        self.ranks = RankMotion()
        self.motion = MapMotion()
        self._view = None   # (key, the course's world window, scale, mirror or None)
        self._deck = None   # (key, the upper decks' road, cut from the map: drawn over the racers below)
        self._tilt = None   # (key, TiltedCourse, HeightStrip or None) for the course in 2.5D
        self.hires = hires
        self.voxel = True        # the voxel course when it can be (False: the 2.5D one)
        self.voxel_sync = False  # make it as it's asked for, not on a thread (pictures, tests)
        self._voxel = None       # (key, VoxelCourse)
        self._vox_frame = None   # the voxel frame being drawn on
        self._vox_sprites = {}
        self.cuts = CutDirector()
        self._heading = None     # the chase camera's heading (radians), eased toward the road's

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
        fx, fz = MAPS[course_file][4]
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
        if self.voxel and self._voxel_view(canvas, race, inner, t_ms):
            return
        if self._tilted(canvas, race, inner, t_ms):
            return
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
        decks = self.decks(race, mirror)
        patch = self._deck_patch(canvas, inner, decks, to, scale, (race['course'], inner.size, window, mirror, turn,
                                                                    bool(backdrop)))
        self._markers(canvas, race, to, t_ms, decks, patch, inner.topleft)
        canvas.set_clip(clip)

    # -- the course as voxel terrain (overlay/mkds_voxel.py) -------------------------

    def _voxel_view(self, canvas, race, inner, t_ms):
        """Draws the voxel course, if it can be (as the tilted view: its
        heights, a course that matches its file) and it's ready: True when
        it did."""
        cps = race.get('checkpoints') or ()
        course_file = COURSES[race['course']][1]
        heights = HEIGHTS.get(course_file)
        if not usable(cps, heights):
            return False
        mirror = self._mirror(race)
        if mirror is None:
            return False
        key = (race['course'], len(cps), mirror, inner.size)
        if not self._voxel or self._voxel[0] != key:
            colours = map_colours(self.art, course_file, mirror)
            if colours is None and self.art and self.art.pending():
                return False                            # (its map's on its way)
            if self._voxel:
                self._voxel[1].close()
            course = VoxelCourse(cps, heights, inner.size, self.decks(race, mirror), colours,
                                 threaded=not self.voxel_sync)
            self._voxel = (key, course)
        course = self._voxel[1]
        if course.failed:
            return False
        got = course.frame(t_ms)
        if got is None:
            return False
        cut = self.cuts.update(race, t_ms)
        wipe = self.cuts.wipe(t_ms)
        if self._vox_frame is None or self._vox_frame.get_size() != got[0].get_size():
            self._vox_frame = pygame.Surface(got[0].get_size())
            self._vox_other = pygame.Surface(got[0].get_size())
        work = self._vox_frame
        chase = cut or (wipe and not wipe[1])          # (the chase camera: in a cut, and wiping out of one)
        if chase:
            self._compose(work, race, course, self._chase(race, course, cut or self.cuts.last[0], t_ms), t_ms)
        else:
            self._heading = None
            self._compose(work, race, course, got, t_ms)
        if wipe:                                       # (the other camera, bars of it giving way)
            other = self._vox_other
            self._compose(other, race, course, got if chase else
                          self._chase(race, course, cut, t_ms), t_ms)
            progress, going_in = wipe
            self._bars(work, other, progress)
        if self.hires:
            self.hires(canvas, work, inner, inner, live=True)
        else:
            canvas.blit(pygame.transform.smoothscale(work, inner.size), inner.topleft)
        if cut and cut['kind'] == 'battle' and cut['for']:
            self._chip(canvas, f"BATTLE FOR {ordinal(cut['for']).upper()}")
        return True

    def _compose(self, surf, race, course, got, t_ms):
        frame, view = got
        surf.blit(frame, (0, 0))
        self._voxel_racers(surf, race, course, view, t_ms)

    def _chase(self, race, course, cut, t_ms):
        """The chase camera's frame: behind the player, looking along the
        road (the heading eased toward it), back far enough for the rival."""
        me = next(r for r in race['racers'] if r['player'])
        x, z, y = self.motion.at3(me['slot'], t_ms)
        mids = course.mids
        n = len(mids)
        cp = me['checkpoint'] % n
        (ax, az), (bx, bz), (cx, cz) = mids[cp], mids[(cp + 1) % n], mids[(cp + 2) % n]
        seg = math.hypot(bx - ax, bz - az) or 1.0
        t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / seg / seg))
        hx, hz = (bx - ax) / seg * (1 - t) + (cx - bx) * t / (math.hypot(cx - bx, cz - bz) or 1.0), \
            (bz - az) / seg * (1 - t) + (cz - bz) * t / (math.hypot(cx - bx, cz - bz) or 1.0)
        want = math.atan2(hz, hx)
        if self._heading is None:
            self._heading = want
        else:
            turn = (want - self._heading + math.pi) % (2 * math.pi) - math.pi
            self._heading += turn * 0.15
        rival = None
        if cut and cut.get('rival') is not None and cut['rival'] in self.motion.now:
            rival = self.motion.at3(cut['rival'], t_ms)
        view = course.chase_view(x, z, y if y is not None else course.base, self._heading, rival)
        return course.chase_frame(view, t_ms)          # (the frame, and the view it was drawn in)

    @staticmethod
    def _bars(work, other, progress):
        """The overlay's wipe (ui.wipe), as a cut: bars from either side,
        alternately, covering `work` with `other` as progress goes 0 to 1."""
        w, h = work.get_size()
        bars = 8
        bh = h // bars + 1
        cover = int(w * (1 - ui.ease_out(min(1.0, progress))))
        for i in range(bars):
            area = (w - cover, i * bh, cover, bh) if i % 2 == 0 else (0, i * bh, cover, bh)
            work.blit(other, area[:2], area)

    def _chip(self, canvas, text):
        """The mode's strip under the map, saying what the cut's for."""
        x, y, w, h = MAP
        strip = (x + 2, y + h - 2 - STRIP_H, w - 4, STRIP_H)
        pygame.draw.rect(canvas, ui.darken(CHIP, 150), strip)
        self.mini.draw(canvas, self.mini.fit(text, w - 8), (x + w // 2, y + h - 2 - STRIP_H + 2), CHIP,
                       align='center')

    def _voxel_racers(self, surf, race, course, view, t_ms):
        """The racers on the voxel course: the ones below the upper decks,
        the decks over them (see-through), the ones on top; far first in
        each, the player last."""
        up = {r['slot'] for r in race['racers'] if course.decks and self.upper(dict(r, **self._live(r, t_ms)),
                                                                               course.decks)}
        placed = []
        for r in race['racers']:
            x, z, y = self.motion.at3(r['slot'], t_ms)
            sx, sy, d = course.place(x, z, y, view)
            if d <= 1:
                continue                                   # (behind the camera)
            gx, gy, _ = course.place(x, z, None, view)
            placed.append((r, sx, sy, d, gx, gy, course.hidden(x, z, y, view)))

        me = next((p for p in placed if p[0]['player']), None)
        view_distance = me[3] if me else math.hypot(course.centre[0] - view.x, course.centre[1] - view.z)

        def layer(rows):
            for r, sx, sy, d, gx, gy, hidden in sorted(rows, key=lambda p: (p[0]['player'], -p[3])):
                size = max(0.75, min(1.6, view_distance / d))
                if not hidden:
                    pygame.draw.ellipse(surf, EDGE_SHADOW, (gx - 5 * size, gy - 2 * size, 10 * size, 4 * size))
                    if sy < gy - 4:
                        pygame.draw.line(surf, EDGE_SHADOW, (gx, gy), (sx, sy + 4))
                self._voxel_marker(surf, r, round(sx), round(sy), size, hidden)
        layer([p for p in placed if p[0]['slot'] not in up])
        decks = course.deck_polygons(view)
        if decks:
            over = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            for _, quad, colour in decks:
                pygame.draw.polygon(over, colour + (DECK_VOXEL_ALPHA,), quad)
                pygame.draw.polygon(over, (8, 10, 14, DECK_VOXEL_ALPHA), quad, 1)
            surf.blit(over, (0, 0))
        layer([p for p in placed if p[0]['slot'] in up])

    def _voxel_marker(self, surf, r, sx, sy, size, hidden):
        """A racer on the voxel course, at four times the canvas's pixels: the
        player's head, a dot with its place for the rest; just a ring where
        the ground's in front of it."""
        k = VOXEL_SCALE
        ring = PLACE_COLORS[1] if r['place'] == 1 else None
        if hidden:
            pygame.draw.circle(surf, color_of(r), (sx, sy), round(3 * k * size), 1)
            return
        if r['player']:
            head = self.art.head(r.get('character')) if self.art else None
            if head:
                hw, hh = head.get_size()
                key = (r.get('character'), k)           # (at the frame's own scale: 1:1 with the ranking's heads)
                big = self._vox_sprites.get(key)
                if big is None:
                    big = self._vox_sprites[key] = pygame.transform.scale(head, (hw * k // 2, hh * k // 2))
                bw, bh = big.get_size()
                pygame.draw.circle(surf, EDGE_SHADOW, (sx, sy - bh // 2), max(bw, bh) // 2 + 3)
                pygame.draw.circle(surf, ring or ui.THEME['text_light'], (sx, sy - bh // 2), max(bw, bh) // 2 + 2, 2)
                surf.blit(big, (sx - bw // 2, sy - bh))
                return
        radius = round(3 * k * size * (1.3 if r['player'] else 1))
        pygame.draw.circle(surf, EDGE_SHADOW, (sx, sy - radius), radius + 2)
        if ring:
            pygame.draw.circle(surf, ring, (sx, sy - radius), radius + 1)
        pygame.draw.circle(surf, color_of(r), (sx, sy - radius), radius - (1 if ring else 0))
        if r['place'] and not r['player']:
            label = self._vox_sprites.get(('label', r['place']))
            if label is None:
                small = self.mini.render(str(r['place']), (255, 255, 255), TRACK_EDGE)
                label = self._vox_sprites[('label', r['place'])] = pygame.transform.scale(
                    small, (small.get_width() * k, small.get_height() * k))
            surf.blit(label, (sx + radius + 2, sy - radius * 2 - 4))

    # -- the course in 2.5D (overlay/mkds_tilt.py) --------------------------------------

    def _tilted(self, canvas, race, inner, t_ms):
        """Draws the course tilted with its height strip, if it can be (its
        heights, matching the console's checkpoints, and a course that
        matches its file): True when it did."""
        cps = race.get('checkpoints') or ()
        course_file = COURSES[race['course']][1]
        heights = HEIGHTS.get(course_file)
        if not usable(cps, heights):
            return False
        mirror = self._mirror(race)
        if mirror is None:
            return False
        key = (race['course'], len(cps), mirror, inner.size)
        if not self._tilt or self._tilt[0] != key:
            decks = self.decks(race, mirror)
            strip = None
            map_h = inner.h
            if max(heights) - min(heights) >= FLAT_BELOW:
                map_h = inner.h - STRIP_H_PX - STRIP_GAP
                strip = HeightStrip(cps, heights, (inner.w, STRIP_H_PX)).build()
            course = TiltedCourse(cps, heights, (inner.w, map_h), decks, self.upper)
            ground = None
            if self.art:
                ground = self.art.course_map(course_file, course.window(), course.size, mirror, TILT_DIM, course.turn)
                if ground is None and self.art.pending():
                    course.build(None)                  # (the map's on its way: this once without it)
                    self._draw_tilted(canvas, race, inner, course, strip, t_ms)
                    return True
            self._tilt = (key, course.build(ground), strip)
        _, course, strip = self._tilt
        self._draw_tilted(canvas, race, inner, course, strip, t_ms)
        return True

    def _draw_tilted(self, canvas, race, inner, course, strip, t_ms):
        clip = canvas.get_clip()
        canvas.set_clip(inner)
        canvas.blit(course.ground, inner.topleft)
        decks = course.decks
        up = {r['slot'] for r in race['racers'] if decks and self.upper(dict(r, **self._live(r, t_ms)), decks)}

        def layer(racers):
            placed = []
            for r in racers:
                x, z, y = self.motion.at3(r['slot'], t_ms)
                (px, py), (gx, gy) = course.racer_point(x, z, y)
                placed.append((py, r, (round(inner.x + px), round(inner.y + py)), (round(inner.x + gx), round(inner.y + gy))))
            placed.sort(key=lambda p: (p[1]['player'], p[0]))          # (far first, the player last)
            for _, r, (px, py), (gx, gy) in placed:
                pygame.draw.ellipse(canvas, TRACK_EDGE, (gx - 3, gy - 1, 7, 3))
                if py < gy - 3:
                    pygame.draw.line(canvas, TRACK_EDGE, (gx, gy), (px, py + 2))
                self._marker(canvas, r, px, py)
        layer([r for r in race['racers'] if r['slot'] not in up])
        if course.bridges is not None:
            canvas.blit(course.bridges, inner.topleft)
        layer([r for r in race['racers'] if r['slot'] in up])
        canvas.set_clip(clip)
        if strip:
            sx, sy = inner.x, inner.bottom - strip.size[1]
            canvas.blit(strip.surface, (sx, sy))
            for r in sorted(race['racers'], key=lambda r: (r['player'], -(r['place'] or 99))):
                x, z, y = self.motion.at3(r['slot'], t_ms)
                px, py = strip.place(x, z, r['checkpoint'], y)
                px, py = round(sx + px), round(sy + py)
                if r['player']:
                    pygame.draw.circle(canvas, TRACK_EDGE, (px, py), 4)
                    pygame.draw.circle(canvas, (255, 255, 255), (px, py), 3)
                    pygame.draw.circle(canvas, color_of(r), (px, py), 2)
                else:
                    pygame.draw.circle(canvas, TRACK_EDGE, (px, py), 3)
                    pygame.draw.circle(canvas, PLACE_COLORS[1] if r['place'] == 1 else color_of(r), (px, py), 2)

    def _live(self, racer, t_ms):
        x, z, y = self.motion.at3(racer['slot'], t_ms)
        return {'x': x, 'z': z, 'y': y}

    def _marker(self, canvas, r, px, py):
        """A racer on the map: its dot and place, or the player's head."""
        t = ui.THEME
        if r['player']:
            head = self.art.head(r.get('character')) if self.art else None
            if head:
                ring = PLACE_COLORS[1] if r['place'] == 1 else t['text_light']
                pygame.draw.circle(canvas, TRACK_EDGE, (px, py), 9)
                pygame.draw.circle(canvas, ring, (px, py), 8, 1)
                canvas.blit(head, (px - head.get_width() // 2, py - head.get_height() // 2))
            else:
                self._dot(canvas, r, px, py, 4, ring=PLACE_COLORS[1] if r['place'] == 1 else t['text_light'])
            return
        self._dot(canvas, r, px, py, 3, ring=PLACE_COLORS[1] if r['place'] == 1 else None)
        if r['place']:
            self.mini.draw(canvas, str(r['place']), (px + 5, py - 6), (255, 255, 255), TRACK_EDGE)

    @staticmethod
    def decks(race, mirror):
        """The course's DECKS as the console has it (x the other way when
        `mirror`), or () (none, or a course that doesn't match its file)."""
        if mirror is None:
            return ()
        found = DECKS.get(COURSES[race['course']][1], ())
        if not mirror:
            return found
        return tuple((-x, z, reach, low, high, tuple((-px, pz) for px, pz in upper))
                     for x, z, reach, low, high, upper in found)

    @staticmethod
    def upper(racer, decks):
        """True when the racer is on an upper deck: near where the course
        crosses over itself, and nearer the upper height than the lower."""
        y = racer.get('y')
        if y is None:
            return False
        return any(math.hypot(racer['x'] - x, racer['z'] - z) <= reach and abs(y - high) < abs(y - low)
                   for x, z, reach, low, high, _ in decks)

    def _deck_patch(self, canvas, inner, decks, to, scale, key):
        """The upper decks' road as the panel has it so far (the map and the
        line, no racers), see-through, cut along each upper path a road wide:
        drawn over the racers below. Made once a view."""
        if not decks:
            return None
        if self._deck and self._deck[0] == key:
            return self._deck[1]
        base = canvas.subsurface(inner).copy().convert_alpha()
        mask = pygame.Surface(inner.size, pygame.SRCALPHA)
        for _, _, reach, _, _, path in decks:
            pts = [(px - inner.x, py - inner.y) for px, py in (to(wx, wz) for wx, wz in path)]
            width = max(3, round(reach * DECK_WIDTH * scale))
            if len(pts) > 1:
                pygame.draw.lines(mask, (255, 255, 255, DECK_ALPHA), False, pts, width)
            for p in (pts[0], pts[-1]):
                pygame.draw.circle(mask, (255, 255, 255, DECK_ALPHA), p, width // 2)
        base.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._deck = (key, base)
        return base

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

    def _markers(self, canvas, race, to, t_ms, decks=(), patch=None, at=(0, 0)):
        """A dot a racer, last place first so the leaders are on top, the
        leader's ringed in gold, and the player's head over the others. With
        decks, in two layers: the racers below, then the upper decks' road
        (`patch`), then the racers up there."""
        up = {r['slot'] for r in race['racers'] if decks and self.upper(r, decks)}
        below = [r for r in race['racers'] if r['slot'] not in up]
        self._layer(canvas, below, to, t_ms)
        if patch is not None:
            canvas.blit(patch, at)
        self._layer(canvas, [r for r in race['racers'] if r['slot'] in up], to, t_ms)

    def _layer(self, canvas, racers, to, t_ms):
        """Racers last place first, so the leaders are on top, and the player last."""
        for r in sorted(racers, key=lambda r: (r['player'], -(r['place'] or 99))):
            px, py = to(*self.motion.at(r['slot'], t_ms))
            self._marker(canvas, r, round(px), round(py))

    # -- right: the player's race -------------------------------------------------

    def _race(self, canvas, race):
        t = ui.THEME
        x, y, w, _ = RIGHT
        ui.panel(canvas, (x, y, w, RACE_H))
        ui.chip(canvas, self.mini, x + 5, y + 7, "ITEM", (104, 120, 132))
        self._item(canvas, race.get('item'), x + w - 5 - ITEM_BOX[0], y + 3)
        laps = race.get('laps') or 3
        lap = max(1, min(laps, race.get('lap') or 1))
        ui.chip(canvas, self.mini, x + 5, y + 28, "LAP", (104, 120, 132))
        text = "FINISH" if race.get('finished') else f"{lap}/{laps}"
        self.font.draw(canvas, text, (x + w - 5, y + 27), t['text'], t['text_shadow'], align='right')
        if race.get('cup_points') is not None:
            ui.chip(canvas, self.mini, x + 5, y + 40, "CUP", PLACE_COLORS[1])
            self.font.draw(canvas, f"{race['cup_points']} PTS", (x + w - 5, y + 39), t['text'], t['text_shadow'],
                           align='right')
        pygame.draw.line(canvas, t['panel_lo'], (x + 5, y + 51), (x + w - 6, y + 51))
        self.mini.draw(canvas, "TIME", (x + 5, y + 57), t['ach_lo'])
        self.font.draw(canvas, race_time(race.get('time_ms')), (x + w - 5, y + 55), t['text'], t['text_shadow'],
                       align='right')

    def _item(self, canvas, item, bx, by):
        """The item held in its box (empty with none): the game's icon, and
        how many (x2, x3) when the icon doesn't show it already."""
        bw, bh = ITEM_BOX
        ui.panel(canvas, (bx, by, bw, bh), fill=BOARD_BG, border=BOARD_FRAME, hi=BOARD_GRID, lo=ui.darken(BOARD_BG, 6))
        if not item:
            return
        icon, counted = self.art.item(item['name'], item['count']) if self.art else (None, False)
        cx, cy = bx + bw // 2, by + bh // 2
        if icon:
            canvas.blit(icon, (cx - icon.get_width() // 2, cy - icon.get_height() // 2))
        else:            # (the Fake Item Box, or no sheet: a box with a ?, as the game's item boxes)
            pygame.draw.rect(canvas, (232, 72, 56), (cx - 6, cy - 6, 12, 12))
            pygame.draw.rect(canvas, (255, 255, 255), (cx - 6, cy - 6, 12, 12), 1)
            self.font.draw(canvas, "?", (cx + 1, cy - 4), (255, 255, 255), TRACK_EDGE, align='center')
        if item['count'] > 1 and not counted:
            self.mini.draw(canvas, f"x{item['count']}", (bx + bw - 1, by + bh - 7), (255, 255, 255), TRACK_EDGE,
                           align='right')
