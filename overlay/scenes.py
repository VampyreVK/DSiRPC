"""
scenes.py - what the overlay draws on its 256x192 canvas:

    party view    header (location, playtime), the six party slots, footer
                  (trainer, badges, Pokedex)
    battle view   sky and ground, platforms, the foe and your Pokemon, their
                  HP boxes and a message box
    Unova view    Pokemon Black and White's main view (overlay/unova.py):
                  the party in the games' own panels, the achievements, the
                  trainer and badges; their battles use the battle view
                  with the games' own backgrounds
    game card     any other game (overlay/gamecard.py): its name, its
                  RetroAchievements rich presence and achievement progress,
                  laid out like the party view
    waiting view  shown while the DSi isn't sending data: what to do, and the
                  last game played
    toasts        short banners for events (shiny, level up, fainted, ...)

The Overlay object keeps the animation state (HP bars sliding to their new
value, the battle transition, the toast queue) between frames.

Moves used in battle are worked out from PP: when one of a battler's moves
loses PP between two reads, that battler just used it. The game takes the
PP when the move starts and the HP only after its animation, which can be
a read or two later, so a damaging move is held back until the target's HP
drops and then plays together with the hit. Held moves play in the order
they happened (see _play_ready): by the read they were seen in, and within
one read by who must have gone first (a Pokemon that fainted moved before
the hit that knocked it out), then by move priority and speed. The game's own
"last move used" record (the parser's last_move) is only trusted as a
backup after it has agreed with the PP twice, since it has only been
checked on hardware for your side so far.
"""

import math

import pygame

from core import bw_data
from core import platinum_data as pdata
from . import markers, ui
from .backdrop import Backdrop, period, terrain, weather_kind
from .effects import Effect
from .font import PixelFont
from .gamecard import GameCard
from .sprites import DIORAMA_BOTTOM, DIORAMA_CENTER_X
from .unova import DOUBLES_DROP, TITLES, TRAINER_MS, UnovaScreen
from .unova_art import UnovaArt

W, H = 256, 192
HEADER_H = 16
FOOTER_Y = 162
SLOT_W, SLOT_H = 124, 46
SLOT_POS = [(3, 18), (129, 18), (3, 66), (129, 66), (3, 114), (129, 114)]

WILD, GYM, TRAINER, CHAMPION, RIVAL, ELITE_FOUR = 0x45C, 0x45D, 0x45F, 0x462, 0x464, 0x470

TOAST_MS = 3500
WIPE_MS = 700

# Move types, categories and PP: Black and White's table holds every Gen IV
# move as Platinum's does, plus Gen V's.
MOVE_INFO = bw_data.MOVE_INFO


def _upper(name):
    return (name or '').upper()


def _facing(d):
    raw = d.get('direction_raw')
    if raw is not None and (raw & 0xFF) < 4:
        return pdata.DIRECTIONS[raw & 0xFF]
    return d['location'].get('facing') or 'down'


def _ident(m):
    return m['species_id'], m['nickname']


def _speed(m):
    """Speed with its stat stage (0-12, 6 = no change) and paralysis."""
    stage = m.get('speed_stage', 6)
    mult = (2 + stage - 6) / 2 if stage >= 6 else 2 / (2 + 6 - stage)
    return m.get('speed', 0) * mult * (0.25 if m.get('status') == 'Paralyzed' else 1)


def _effectiveness(mtype, foe):
    """The type multiplier of a `mtype` move against `foe` (from its types;
    abilities like Levitate aren't counted). None if unknown."""
    if not mtype or not foe or not foe.get('types'):
        return None
    mult = 1
    identified = 'Identified' in (foe.get('conditions') or [])
    for t in foe['types']:
        if identified and (mtype, t) in pdata.FORESIGHT_IGNORES:
            continue
        mult *= pdata.TYPE_CHART.get((mtype, t), 1)
    return mult


def _opponent(d):
    """(wild, trainer name or None). The parser's `wild` flag (the foe has
    the player's trainer ID) decides; without it, the battle music does when
    it can, since the trainer class read can be unknown ('sprite 0x..')."""
    name = d['battle'].get('trainer')
    name = _upper(name) if name and not name.startswith('sprite') else None
    if 'wild' in d['battle']:
        wild = bool(d['battle']['wild'])
        return wild, None if wild else name
    music = d['misc'].get('music_id')
    if music == WILD:
        return True, None
    if music in (GYM, TRAINER, CHAMPION, RIVAL, ELITE_FOUR):
        return False, name
    return name is None, name


