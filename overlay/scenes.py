"""
scenes.py - what the overlay draws on its 256x192 canvas:

    party view    header (location, playtime), the six party slots, footer
                  (trainer, badges, Pokedex)
    battle view   sky and ground, platforms, the foe and your Pokemon, their
                  HP boxes and a message box
    waiting view  shown while the DSi isn't sending data
    toasts        short banners for events (shiny, level up, fainted, ...)

The Overlay object keeps the animation state (HP bars sliding to their new
value, the battle transition, the toast queue) between frames.
"""

import math

import pygame

from core import platinum_data as pdata
from . import ui
from .backdrop import Backdrop, period, terrain, weather_kind
from .font import PixelFont
from .sprites import DIORAMA_BOTTOM, DIORAMA_CENTER_X

W, H = 256, 192
HEADER_H = 16
FOOTER_Y = 162
SLOT_W, SLOT_H = 124, 46
SLOT_POS = [(3, 18), (129, 18), (3, 66), (129, 66), (3, 114), (129, 114)]

WILD, GYM, TRAINER, CHAMPION, RIVAL, ELITE_FOUR = 0x45C, 0x45D, 0x45F, 0x462, 0x464, 0x470

TOAST_MS = 3500
WIPE_MS = 700


def _upper(name):
    return (name or '').upper()


def _facing(d):
    raw = d.get('direction_raw')
    if raw is not None and (raw & 0xFF) < 4:
        return pdata.DIRECTIONS[raw & 0xFF]
    return d['location'].get('facing') or 'down'


