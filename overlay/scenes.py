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

import pygame

from core import platinum_data as pdata
from . import ui
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
            elif kind == 'fainted':
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

    def draw_battle(self, canvas, d, t_ms, dt_ms):
        t = ui.THEME
        b = d['battle']
        if t['chroma']:
            canvas.fill(t['chroma'])
        else:
            ui.bands(canvas, (0, 0, W, 100), t['sky'])
            ui.bands(canvas, (0, 100, W, 46), t['ground'])
            pygame.draw.line(canvas, ui.lighten(t['ground'][0], 30), (0, 100), (W - 1, 100))

        foe_x, foe_y = 182, 81  # where the foe stands; refined below once the platform has loaded
        plat = self.sprites.platform()
        if plat:
            p = plat.frames[0]
            px, py = 190 - p.get_width() // 2, 106 - p.get_height()
            canvas.blit(p, (px, py))
            canvas.blit(p, (70 - p.get_width() // 2, 182 - p.get_height()))
            box = self.sprites.platform_box
            if box:
                # Same spot on the platform as process_diorama.py uses for the
                # Discord images: centred on x=80, bottom at y=126 of its canvas.
                foe_x = px + DIORAMA_CENTER_X - box[0]
                foe_y = py + DIORAMA_BOTTOM - box[1]

        foes = [m for m in b['mons'] if m['side'].startswith('foe')]
        yours = [m for m in b['mons'] if m['side'].startswith('yours')]

        # Foe(s) on the far platform.
        offsets = [0] if len(foes) < 2 else [-26, 26]
        for k, m in enumerate(foes[:2]):
            anim = self.sprites.front(m['species_id'], m['shiny'])
            if anim:
                f = self._fit(anim.frame(t_ms + k * 300), 96, 96)
                canvas.blit(f, (foe_x + offsets[k] - f.get_width() // 2, foe_y - f.get_height()))
            if m['shiny'] and t_ms < self.shiny_intro_until:
                for j in range(5):
                    ui.sparkle(canvas, foe_x - 20 + offsets[k] + (j * 13) % 40, foe_y - 54 + (j * 17) % 45, t_ms + j * 70)

        # Your Pokemon from behind, standing on the near platform.
        if yours:
            m = yours[0]
            anim = self.sprites.back(m['species_id'], m['shiny'])
            if anim:
                f = self._fit(anim.frame(t_ms), 84, 84)
                canvas.blit(f, (70 - f.get_width() // 2, 150 - f.get_height()))

        # HP boxes.
        for k, m in enumerate(foes[:2]):
            self._foe_box(canvas, m, 4, 8 + k * 30, dt_ms, k)
        if yours:
            self._your_box(canvas, yours[0], 136, 106, dt_ms)

        # Message box.
        ui.textbox(canvas, (0, 146, W, H - 146))
        l1, l2 = self._battle_lines(d, foes, yours)
        self.font.draw(canvas, l1, (12, 156), t['text'], t['text_shadow'])
        self.font.draw(canvas, l2, (12, 170), t['text'], t['text_shadow'])

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

    def _battle_lines(self, d, foes, yours):
        b = d['battle']
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