class Overlay:
    def __init__(self, sprites):
        self.sprites = sprites
        self.font = PixelFont()
        self.mini = PixelFont(mini=True)
        self.card = GameCard(self.font, self.mini)
        self.unova = UnovaScreen(self, UnovaArt(sprites.assets))
        self.hp_shown = {}         # key -> displayed HP (float), slides toward the real value
        self.toasts = []           # [text, started_ms or None, sparkly]
        self.view = 'auto'         # 'auto', 'party' or 'battle' (V key in the window)
        self.showing_battle = False
        self.wipe_start = None
        self.walk_until = 0
        self.last_pos = None
        self.shiny_intro_until = 0
        self._scaled = {}
        # Window-resolution sprites (see blit_hires): app.py sets hires_ok
        # when it composites them, they're queued in `hires` each frame, and
        # what's drawn after lift() goes on `layer`, above them.
        self.hires_ok = False
        self.hires = []
        self.layer = None
        self._over = None
        self._over_big = None
        self._sharp = {}
        self.backdrop = Backdrop()
        self.battle_since = None   # when the battle view appeared (intro slide-in)
        self.battlers = {}         # 'foe0' / 'foe1' / 'you0' / 'you1' -> animation state
        self.msg = None            # (line 1, line 2, until_ms) for the message box
        self.effects = []          # move animations playing (effects.Effect)
        self.boxes = {}            # battler key -> where its sprite was drawn this frame
        self.last_move_agreed = 0  # times the game's last-move record matched a PP drop
        self.msg_queue = []        # (from_ms, line 1, line 2): messages waiting their turn
        self.next_msg_at = 0       # things seen in the same read play one after another
        self.held = []             # moves seen (PP spent) that haven't played yet
        self.seq = 0               # order moves were seen in
        self.intro_until = 0       # the intro message follows the data until then
        self.read_at = None        # when the data being drawn was read (Snapshot.updated)
        self.unova_battle = False  # the battle being drawn is Black or White's (their HUD)
        self.trainer_intro = None  # Black and White: the leader shown at the start ({} for none)
        self.caught_at = None      # Black and White: when the foe was caught (its ball animation)

    # -- state -----------------------------------------------------------------

    def handle_events(self, events, t_ms):
        for e in events:
            kind = e['type']
            if kind == 'online':
                self.toast("DSi connected!")
            elif kind == 'offline':
                self.toast("Lost the DSi...")
            elif kind == 'shiny_encounter':
                self.toast(f"A shiny {_upper(e['mon']['species'])} appeared!", sparkly=True)
                self.shiny_intro_until = t_ms + 2500
            elif kind == 'level_up':
                self.toast(f"{e['mon']['nickname']} grew to Lv. {e['mon']['level']}!")
            elif kind == 'fainted' and not self.showing_battle:  # battles say it in the message box
                self.toast(f"{e['mon']['nickname']} fainted!")
            elif kind == 'badge_earned':
                self.toast(f"Got the {e['badges'][-1]} Badge!", sparkly=True)
            elif kind == 'dex_caught':
                self.toast(f"Pokédex: {e['caught']} caught!")
            elif kind == 'game_changed':
                self.toast(self._fit_line(f"Now playing {e['title']}", W - 24))
            elif kind == 'achievement':
                self.toast(self._fit_line(f"Achievement: {e['title']}", W - 40), sparkly=True)
            elif kind == 'caught':
                name = _upper((e.get('mon') or {}).get('nickname') or 'the Pokémon')
                self.toast(self._fit_line(f"Gotcha! {name} was caught!", W - 40), sparkly=True)
                self.caught_at = t_ms

    def _fit_line(self, text, width):
        """`text`, cut with … so it's at most `width` pixels wide."""
        return self.font.fit(text, width)

    def toast(self, text, sparkly=False):
        if len(self.toasts) < 6:
            self.toasts.append([text, None, sparkly])

    def _hp(self, key, real, max_hp, dt_ms):
        """Slides the displayed HP toward the real value, about a full bar in 1.2 s."""
        shown = self.hp_shown.get(key)
        if shown is None or abs(shown - real) > max_hp:
            shown = float(real)
        step = max_hp / 1200.0 * dt_ms
        if shown > real:
            shown = max(real, shown - step)
        elif shown < real:
            shown = min(real, shown + step)
        self.hp_shown[key] = shown
        return shown

    # -- frame -----------------------------------------------------------------

    def draw(self, canvas, snap, t_ms, dt_ms):
        self.hires, self.layer = [], None
        d = snap.state if snap.online else None
        self.read_at = snap.updated
        other = bool(d) and d.get('kind') == 'other'
        in_battle = bool(d and not other and d['battle']['active'])
        want_battle = in_battle if self.view == 'auto' else (self.view == 'battle' and in_battle)

        # Battle transition: bars close, the view switches, bars open.
        if want_battle != self.showing_battle and self.wipe_start is None:
            self.wipe_start = t_ms
        wipe = None
        if self.wipe_start is not None:
            p = (t_ms - self.wipe_start) / (WIPE_MS / 2)
            if p >= 1 and want_battle != self.showing_battle:
                self.showing_battle = want_battle
                self.battlers, self.msg, self.effects, self.boxes = {}, None, [], {}
                self.trainer_intro = None
                self.caught_at = None
                self.msg_queue, self.held = [], []
                self.battle_since = t_ms if want_battle else None
                if want_battle:
                    self.intro_until = t_ms + 4500
                    self.msg = (*self._battle_lines(d), self.intro_until)
            if p >= 2:
                self.wipe_start = None
            else:
                wipe = p

        if d is None:
            self.draw_waiting(canvas, snap, t_ms)
        elif other:
            self.card.draw(canvas, d, t_ms)
        elif self.showing_battle and in_battle:
            self.draw_battle(canvas, d, t_ms, dt_ms)
        elif d.get('kind') == 'bw':
            self.unova.draw(canvas, d, t_ms, dt_ms)
        else:
            self.draw_party(canvas, d, t_ms, dt_ms)

        top = self.layer or canvas
        self.draw_toasts(top, t_ms)
        if wipe is not None:
            ui.wipe(top, wipe)

    # -- window-resolution sprites ----------------------------------------------

    def blit_hires(self, canvas, surf, rect, clip=None, dim=False):
        """Draws `surf` shrunk into `rect` (x, y, w, h in canvas pixels),
        clipped to `clip`, greyed if `dim`. When app.py composites the
        window itself (hires_ok) the sprite is queued and drawn at the
        window's resolution instead (see present), so one shown smaller than
        its own pixels keeps its detail; call lift() before drawing anything
        that goes on top of it."""
        clip = pygame.Rect(clip) if clip else canvas.get_clip()
        if self.hires_ok and self.layer is None:
            self.hires.append((surf, rect, clip, dim))
            return
        old = canvas.get_clip()
        canvas.set_clip(clip.clip(old))
        canvas.blit(self._sharp_scale(surf, rect[2:], dim), rect[:2])
        canvas.set_clip(old)

    def lift(self, canvas):
        """The surface to draw what goes above the queued window-resolution
        sprites on: a clear layer of its own when there are any, else
        `canvas` itself."""
        if not self.hires:
            return canvas
        if self._over is None or self._over.get_size() != canvas.get_size():
            self._over = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        self._over.fill((0, 0, 0, 0))
        self.layer = self._over
        return self._over

    def present(self, window, canvas):
        """Scales the frame up into `window`: the canvas, then the queued
        sprites at the window's own resolution, then the layer above them."""
        size = window.get_size()
        pygame.transform.scale(canvas, size, window)
        if not self.hires:
            return
        s = size[0] / canvas.get_width()
        old = window.get_clip()
        for surf, (x, y, w, h), clip, dim in self.hires:
            window.set_clip(pygame.Rect(round(clip.x * s), round(clip.y * s), round(clip.w * s), round(clip.h * s)))
            window.blit(self._sharp_scale(surf, (max(1, round(w * s)), max(1, round(h * s))), dim), (round(x * s), round(y * s)))
        window.set_clip(old)
        if self.layer is not None:
            if self._over_big is None or self._over_big.get_size() != size:
                self._over_big = pygame.Surface(size, pygame.SRCALPHA)
            pygame.transform.scale(self.layer, size, self._over_big)
            window.blit(self._over_big, (0, 0))

    def _sharp_scale(self, surf, size, dim=False):
        """`surf` at `size`: pixels multiplied up to the next whole multiple,
        then smoothed down, so they stay crisp with only their edges blended
        ("sharp bilinear")."""
        key = (id(surf), size, dim)
        out = self._sharp.get(key)
        if out is not None:
            return out
        w, h = surf.get_size()
        if size == (w, h):
            out = surf
        elif size[0] % w == 0 and size[1] % h == 0 and size[0] >= w:
            out = pygame.transform.scale(surf, size)
        else:
            k = max(1, math.ceil(max(size[0] / w, size[1] / h)))
            big = pygame.transform.scale(surf, (w * k, h * k)) if k > 1 else surf
            out = pygame.transform.smoothscale(big, size)
        if dim:
            out = out.copy()
            out.fill((130, 130, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
        if len(self._sharp) > 900:
            self._sharp.clear()
        self._sharp[key] = out
        return out

    # -- helpers ---------------------------------------------------------------

    def _fit(self, surf, max_w, max_h):
        """Halves sprites that don't fit (integer steps only, to keep pixels crisp)."""
        key = (id(surf), max_w, max_h)
        cached = self._scaled.get(key)
        if cached is not None:
            return cached
        out = surf
        while out.get_width() > max_w * 1.25 or out.get_height() > max_h * 1.25:
            out = pygame.transform.scale(out, (max(1, out.get_width() // 2), max(1, out.get_height() // 2)))
        if len(self._scaled) > 600:
            self._scaled.clear()
        self._scaled[key] = out
        return out

    def _name_line(self, canvas, name, gender, x, y, light=False):
        t = ui.THEME
        col, sh = (t['text_light'], t['text_light_shadow']) if light else (t['text'], t['text_shadow'])
        w = self.font.draw(canvas, name, (x, y), col, sh)
        sym, scol = ui.gender_symbol(self.font, gender)
        if sym:
            self.font.draw(canvas, sym, (x + w + 1, y), scol, sh)
        return w

    def _level(self, canvas, level, x, y):
        t = ui.THEME
        self.mini.draw(canvas, "Lv", (x, y + 3), t['text'])
        return 8 + self.font.draw(canvas, str(level), (x + 8, y), t['text'], t['text_shadow'])

    # -- party view ------------------------------------------------------------

    def draw_party(self, canvas, d, t_ms, dt_ms):
        t = ui.THEME
        ui.tiled_background(canvas, t_ms)

        # Header: location and playtime.
        self._bar(canvas, 0, HEADER_H)
        loc = d['location']['name'] or d['location']['area'] or 'Somewhere'
        self.font.draw(canvas, loc, (5, 4), t['text_light'], t['text_light_shadow'])
        pt = d['playtime']
        self.font.draw(canvas, f"{pt['hours']}:{pt['minutes']:02d}", (W - 5, 4), t['text_light'],
                       t['text_light_shadow'], align='right')

        party = d['party']
        for i, (x, y) in enumerate(SLOT_POS):
            if i < len(party):
                self._slot(canvas, party[i], i, x, y, t_ms, dt_ms)
            else:
                self._empty_slot(canvas, x, y)

        self._footer(canvas, d, t_ms)

    def _bar(self, canvas, y, h):
        ui.bar(canvas, y, h)

    def _empty_slot(self, canvas, x, y):
        t = ui.THEME
        c = t['bg_dot'] if not t['chroma'] else (96, 110, 118)
        for xx in range(x + 3, x + SLOT_W - 3, 4):
            canvas.set_at((xx, y), c)
            canvas.set_at((xx, y + SLOT_H - 1), c)
        for yy in range(y + 3, y + SLOT_H - 3, 4):
            canvas.set_at((x, yy), c)
            canvas.set_at((x + SLOT_W - 1, yy), c)

    def _slot(self, canvas, mon, i, x, y, t_ms, dt_ms):
        t = ui.THEME
        egg = mon.get('egg')
        fainted = not egg and mon['curr_hp'] == 0
        if fainted:
            ui.panel(canvas, (x, y, SLOT_W, SLOT_H), fill=t['faint_fill'], lo=t['faint_lo'])
        elif i == 0:
            ui.panel(canvas, (x, y, SLOT_W, SLOT_H), fill=t['lead_fill'], lo=t['lead_lo'], border=t['lead_border'])
        else:
            ui.panel(canvas, (x, y, SLOT_W, SLOT_H))

        # Icon, standing on a little shadow, clipped to the slot.
        icon = None if egg else self.sprites.party_icon(mon['species_id'], mon['shiny'])
        cx, base = x + 24, y + SLOT_H - 5
        pygame.draw.ellipse(canvas, ui.darken(t['panel_lo'] if not fainted else t['faint_lo'], 20),
                            (cx - 14, base - 3, 28, 6))
        if icon:
            frame = self._fit(icon.frame(t_ms + i * 137), 44, 40)
            clip = canvas.get_clip()
            canvas.set_clip((x + 1, y + 2, 47, SLOT_H - 4))
            fx = cx - frame.get_width() // 2
            fy = base - frame.get_height() + (0 if fainted else ui.bob(t_ms + i * 200, 900, 0))
            if fainted:
                frame = frame.copy()
                frame.fill((140, 140, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
            canvas.blit(frame, (fx, fy))
            canvas.set_clip(clip)
        if mon['shiny'] and not egg:
            ui.sparkle(canvas, x + 8, y + 8, t_ms + i * 90)

        tx = x + 48
        name = 'EGG' if egg else mon['nickname']
        self._name_line(canvas, name, None if egg else mon['gender'], tx, y + 5)
        if egg:
            self.font.draw(canvas, "Hatching soon...", (tx, y + 20), t['text'], t['text_shadow'])
            return

        hp = self._hp(('party', i, mon['species_id']), mon['curr_hp'], mon['max_hp'], dt_ms)
        ui.hp_bar(canvas, self.mini, tx, y + 17, 72, hp / max(1, mon['max_hp']))
        lw = self._level(canvas, mon['level'], tx, y + 27)
        status = 'Fainted' if fainted else mon.get('status')
        if status:
            ui.status_tag(canvas, self.mini, tx + lw + 4, y + 27, status)
        self.font.draw(canvas, f"{int(round(hp))}/{mon['max_hp']}", (x + SLOT_W - 5, y + 27),
                       t['text'], t['text_shadow'], align='right')

    def _footer(self, canvas, d, t_ms):
        t = ui.THEME
        self._bar(canvas, FOOTER_Y, H - FOOTER_Y)

        # Your trainer, facing the way you face and walking when you move.
        facing = _facing(d)
        pos = (d['location']['map_id'], d['location']['x'], d['location']['z'], facing)
        if self.last_pos is not None and pos != self.last_pos:
            self.walk_until = t_ms + 700
        self.last_pos = pos
        anim = self.sprites.trainer(d.get('character') or 'Lucas', facing)
        if anim:
            frame = anim.frame(t_ms) if t_ms < self.walk_until else anim.frames[0]
            canvas.blit(frame, (22 - frame.get_width() // 2, H - 3 - frame.get_height()))

        self.font.draw(canvas, d.get('trainer_name') or '', (44, FOOTER_Y + 5), t['text_light'], t['text_light_shadow'])
        for i in range(8):
            ui.badge_pip(canvas, 44 + i * 9, FOOTER_Y + 18, i, pdata.BADGES[i] in d['badges'])

        dex = d['pokedex']
        if dex.get('obtained', True):
            self.mini.draw(canvas, "CAUGHT", (W - 30, FOOTER_Y + 7), t['hp_label'])
            self.font.draw(canvas, str(dex['caught']), (W - 34, FOOTER_Y + 5), t['text_light'],
                           t['text_light_shadow'], align='right')
            self.mini.draw(canvas, "SEEN", (W - 30, FOOTER_Y + 19), t['hp_label'])
            self.font.draw(canvas, str(dex['seen']), (W - 34, FOOTER_Y + 17), t['text_light'],
                           t['text_light_shadow'], align='right')

    # -- battle view -----------------------------------------------------------
    #
    # Layout: the far platform sits on the ground just below the horizon, the
    # near one at the bottom left, half behind the message box. Both
    # Pokemon stand on their platform at the spot process_diorama.py uses
    # for the Discord images.

    FAR_PLATFORM = (190, 106)   # centre x, bottom y
    NEAR_PLATFORM = (70, 162)
    INTRO_MS = 650
    SWITCH_MS = 450
    LUNGE_MS = 300
    HIT_MS = 520
    FAINT_MS = 550
    MSG_MS = 3200
    MOVE_GAP_MS = 1400
    MISS_AFTER_S = 5.0   # a held move whose target hasn't lost HP by then (in read time) plays anyway

    def draw_battle(self, canvas, d, t_ms, dt_ms):
        t = ui.THEME
        b = d['battle']
        unova = d.get('kind') == 'bw'
        self.unova_battle = unova  # Black and White's HUD for the boxes below
        self.unova.now = t_ms
        place = 'field' if unova else terrain(d['location'])
        when = self.unova.time_of_day(d) if unova else period(d['misc'].get('clock'))
        if unova:
            self.unova.draw_backdrop(canvas, d, when, t_ms)
        else:
            self.backdrop.draw(canvas, place, when, t_ms, t['chroma'])

        foes = [m for m in b['mons'] if m['side'].startswith('foe')][:2]
        yours = [m for m in b['mons'] if m['side'].startswith('yours')][:2]
        self._track_battlers(d, foes, yours, t_ms)

        # Intro: each side slides in from its edge with its platform.
        intro = 1.0
        if self.battle_since is not None:
            intro = ui.ease_out(min(1.0, (t_ms - self.battle_since) / self.INTRO_MS))
        far_dx = int((intro - 1) * 200)
        near_dx = int((1 - intro) * 200)

        plat = None if unova else self.sprites.platform(place, when)
        box = self.sprites.platform_box
        spots = self.unova.draw_platforms(canvas, d, when, far_dx, near_dx) if unova else {}
        for side, (cx, bottom), dx in (('foe', self.FAR_PLATFORM, far_dx), ('you', self.NEAR_PLATFORM, near_dx)):
            if side in spots:
                continue
            if plat and box:
                p = plat.frames[0]
                px, py = cx - p.get_width() // 2 + dx, bottom - p.get_height()
                canvas.blit(p, (px, py))
                spots[side] = (px + DIORAMA_CENTER_X - box[0], py + DIORAMA_BOTTOM - box[1])
            else:
                spots[side] = (cx - 8 + dx, bottom - 25)
        if unova:
            self._unova_trainer(canvas, d, spots, t_ms)

        # Foes (up to two; the first one is on the right, as in the game),
        # then your Pokemon from behind.
        offsets = [0] if len(foes) < 2 else [26, -26]
        for k, m in enumerate(foes):
            x, y = spots['foe']
            if unova and self.caught_at is not None and k == 0:
                # Caught: it flashes into the ball, which wobbles and clicks.
                age = t_ms - self.caught_at
                if age < 250:
                    anim = self.sprites.front(m['species_id'], m['shiny'])
                    self._draw_battler(canvas, 'foe0', anim, x + offsets[k], y, 96, t_ms, 0, direction=-1,
                                       tint=(255, 160, 160))
                self.boxes.pop('foe0', None)
                self.unova.draw_catch(canvas, (x + offsets[k], y), age)
                continue
            anim = self.sprites.front(m['species_id'], m['shiny'])
            self._draw_battler(canvas, f'foe{k}', anim, x + offsets[k], y, 96, t_ms, k * 300, direction=-1,
                               tint=markers.FROZEN_TINT if m.get('status') == 'Frozen' else None)
            if m['shiny'] and t_ms < self.shiny_intro_until:
                for j in range(5):
                    ui.sparkle(canvas, x - 20 + offsets[k] + (j * 13) % 40, y - 54 + (j * 17) % 45, t_ms + j * 70)
        # Yours (up to two; the first one on the left), the right one first
        # so the first stands in front; in Black and White the right one is
        # nearer the camera, so it's drawn last, in front.
        offsets = [0] if len(yours) < 2 else [-22, 22]
        for k in (range(len(yours)) if unova else reversed(range(len(yours)))):
            m = yours[k]
            x, y = spots['you']
            anim = self.sprites.back(m['species_id'], m['shiny'])
            drop = DOUBLES_DROP[k] if unova and len(yours) > 1 else 0
            self._draw_battler(canvas, f'you{k}', anim, x + offsets[k], y + drop, 84, t_ms, k * 300, direction=1,
                               tint=markers.FROZEN_TINT if m.get('status') == 'Frozen' else None)

        # Condition markers (sleep, paralysis, confusion, ...) on everyone
        # who's out and standing.
        for key, m in [(f'foe{k}', m) for k, m in enumerate(foes)] + [(f'you{k}', m) for k, m in enumerate(yours)]:
            st, rect = self.battlers.get(key, {}), self.boxes.get(key)
            if rect is None or m['curr_hp'] <= 0 or st.get('faint') is not None:
                continue
            if st.get('entered') is not None and t_ms < st['entered'] + self.SWITCH_MS:
                continue
            markers.draw(canvas, rect, m, t_ms, self.font)

        self.effects = [e for e in self.effects if e.draw(canvas, t_ms, self.boxes)]
        self.backdrop.draw_weather(canvas, self.unova.weather(d) if unova else
                                   weather_kind(d['location'].get('weather'), place), t_ms)
        # Quakes, explosions and heavy hits shake the scene (not the HUD).
        shake = max((e.shake(t_ms) for e in self.effects), key=lambda v: abs(v[0]) + abs(v[1]), default=(0, 0))
        if shake != (0, 0):
            canvas.scroll(*shake)

        # HP boxes slide in after the Pokemon.
        hud = 1.0
        if self.battle_since is not None:
            hud = ui.ease_out(max(0.0, min(1.0, (t_ms - self.battle_since - 350) / 400)))
        # Foe boxes top left, stacked; a box grows a row of chips for stat
        # changes and conditions when there are any.
        y = 6
        for k, m in enumerate(foes):
            entered = self.battlers.get(f'foe{k}', {}).get('entered')
            if entered is not None and t_ms < entered:
                continue  # not sent out yet (its "sent out" message is still queued)
            y += 3 + self._foe_box(canvas, m, 4 + int((hud - 1) * 130), y, dt_ms, k, self._hp_now(f'foe{k}', m, t_ms))
        # Yours bottom right, stacked upwards from just above the message box.
        x = 136 + int((1 - hud) * 130)
        bottom = 145 if len(yours) > 1 else 141
        for k in reversed(range(len(yours))):
            m = yours[k]
            entered = self.battlers.get(f'you{k}', {}).get('entered')
            if entered is not None and t_ms < entered:
                continue
            if len(yours) == 1:
                h = self._your_box(canvas, m, x, bottom, dt_ms, self._hp_now('you0', m, t_ms))
            else:
                # Two smaller boxes (no HP numbers).
                h = self._your_small_box(canvas, m, x, bottom, dt_ms, k, self._hp_now(f'you{k}', m, t_ms))
            bottom -= h + 1

        # Bottom: a message for a few seconds after something happens,
        # otherwise your Pokemon's moves.
        if self.msg and self.msg[2] == self.intro_until and t_ms < self.intro_until:
            # Until something else is said, the intro follows the data (the
            # music at the very start can still be the encounter jingle).
            self.msg = (*self._battle_lines(d), self.intro_until)
        while self.msg_queue and self.msg_queue[0][0] <= t_ms:
            start, l1, l2 = self.msg_queue.pop(0)
            self.msg = (l1, l2, start + self.MSG_MS)
        if self.msg and t_ms < self.msg[2] and unova:
            self.unova.message_band(canvas, (0, 146, W, H - 146))
            self.unova.message_text(canvas, self.msg[0], self.msg[1])
        elif self.msg and t_ms < self.msg[2]:
            ui.textbox(canvas, (0, 146, W, H - 146))
            self.font.draw(canvas, self.msg[0], (12, 156), t['text'], t['text_shadow'])
            self.font.draw(canvas, self.msg[1], (12, 170), t['text'], t['text_shadow'])
        else:
            picked = self.battlers.get('you0', {}).get('picked')
            self._move_panel(canvas, yours[0] if yours else None, picked, foes[0] if foes else None)

    def _unova_trainer(self, canvas, d, spots, t_ms):
        """Black and White: a Gym Leader, Elite Four member or Champion
        stands on the far turf as the battle starts, then steps aside as
        their first Pokemon comes out (decided on the battle's first frame:
        a leader told only later by their music gets the message, not the
        entrance)."""
        if self.trainer_intro is None and self.battle_since is not None:
            intro = self.unova.trainer_intro(d) or {}
            if intro:
                intro['out_at'] = self.battle_since + TRAINER_MS
                for key, st in self.battlers.items():
                    if key.startswith('foe') and st.get('entered') is None:
                        st['entered'] = intro['out_at']
                foes = [m for m in d['battle']['mons'] if m['side'].startswith('foe')]
                if foes:
                    self._say(f"{intro['name']} sent out", f"{_upper(foes[0]['nickname'])}!", intro['out_at'])
            self.trainer_intro = intro
        if self.trainer_intro and 'foe' in spots:
            self.unova.draw_trainer(canvas, self.trainer_intro, spots['foe'], t_ms)

    def _track_battlers(self, d, foes, yours, t_ms):
        """Notices moves, damage, fainting and switches, and plays them in
        the order they happened in the game."""
        wild, trainer = _opponent(d)
        current = {f'foe{k}': m for k, m in enumerate(foes)}
        for k, m in enumerate(yours):
            current[f'you{k}'] = m
        same = {key: m for key, m in current.items()
                if key in self.battlers and self.battlers[key]['ident'] == _ident(m)}

        # 1. Moves used since the last read (PP drops), held until they can
        #    play in order.
        for key, m in same.items():
            self._check_move(key, m, self.battlers[key], wild, t_ms)

        # 2. Damage, put down to the held move that did it.
        for key, m in same.items():
            st = self.battlers[key]
            if m['curr_hp'] < st['hp']:
                self._took_damage(key, m, st, wild, t_ms)
            if m['curr_hp'] > 0:
                st['faint'] = None
            st['hp'] = m['curr_hp']

        # 3. Switches. Whatever the one that left did, or had done to it,
        #    plays before its replacement comes out.
        for key, m in current.items():
            if key in same:
                continue
            switched = key in self.battlers
            if switched:
                self._play_ready(t_ms, leaving=key)
            self.battlers[key] = {'ident': _ident(m), 'hp': m['curr_hp'], 'entered': None,
                                  'hit': None, 'lunge': None, 'faint': None if m['curr_hp'] > 0 else t_ms - 9999,
                                  'moves': list(m.get('moves') or []), 'pp': list(m.get('pp') or []),
                                  'last_move': m.get('last_move'), 'used': None, 'log': [],
                                  'picked': None}
            if switched:
                if key.startswith('foe'):
                    who = f"{trainer} sent out" if trainer else "Go,"
                    line = f"{who} {_upper(m['nickname'])}!"
                else:
                    line = f"Go! {m['nickname']}!"
                self.battlers[key]['entered'] = self._say(line, "", t_ms)

        # 4. Play whatever is ready, in order.
        self._play_ready(t_ms)

    def _took_damage(self, key, m, st, wild, t_ms):
        st['hp_before'] = st['hp']   # the HP box holds this until the hit lands
        ko = self._faint_lines(key, m, wild) if m['curr_hp'] <= 0 < st['hp'] else None
        # Held damaging moves from the other side. In a double battle the
        # target isn't known until its HP drops, so any of them will do.
        aimed = [h for h in self.held if not h['status'] and h['key'][:3] != key[:3]]
        h = next((h for h in aimed if not h['hits']), aimed[-1] if aimed else None)
        if h is not None:
            # The move that did it hasn't played yet; the hit (and the
            # faint) land when it does. A move that hits both (Surf, ...)
            # collects both.
            if not h['hits']:
                h['target'] = key
            h['hits'].append((key, ko))
            st['hit'] = float('inf')
            return
        attacker = self.battlers.get('you0' if key.startswith('foe') else 'foe0')
        used = attacker and attacker['used']
        if used and t_ms - used[1] < 4000:
            # Another hit from a move that just played (multi-hit, ...).
            st['hit'] = max(t_ms + 150, used[2])
        else:
            # No move seen (or it was a while ago): the attacker lunges.
            st['hit'] = t_ms + 150
            if attacker:
                attacker['lunge'] = t_ms
        if ko:
            st['faint'] = st['hit'] + self.HIT_MS
            self._say(*ko, st['faint'])

    def _faint_lines(self, key, m, wild):
        if key.startswith('foe'):
            owner = "The wild" if wild else "The foe's"
            return f"{owner} {_upper(m['nickname'])}", "fainted!"
        return f"{m['nickname']} fainted!", ""

    def _check_move(self, key, m, st, wild, t_ms):
        """Works out whether this battler used a move since the last read."""
        moves, pp = list(m.get('moves') or []), list(m.get('pp') or [])
        st['log'] = [e for e in st['log'] if t_ms - e[1] < 8000]   # (move, when, seen via PP)
        used = slot = None
        if moves == st['moves'] and len(pp) == len(st['pp']):
            for i, (now, before) in enumerate(zip(pp, st['pp'])):
                if now < before:
                    used, slot = moves[i], i
                    st['log'].append((used, t_ms, True))
                    break
        st['moves'], st['pp'] = moves, pp

        last, before = m.get('last_move'), st['last_move']
        st['last_move'] = last
        if last and last != before:
            if any(mv == last and via_pp for mv, _, via_pp in st['log']):
                self.last_move_agreed += 1
            elif used is None and self.last_move_agreed >= 2 and last in MOVE_INFO \
                    and not any(mv == last for mv, _, _ in st['log']):
                # A move PP didn't show: Struggle, or one called by another
                # move (Metronome and friends).
                used = last
                st['log'].append((used, t_ms, False))
        if used:
            self._hold_move(key, m, used, wild, slot)

    def _hold_move(self, key, m, move, wild, slot):
        """Keeps a move until it's ready to play (see _ready)."""
        self.seq += 1
        category = MOVE_INFO.get(move, ('Normal', 'Physical', 0))[1]
        self.held.append({'key': key, 'target': 'foe0' if key.startswith('you') else 'you0',
                          'move': move, 'slot': slot, 'status': category == 'Status',
                          'hits': [], 'read_at': self.read_at or 0.0, 'seq': self.seq,
                          'priority': pdata.MOVE_PRIORITY.get(move, 0), 'speed': _speed(m),
                          'lines': self._move_lines(key, m, move, wild)})

    def _ready(self, h, leaving=None):
        """A held move can play once it has clearly finished in the game."""
        if h['status'] or h['hits'] or leaving in (h['key'], h['target']) \
                or any(leaving == k for k, _ in h['hits']):
            return True
        # Something happened after it (another move was seen in a later
        # read), or one side fainted or left: it missed or did no damage.
        if any(o['read_at'] > h['read_at'] for o in self.held):
            return True
        for k in (h['key'], h['target']):
            st = self.battlers.get(k)
            if st is None or st['hp'] <= 0:
                return True
        return (self.read_at or 0.0) - h['read_at'] >= self.MISS_AFTER_S

    def _order(self, h):
        """Moves play by the read they were seen in. Within one read: a
        Pokemon that has fainted went before the hit that knocked it out,
        then higher priority, then higher speed, then yours."""
        st = self.battlers.get(h['key'])
        fainted = st is not None and st['hp'] <= 0
        return (h['read_at'], not fainted, -h['priority'], -h['speed'], not h['key'].startswith('you'), h['seq'])

    def _play_ready(self, t_ms, leaving=None):
        self.held.sort(key=self._order)
        while self.held and self._ready(self.held[0], leaving):
            self._play(self.held.pop(0), t_ms)

    def _play(self, h, t_ms):
        """Message, lunge and animation for a held move, then its hit (and
        faint) on the target. When several things are ready at once, each
        gets its turn, MOVE_GAP_MS apart."""
        key, move = h['key'], h['move']
        start = self._say(*h['lines'], t_ms)
        mtype, category, _ = MOVE_INFO.get(move, ('Normal', 'Physical', 0))
        fx = Effect(mtype, category, key, h['target'], start + 250, move)
        self.effects = self.effects[-3:] + [fx]
        st = self.battlers.get(key)
        if st is not None:
            st['used'] = (move, start, fx.impact)
            if h['slot'] is not None:
                st['picked'] = h['slot']
            if category == 'Physical':
                st['lunge'] = start + 100   # at its furthest as the effect starts
        for key_hit, ko in h['hits']:
            target = self.battlers.get(key_hit)
            if target is None:
                continue
            target['hit'] = max(t_ms + 150, fx.impact)
            if ko:
                target['faint'] = target['hit'] + self.HIT_MS
                self._say(*ko, target['faint'])

    def _say(self, l1, l2, at):
        """Queues a message for the box, no earlier than `at` and MOVE_GAP_MS
        after the one before. Returns when it will show."""
        start = max(at, self.next_msg_at)
        self.next_msg_at = start + self.MOVE_GAP_MS
        self.msg_queue.append((start, l1, l2))
        return start

    def _move_lines(self, key, m, move, wild):
        """'X used MOVE!' split over the two lines of the message box as needed."""
        if key.startswith('you'):
            name = m['nickname']
        else:
            owner = "The wild" if wild else "The foe's"
            name = f"{owner} {_upper(m['nickname'])}"
        mv = _upper(move)
        for l1, l2 in ((f"{name} used {mv}!", ""), (f"{name} used", f"{mv}!")):
            if self.font.width(l1) <= W - 24 and self.font.width(l2) <= W - 24:
                return l1, l2
        return name, f"used {mv}!"

    def _draw_battler(self, canvas, key, anim, feet_x, feet_y, max_size, t_ms, phase, direction, tint=None):
        """direction: -1 for foes (they face left, slide in from the left),
        +1 for your side. tint: colour to multiply the sprite by (frozen)."""
        if not anim:
            return
        st = self.battlers.get(key, {})
        if st.get('entered') is not None and t_ms < st['entered']:
            return  # not sent out yet
        f = self._fit(anim.frame(t_ms + phase), max_size, max_size)
        dx = dy = 0
        if st.get('entered') is not None:
            p = min(1.0, (t_ms - st['entered']) / self.SWITCH_MS)
            dx += int((1 - ui.ease_out(p)) * 140) * (1 if direction > 0 else -1)
        if st.get('lunge') is not None:
            p = (t_ms - st['lunge']) / self.LUNGE_MS
            if 0 <= p < 1:
                push = math.sin(math.pi * p) * 8
                dx += int(push * direction)
                dy -= int(push * direction / 2)
        visible = True
        if st.get('hit') is not None:
            q = t_ms - st['hit']
            if 0 <= q < self.HIT_MS:
                visible = (q // 65) % 2 == 0
                if q < 300:
                    dx += 2 if (q // 40) % 2 else -2
        sink = 0
        if st.get('faint') is not None:
            p = (t_ms - st['faint']) / self.FAINT_MS
            if p >= 1:
                return
            sink = int(max(0.0, p) * f.get_height())
        if not visible:
            return
        x = feet_x - f.get_width() // 2 + dx
        y = feet_y - f.get_height() + dy + sink
        self.boxes[key] = pygame.Rect(x, y, f.get_width(), f.get_height() - sink)
        if tint:
            f = f.copy()
            f.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        clip = canvas.get_clip()
        canvas.set_clip((0, 0, W, feet_y + dy))  # a fainting Pokemon sinks into its platform
        canvas.blit(f, (x, y))
        canvas.set_clip(clip)

    def _move_panel(self, canvas, mon, picked=None, foe=None):
        """Your Pokemon's moves; picked: index of the one it used last. Each
        damaging move gets its type multiplier against `foe` (the first
        foe in a double battle)."""
        t = ui.THEME
        if self.unova_battle:
            self.unova.message_band(canvas, (0, 146, W, H - 146))
        else:
            ui.panel(canvas, (0, 146, W, H - 146), fill=t['box_frame'], border=ui.darken(t['box_frame'], 30),
                     hi=t['box_frame_hi'], lo=ui.darken(t['box_frame'], 16), radius=3)
        button = self.unova.move_button if self.unova_battle else \
            (lambda rect, canvas, *a, **k: ui.move_button(canvas, self.font, self.mini, rect, *a, **k))
        moves = (mon or {}).get('moves') or []
        pps = (mon or {}).get('pp') or []
        ups = (mon or {}).get('pp_ups') or []
        for i in range(4):
            rect = (5 + (i % 2) * 124, 150 + (i // 2) * 20, 122, 18)
            if i >= len(moves):
                button(rect, canvas, None)
                continue
            info = MOVE_INFO.get(moves[i])
            mtype, base = (info[0], info[2]) if info else (None, None)
            pp = pps[i] if i < len(pps) else None
            pp_max = base + (base // 5) * (ups[i] if i < len(ups) else 0) if base else None
            if i < len((mon or {}).get('pp_max') or ()):
                pp_max = mon['pp_max'][i]  # Black and White keep it
            effect = _effectiveness(mtype, foe) if info and info[1] != 'Status' else None
            button(rect, canvas, moves[i], mtype, pp, pp_max, selected=i == picked, effect=effect)

    def _hp_now(self, key, m, t_ms):
        """The HP to show: the old value until a queued hit lands."""
        st = self.battlers.get(key, {})
        if st.get('hit') and t_ms < st['hit'] and st.get('hp_before') is not None:
            return st['hp_before']
        return m['curr_hp']

    def _chips(self, canvas, m, x, y, width):
        """Rows of stat-change and condition chips from (x, y). Returns the
        height they take (0 without any)."""
        rows = ui.chip_rows(self.mini, ui.stage_chips(m), width)
        for r, row in enumerate(rows):
            cx = x
            for text, color in row:
                cx += ui.chip(canvas, self.mini, cx, y + r * 10, text, color) + 2
        return len(rows) * 10

    def _box_rows(self, m, width):
        return len(ui.chip_rows(self.mini, ui.stage_chips(m), width))

    def _foe_box(self, canvas, m, x, y, dt_ms, k, hp_now):
        """Draws the foe's box with its top at y. Returns its height."""
        if self.unova_battle:
            hp = self._hp(('foe', k, m['species_id']), hp_now, m['max_hp'], dt_ms)
            return self.unova.foe_hud(canvas, m, x, y, hp, self._chips)
        h = 27 + 10 * self._box_rows(m, 104)
        ui.panel(canvas, (x, y, 112, h))
        self._name_line(canvas, m['nickname'], m['gender'], x + 5, y + 4)
        self._level(canvas, m['level'], x + 84, y + 4)
        hp = self._hp(('foe', k, m['species_id']), hp_now, m['max_hp'], dt_ms)
        ui.hp_bar(canvas, self.mini, x + 30, y + 16, 76, hp / max(1, m['max_hp']))
        if m.get('status'):
            ui.status_tag(canvas, self.mini, x + 5, y + 15, m['status'])
        self._chips(canvas, m, x + 5, y + 26, 104)
        return h

    def _your_box(self, canvas, m, x, bottom, dt_ms, hp_now):
        """Draws your box with its bottom edge at `bottom`. Returns its height."""
        t = ui.THEME
        if self.unova_battle:
            hp = self._hp(('yours', m['species_id']), hp_now, m['max_hp'], dt_ms)
            return self.unova.your_hud(canvas, m, x, bottom, hp, self._chips)
        h = 37 + 10 * self._box_rows(m, 106)
        y = bottom - h
        ui.panel(canvas, (x, y, 116, h))
        self._name_line(canvas, m['nickname'], m['gender'], x + 5, y + 4)
        self._level(canvas, m['level'], x + 88, y + 4)
        hp = self._hp(('yours', m['species_id']), hp_now, m['max_hp'], dt_ms)
        ui.hp_bar(canvas, self.mini, x + 34, y + 16, 76, hp / max(1, m['max_hp']))
        if m.get('status'):
            ui.status_tag(canvas, self.mini, x + 5, y + 15, m['status'])
        self.font.draw(canvas, f"{int(round(hp))}/{m['max_hp']}", (x + 110, y + 25),
                       t['text'], t['text_shadow'], align='right')
        self._chips(canvas, m, x + 5, y + 36, 106)
        return h

    def _your_small_box(self, canvas, m, x, bottom, dt_ms, k, hp_now):
        """Your side's box in a double battle: like the foe's box, with its
        bottom edge at `bottom`. Returns its height."""
        if self.unova_battle:
            hp = self._hp(('yours', k, m['species_id']), hp_now, m['max_hp'], dt_ms)
            return self.unova.your_hud(canvas, m, x, bottom, hp, self._chips, numbers=False)
        h = 27 + 10 * self._box_rows(m, 106)
        y = bottom - h
        ui.panel(canvas, (x, y, 116, h))
        self._name_line(canvas, m['nickname'], m['gender'], x + 5, y + 4)
        self._level(canvas, m['level'], x + 88, y + 4)
        hp = self._hp(('yours', k, m['species_id']), hp_now, m['max_hp'], dt_ms)
        ui.hp_bar(canvas, self.mini, x + 34, y + 16, 76, hp / max(1, m['max_hp']))
        if m.get('status'):
            ui.status_tag(canvas, self.mini, x + 5, y + 15, m['status'])
        self._chips(canvas, m, x + 5, y + 26, 106)
        return h

    def _battle_lines(self, d):
        b = d['battle']
        foes = [m for m in b['mons'] if m['side'].startswith('foe')]
        yours = [m for m in b['mons'] if m['side'].startswith('yours')]
        music = d['misc']['music_id']
        wild, trainer = _opponent(d)
        foe = _upper(foes[0]['nickname']) if foes else 'the foe'
        kind = b.get('kind')  # Black and White say who it is
        if wild:
            l1 = f"A wild {foe} appeared!"
        elif kind in TITLES:
            some = {'gym': 'a Gym Leader', 'elite': 'the Elite Four', 'champion': 'the Champion'}[kind]
            l1 = f"You are challenged by {TITLES[kind]} {trainer}!" if trainer else f"You are challenged by {some}!"
        elif kind == 'trainer':
            l1 = "You are challenged by a Trainer!"
        elif music == RIVAL:
            l1 = f"You are challenged by Rival {trainer}!" if trainer else "You are challenged by your rival!"
        elif music == GYM:
            l1 = f"You are challenged by Gym Leader {trainer}!" if trainer else "You are challenged by a Gym Leader!"
        elif music == CHAMPION:
            l1 = "You are challenged by Champion CYNTHIA!"
        elif music == ELITE_FOUR:
            l1 = f"You are challenged by Elite Four {trainer}!" if trainer else "You are challenged by the Elite Four!"
        else:
            l1 = f"You are challenged by {trainer}!" if trainer else "You are challenged by a Trainer!"
        mine = yours[0]['nickname'] if yours else 'you'
        return l1, f"What will {mine} do?"

    # -- waiting view ----------------------------------------------------------

    def draw_waiting(self, canvas, snap, t_ms):
        """While the DSi isn't sending: what to do, and the last game played,
        in the same frame as the other views."""
        t = ui.THEME
        ui.tiled_background(canvas, t_ms)

        # Header: the name, and a signal meter that fills up and resets.
        self._bar(canvas, 0, HEADER_H)
        self.font.draw(canvas, "DSiRPC", (5, 4), t['text_light'], t['text_light_shadow'])
        level = (t_ms // 350) % 4
        for i in range(3):
            c = t['hp_green'] if i < level else t['bar_hi']
            pygame.draw.rect(canvas, c, (W - 18 + i * 5, 11 - i * 3, 3, 2 + i * 3))

        # A DSi looking for a connection, and what to do, centred in a panel.
        px, py, pw, ph = 3, 18, 250, 142
        ui.panel(canvas, (px, py, pw, ph))
        tx, tw = px + 58, pw - 64
        status = self.font.wrap(snap.status or '', tw, 2)
        steps = ["Start the DSiRPC launcher.", "Press START and pick a game.", "It shows up here as you play."]
        block = 12 + 12 * len(status) + 10 + 16 * len(steps) - 4
        y = py + (ph - block) // 2
        ix, iy = px + 12, py + (ph - ui.DSI_H) // 2
        ui.dsi(canvas, ix, iy)
        self._wifi(canvas, ix, iy, t_ms)
        dots = '.' * (1 + (t_ms // 400) % 3)
        self.font.draw(canvas, "Waiting for the DSi" + dots, (tx, y), t['text'], t['text_shadow'])
        y += 12
        for line in status:
            self.font.draw(canvas, line, (tx, y), t['text_muted'], t['text_shadow'])
            y += 12
        pygame.draw.line(canvas, t['panel_lo'], (tx, y + 3), (px + pw - 7, y + 3))
        y += 10
        for n, line in enumerate(steps, 1):
            ui.chip(canvas, self.mini, tx, y + 1, str(n), t['lead_border'])
            self.font.draw(canvas, line, (tx + 12, y), t['text'], t['text_shadow'])
            y += 16

        # Footer: the last game played (its trainer, or its game card).
        self._bar(canvas, FOOTER_Y, H - FOOTER_Y)
        last = snap.state
        if last and last.get('kind') == 'other':
            code = (last.get('game') or {}).get('code') or '????'
            ui.game_card(canvas, 14, H - 24, ui.card_color(code))
            title = last.get('title') or code
        else:
            anim = self.sprites.trainer((last or {}).get('character') or 'Dawn', 'down')
            if anim:
                f = anim.frames[0]
                canvas.blit(f, (22 - f.get_width() // 2, H - 3 - f.get_height()))
            title = "Pokémon Platinum" if last else "DSiRPC"
            if last and last.get('kind') == 'bw':
                title = last.get('title') or f"Pokémon {last.get('version', 'Black')}"
        label = "LAST PLAYED" if last else "DISCORD + RETROACHIEVEMENTS"
        self.font.draw(canvas, self.font.fit(title, W - 52), (44, FOOTER_Y + 5), t['text_light'],
                       t['text_light_shadow'])
        self.mini.draw(canvas, label, (44, FOOTER_Y + 19), t['hp_label'])

    def _wifi(self, canvas, ix, iy, t_ms):
        """Wi-Fi arcs on the DSi's top screen, lighting up one by one."""
        t = ui.THEME
        sx, sy, sw, sh = ui.DSI_TOP_SCREEN
        cx, cy = ix + sx + sw // 2, iy + sy + sh - 3
        lit = (t_ms // 400) % 4
        off = (64, 76, 88)
        canvas.set_at((cx, cy), t['hp_green'])
        for i, r in enumerate((3, 5, 7)):
            c = t['hp_green'] if i < lit else off
            for deg in range(45, 136, 5):
                rad = math.radians(deg)
                canvas.set_at((cx + int(round(r * math.cos(rad))), cy - int(round(r * math.sin(rad)))), c)

    # -- toasts ----------------------------------------------------------------

    def draw_toasts(self, canvas, t_ms):
        if not self.toasts:
            return
        toast = self.toasts[0]
        if toast[1] is None:
            toast[1] = t_ms
        age = t_ms - toast[1]
        if age > TOAST_MS:
            self.toasts.pop(0)
            return
        text, _, sparkly = toast
        w = self.font.width(text) + (32 if sparkly else 16)
        slide = min(1.0, age / 250.0, (TOAST_MS - age) / 250.0)
        y = int(-26 + 30 * ui.ease_out(max(0.0, slide)))
        x = (W - w) // 2
        t = ui.THEME
        ui.panel(canvas, (x, y, w, 20), fill=t['lead_fill'], lo=t['lead_lo'], border=t['lead_border'])
        self.font.draw(canvas, text, (x + (16 if sparkly else 8), y + 6), t['text'], t['text_shadow'])
        if sparkly:
            ui.sparkle(canvas, x + 8, y + 10, t_ms)
            ui.sparkle(canvas, x + w - 9, y + 10, t_ms + 300)