class Overlay:
    def __init__(self, sprites):
        self.sprites = sprites
        self.font = PixelFont()
        self.mini = PixelFont(mini=True)
        self.hp_shown = {}         # key -> displayed HP (float), slides toward the real value
        self.toasts = []           # [text, started_ms or None, sparkly]
        self.view = 'auto'         # 'auto', 'party' or 'battle' (V key in the window)
        self.showing_battle = False
        self.wipe_start = None
        self.walk_until = 0
        self.last_pos = None
        self.shiny_intro_until = 0
        self._scaled = {}
        self.backdrop = Backdrop()
        self.battle_since = None   # when the battle view appeared (intro slide-in)
        self.battlers = {}         # 'foe0' / 'foe1' / 'you0' -> animation state
        self.msg = None            # (line 1, line 2, until_ms) for the message box

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
        d = snap.state if snap.online else None
        in_battle = bool(d and d['battle']['active'])
        want_battle = in_battle if self.view == 'auto' else (self.view == 'battle' and in_battle)

        # Battle transition: bars close, the view switches, bars open.
        if want_battle != self.showing_battle and self.wipe_start is None:
            self.wipe_start = t_ms
        wipe = None
        if self.wipe_start is not None:
            p = (t_ms - self.wipe_start) / (WIPE_MS / 2)
            if p >= 1 and want_battle != self.showing_battle:
                self.showing_battle = want_battle
                self.battlers, self.msg = {}, None
                self.battle_since = t_ms if want_battle else None
                if want_battle:
                    self.msg = (*self._battle_lines(d), t_ms + 4500)
            if p >= 2:
                self.wipe_start = None
            else:
                wipe = p

        if d is None:
            self.draw_waiting(canvas, snap, t_ms)
        elif self.showing_battle and in_battle:
            self.draw_battle(canvas, d, t_ms, dt_ms)
        else:
            self.draw_party(canvas, d, t_ms, dt_ms)

        self.draw_toasts(canvas, t_ms)
        if wipe is not None:
            ui.wipe(canvas, wipe)

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
        t = ui.THEME
        pygame.draw.rect(canvas, t['bar'], (0, y, W, h))
        pygame.draw.line(canvas, t['bar_hi'], (0, y), (W - 1, y))
        pygame.draw.line(canvas, t['bar_lo'], (0, y + h - 1), (W - 1, y + h - 1))

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

    def draw_battle(self, canvas, d, t_ms, dt_ms):
        t = ui.THEME
        b = d['battle']
        place = terrain(d['location'])
        when = period(d['misc'].get('clock'))
        self.backdrop.draw(canvas, place, when, t_ms, t['chroma'])

        foes = [m for m in b['mons'] if m['side'].startswith('foe')][:2]
        yours = [m for m in b['mons'] if m['side'].startswith('yours')][:1]
        self._track_battlers(d, foes, yours, t_ms)

        # Intro: each side slides in from its edge with its platform.
        intro = 1.0
        if self.battle_since is not None:
            intro = ui.ease_out(min(1.0, (t_ms - self.battle_since) / self.INTRO_MS))
        far_dx = int((intro - 1) * 200)
        near_dx = int((1 - intro) * 200)

        plat = self.sprites.platform(place, when)
        box = self.sprites.platform_box
        spots = {}
        for side, (cx, bottom), dx in (('foe', self.FAR_PLATFORM, far_dx), ('you', self.NEAR_PLATFORM, near_dx)):
            if plat and box:
                p = plat.frames[0]
                px, py = cx - p.get_width() // 2 + dx, bottom - p.get_height()
                canvas.blit(p, (px, py))
                spots[side] = (px + DIORAMA_CENTER_X - box[0], py + DIORAMA_BOTTOM - box[1])
            else:
                spots[side] = (cx - 8 + dx, bottom - 25)

        # Foes (up to two), then your Pokemon from behind.
        offsets = [0] if len(foes) < 2 else [-26, 26]
        for k, m in enumerate(foes):
            x, y = spots['foe']
            anim = self.sprites.front(m['species_id'], m['shiny'])
            self._draw_battler(canvas, f'foe{k}', anim, x + offsets[k], y, 96, t_ms, k * 300, direction=-1)
            if m['shiny'] and t_ms < self.shiny_intro_until:
                for j in range(5):
                    ui.sparkle(canvas, x - 20 + offsets[k] + (j * 13) % 40, y - 54 + (j * 17) % 45, t_ms + j * 70)
        if yours:
            m = yours[0]
            x, y = spots['you']
            anim = self.sprites.back(m['species_id'], m['shiny'])
            self._draw_battler(canvas, 'you0', anim, x, y, 84, t_ms, 0, direction=1)

        self.backdrop.draw_weather(canvas, weather_kind(d['location'].get('weather'), place), t_ms)

        # HP boxes slide in after the Pokemon.
        hud = 1.0
        if self.battle_since is not None:
            hud = ui.ease_out(max(0.0, min(1.0, (t_ms - self.battle_since - 350) / 400)))
        for k, m in enumerate(foes):
            self._foe_box(canvas, m, 4 + int((hud - 1) * 130), 6 + k * 30, dt_ms, k)
        if yours:
            self._your_box(canvas, yours[0], 136 + int((1 - hud) * 130), 104, dt_ms)

        # Bottom: a message for a few seconds after something happens,
        # otherwise your Pokemon's moves.
        if self.msg and t_ms < self.msg[2]:
            ui.textbox(canvas, (0, 146, W, H - 146))
            self.font.draw(canvas, self.msg[0], (12, 156), t['text'], t['text_shadow'])
            self.font.draw(canvas, self.msg[1], (12, 170), t['text'], t['text_shadow'])
        else:
            self._move_panel(canvas, yours[0] if yours else None)

    def _track_battlers(self, d, foes, yours, t_ms):
        """Notices switches, damage and fainting, and starts the animations
        and messages for them."""
        trainer = _upper(d['battle'].get('trainer'))
        wild = not trainer
        current = {f'foe{k}': m for k, m in enumerate(foes)}
        if yours:
            current['you0'] = yours[0]
        for key, m in current.items():
            ident = (m['species_id'], m['nickname'])
            st = self.battlers.get(key)
            if st is None or st['ident'] != ident:
                switched = st is not None
                self.battlers[key] = {'ident': ident, 'hp': m['curr_hp'], 'entered': t_ms if switched else None,
                                      'hit': None, 'lunge': None, 'faint': None if m['curr_hp'] > 0 else t_ms - 9999}
                if switched and key.startswith('foe'):
                    who = f"{trainer} sent out" if trainer else "Go,"
                    self.msg = (f"{who} {_upper(m['nickname'])}!", "", t_ms + self.MSG_MS)
                elif switched:
                    self.msg = (f"Go! {m['nickname']}!", "", t_ms + self.MSG_MS)
                continue
            if m['curr_hp'] < st['hp']:
                # The attacker lunges, then the one that lost HP blinks.
                st['hit'] = t_ms + 150
                attacker = 'you0' if key.startswith('foe') else 'foe0'
                if attacker in self.battlers:
                    self.battlers[attacker]['lunge'] = t_ms
            if m['curr_hp'] > 0:
                st['faint'] = None
            elif st['hp'] > 0:
                st['faint'] = t_ms
                if key.startswith('foe'):
                    owner = "The wild" if wild else "The foe's"
                    self.msg = (f"{owner} {_upper(m['nickname'])}", "fainted!", t_ms + self.MSG_MS)
                else:
                    self.msg = (f"{m['nickname']} fainted!", "", t_ms + self.MSG_MS)
            st['hp'] = m['curr_hp']

    def _draw_battler(self, canvas, key, anim, feet_x, feet_y, max_size, t_ms, phase, direction):
        """direction: -1 for foes (they face left, slide in from the left),
        +1 for your side."""
        if not anim:
            return
        st = self.battlers.get(key, {})
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
        clip = canvas.get_clip()
        canvas.set_clip((0, 0, W, feet_y + dy))  # a fainting Pokemon sinks into its platform
        canvas.blit(f, (x, y))
        canvas.set_clip(clip)

    def _move_panel(self, canvas, mon):
        t = ui.THEME
        ui.panel(canvas, (0, 146, W, H - 146), fill=t['box_frame'], border=ui.darken(t['box_frame'], 30),
                 hi=t['box_frame_hi'], lo=ui.darken(t['box_frame'], 16), radius=3)
        moves = (mon or {}).get('moves') or []
        pps = (mon or {}).get('pp') or []
        ups = (mon or {}).get('pp_ups') or []
        for i in range(4):
            rect = (5 + (i % 2) * 124, 150 + (i // 2) * 20, 122, 18)
            if i >= len(moves):
                ui.move_button(canvas, self.font, self.mini, rect, None)
                continue
            info = pdata.MOVE_INFO.get(moves[i])
            mtype, base = (info[0], info[2]) if info else (None, None)
            pp = pps[i] if i < len(pps) else None
            pp_max = base + (base // 5) * (ups[i] if i < len(ups) else 0) if base else None
            ui.move_button(canvas, self.font, self.mini, rect, moves[i], mtype, pp, pp_max)

    def _foe_box(self, canvas, m, x, y, dt_ms, k):
        t = ui.THEME
        ui.panel(canvas, (x, y, 112, 27))
        self._name_line(canvas, m['nickname'], m['gender'], x + 5, y + 4)
        self._level(canvas, m['level'], x + 84, y + 4)
        hp = self._hp(('foe', k, m['species_id']), m['curr_hp'], m['max_hp'], dt_ms)
        ui.hp_bar(canvas, self.mini, x + 30, y + 16, 76, hp / max(1, m['max_hp']))
        if m.get('status'):
            ui.status_tag(canvas, self.mini, x + 5, y + 15, m['status'])

    def _your_box(self, canvas, m, x, y, dt_ms):
        t = ui.THEME
        ui.panel(canvas, (x, y, 116, 37))
        self._name_line(canvas, m['nickname'], m['gender'], x + 5, y + 4)
        self._level(canvas, m['level'], x + 88, y + 4)
        hp = self._hp(('yours', m['species_id']), m['curr_hp'], m['max_hp'], dt_ms)
        ui.hp_bar(canvas, self.mini, x + 34, y + 16, 76, hp / max(1, m['max_hp']))
        if m.get('status'):
            ui.status_tag(canvas, self.mini, x + 5, y + 15, m['status'])
        self.font.draw(canvas, f"{int(round(hp))}/{m['max_hp']}", (x + 110, y + 25),
                       t['text'], t['text_shadow'], align='right')

    def _battle_lines(self, d):
        b = d['battle']
        foes = [m for m in b['mons'] if m['side'].startswith('foe')]
        yours = [m for m in b['mons'] if m['side'].startswith('yours')]
        music = d['misc']['music_id']
        trainer = _upper(b.get('trainer'))
        foe = _upper(foes[0]['nickname']) if foes else 'the foe'
        if music == WILD or (not trainer and music not in (GYM, TRAINER, CHAMPION, RIVAL, ELITE_FOUR)):
            l1 = f"A wild {foe} appeared!"
        elif music == RIVAL:
            l1 = f"You are challenged by Rival {trainer}!"
        elif music == GYM:
            l1 = f"You are challenged by Gym Leader {trainer}!"
        elif music == CHAMPION:
            l1 = "You are challenged by Champion CYNTHIA!"
        elif music == ELITE_FOUR:
            l1 = f"You are challenged by Elite Four {trainer}!"
        else:
            l1 = "You are challenged by a Trainer!"
        mine = yours[0]['nickname'] if yours else 'you'
        return l1, f"What will {mine} do?"

    # -- waiting view ----------------------------------------------------------

    def draw_waiting(self, canvas, snap, t_ms):
        t = ui.THEME
        ui.tiled_background(canvas, t_ms)
        ui.panel(canvas, (20, 52, 216, 88))
        dots = '.' * (1 + (t_ms // 400) % 3)
        self.font.draw(canvas, "Waiting for the DSi" + dots, (70, 64), t['text'], t['text_shadow'])
        self.font.draw(canvas, snap.status or '', (70, 80), (96, 104, 112), t['text_shadow'])
        self.font.draw(canvas, "Start the launcher, press", (70, 100), t['text'], t['text_shadow'])
        self.font.draw(canvas, "START, then launch the game.", (70, 112), t['text'], t['text_shadow'])

        character = (snap.state or {}).get('character') or 'Dawn'
        anim = self.sprites.trainer(character, 'down')
        if anim:
            f = anim.frame(t_ms)
            canvas.blit(f, (44 - f.get_width() // 2, 130 - f.get_height()))

        # A little signal meter that fills up and resets.
        level = (t_ms // 350) % 4
        for i in range(3):
            c = t['hp_green'] if i < level else (170, 184, 188)
            pygame.draw.rect(canvas, c, (212 + i * 5, 72 - i * 3, 3, 4 + i * 3))

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
