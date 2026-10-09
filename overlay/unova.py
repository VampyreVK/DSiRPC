"""
unova.py - the overlay's main view for Pokemon Black and White, in the
games' own look (overlay/unova_art.py cuts the art from the sprite sheets):

    header        the season (an animated icon), where you are, trainers beaten
                  and items found there, Repel steps, and the play time
    party         the six Pokemon in the party screen's chevron panels,
                  three to a row: name, gender, level, HP, status, held
                  item, shiny star; the lead's panel is the brighter one,
                  a fainted one's is red, an egg's green
    achievements  the RetroAchievements progress, the latest unlock (left
                  two thirds) and one still to earn (right third), as on
                  the game card
    footer        your trainer walking the way you face, name and money,
                  the eight Unova badges (as polished as you keep them, dull
                  until earned), the Pokedex

The achievements panel gives way to the Battle Subway's streaks, the Battle
Institute's rank, or the Elite Four you've beaten, in those places. The
season plays over all of it (overlay/seasons.py): petals, sunbeams and
fireflies, falling leaves, snow piling up on the panels, by the game's
clock.

Everything comes from the Black/White parser's state (core/bw_parser.py),
which is laid out like the Platinum parser's, plus 'season' and the
RetroAchievements keys the game card uses (core/other_game.py's
ra_summary). The battle view is the shared one in overlay/scenes.py, with
these games' own background and turfs (overlay/unova_backdrop.py; see
draw_backdrop, draw_platforms), HUD (foe_hud, your_hud, message_band) and
trainer intro (trainer_intro).
"""

import math
import time

import pygame

from core import bw_data
from . import ui
from .party_screen import CARD_GAP, CARD_POS, CARD_TRAY, draw_tray
from .gamecard import NEW_FOR_S, NEXT_EVERY_MS, ago
from .seasons import SeasonFX
from .unova_backdrop import UnovaBackdrop

W, H = 256, 192
HEADER_H = 14
SLOT_W, SLOT_H = 84, 46
ICON_BOX = (34, 31)  # the most a party icon is shown at (canvas pixels)
SLOT_POS = [(1 + (i % 3) * (SLOT_W + 1), 15 + (i // 3) * (SLOT_H + 1)) for i in range(6)]
NAME_X = 11                # the name's left edge in a panel
HP_RIGHT = 9               # the HP bar's and numbers' gap to the panel's right edge
ACH_RECT = (1, 110, 254, 51)
ACH_SPLIT = 168            # the divider between the latest unlock and the one to earn
FOOTER_Y = 162
TRAINER_MS = 2200          # a leader stands on the far turf this long at the start
TRAINER_OUT_MS = 400       # then steps off to the right
TITLES = {'gym': 'Gym Leader', 'elite': 'Elite Four', 'champion': 'Champion'}
# In a double battle your two Pokemon stand this much lower (left, right)
# than a single one, so they keep clear of the HP bars above them; the right
# one is nearer the camera (lower, and drawn in front).
DOUBLES_DROP = (0, 6)

BADGES = ['Trio', 'Basic', 'Insect', 'Bolt', 'Quake', 'Jet', 'Freeze', 'Legend']

# The party screen's colours, for what's drawn in code around the art.
CYAN = (99, 231, 255)
CYAN_LO = (24, 120, 160)
INK = (10, 16, 24)
BOX = (14, 26, 38)
BOX_HI = (34, 56, 74)
WHITE = (248, 248, 248)
SHADOW = (16, 24, 32)
MUTED = (150, 172, 186)
GOLD = (248, 208, 72)

# The Battle HUD sheet's colours.
HUD_INK = (32, 32, 32)
HUD_WHITE = (248, 248, 248)
HUD_LIGHT = (208, 208, 208)
HUD_MID = (96, 96, 96)
HUD_DARK = (48, 48, 48)
HUD_PLATE = (49, 49, 49)
HUD_HP = (0, 248, 72)
HUD_GAUGE = [((0, 255, 74), (0, 189, 33)), ((234, 255, 0), (173, 189, 0)), ((255, 0, 0), (189, 0, 0))]
HUD_EMPTY = ((255, 255, 255), (181, 181, 181))
HUD_LV = (248, 168, 0)
HUD_FOE_W = 120            # the foe's bar, from the left edge to its tip
BAND = (16, 18, 26, 218)   # the message band (see-through)
BAND_EDGE, BAND_EDGE_LO = (152, 40, 56), (72, 20, 30)

SEASONS = ['spring', 'summer', 'autumn', 'winter']
_ITEM = ([".##.", "#oo#", "#oo#", ".##."], {'#': (120, 72, 40), 'o': (232, 184, 96)})
# Small icons for the header and HUD.
_BALL = ([".kkk.", "krrrk", "kkwkk", "kwwwk", ".kkk."],
         {'k': (24, 24, 32), 'r': (232, 64, 56), 'w': (240, 240, 240)})
_BIG_BALL = (["..kkkkk..", ".krRrrrk.", "krrrrrrrk", "krrrrrrrk", "kkkkwkkkk", "kwwkWkwwk", "kwwwkwwwk",
              ".kwwwwwk.", "..kkkkk.."],
             {'k': (24, 24, 32), 'r': (232, 64, 56), 'R': (255, 168, 160), 'w': (236, 236, 240), 'W': (255, 255, 255)})
_TRAINER = ([".hh.", ".ff.", "bbbb", ".bb.", ".ll.", "l..l"],
            {'h': (220, 72, 72), 'f': (248, 208, 168), 'b': (72, 120, 216), 'l': (60, 60, 80)})
_REPEL = (["..k", ".pp", "pPp", "pPp", "pPp", "ppp"], {'k': (180, 180, 190), 'p': (160, 88, 200), 'P': (220, 168, 248)})
_TRAIN = (["kkkkkk.", "kwkwkk.", "kkkkkkk", ".o..o.."], {'k': (88, 140, 220), 'w': (220, 240, 255), 'o': (40, 40, 48)})


def season_of(d):
    """'spring' .. 'winter': the parser's, else from the DS clock's month
    (a new season every month, January is spring), else the PC's."""
    s = d.get('season')
    if s in SEASONS:
        return s
    try:
        month = int((d.get('misc') or {}).get('clock', '').split('-')[1])
    except (IndexError, ValueError, AttributeError):
        month = time.localtime().tm_mon
    return SEASONS[(month - 1) % 4]


def bw_box(surf, rect, fill=BOX, border=CYAN, hi=BOX_HI):
    """A dark box with cut corners and a cyan rim, like the party panels."""
    x, y, w, h = rect
    pts = [(x + 3, y), (x + w - 4, y), (x + w - 1, y + 3), (x + w - 1, y + h - 4),
           (x + w - 4, y + h - 1), (x + 3, y + h - 1), (x, y + h - 4), (x, y + 3)]
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, border, pts, 1)
    pygame.draw.line(surf, hi, (x + 3, y + 1), (x + w - 4, y + 1))


class UnovaScreen:
    def __init__(self, owner, art):
        """owner: the scenes.Overlay (its fonts, sprites and HP sliding);
        art: an overlay/unova_art.UnovaArt."""
        self.o = owner
        self.art = art
        self.backdrop = UnovaBackdrop(art)
        self.fx = SeasonFX(toast=owner.toast)
        self.font = owner.font
        self.mini = owner.mini
        self.walk_until = 0
        self.last_pos = None
        self.now = 0               # the frame's time (set by the battle view), for pulses

    # -- main view -------------------------------------------------------------

    def draw(self, canvas, d, t_ms, dt_ms):
        panels = [(i, (x, y, SLOT_W, SLOT_H)) for i, (x, y) in enumerate(SLOT_POS)] + [('ach', ACH_RECT)]
        self.fx.update(season_of(d), self.time_of_day(d), t_ms, panels)
        self._background(canvas)
        self._header(canvas, d, t_ms)
        party = (d.get('party') or [])[:len(SLOT_POS)]
        for i, (x, y) in enumerate(SLOT_POS):
            if i < len(party):
                self._slot(canvas, party[i], i, x, y, t_ms)
            else:
                p = self.art.panel('empty', SLOT_W)
                if p:
                    canvas.blit(p, (x, y))
        # The rest goes above the party icons, which the window may draw at
        # its own resolution (Overlay.blit_hires).
        canvas = self.o.lift(canvas)
        for i, mon in enumerate(party):
            self._slot_info(canvas, mon, i, *SLOT_POS[i], dt_ms)
        if d.get('league'):
            self._league(canvas, d, t_ms)
        elif d.get('subway'):
            self._subway(canvas, d['subway'], t_ms)
        elif d.get('institute'):
            self._institute(canvas, d['institute'], t_ms)
        else:
            self._achievements(canvas, d, t_ms)
        self.fx.draw_panels(canvas, panels)
        self._footer(canvas, d, t_ms)
        self.fx.draw_edges(canvas, HEADER_H, FOOTER_Y, t_ms)
        self.fx.draw_front(canvas, t_ms, bool(ui.THEME['chroma']))

    def draw_party_screen(self, canvas, d, t_ms, dt_ms):
        """The party screen (V): the whole screen for the party, each panel
        over a tray with its moves, nature and held item, the season as on
        the main view. `d`'s party has the battle's HP and PP in a battle
        (party_screen.live_party)."""
        party = (d.get('party') or [])[:len(CARD_POS)]
        panels = [(f'card{i}', (x, y, SLOT_W, SLOT_H)) for i, (x, y) in enumerate(CARD_POS)]
        self.fx.update(season_of(d), self.time_of_day(d), t_ms, panels)
        self._background(canvas)
        self._party_header(canvas, d, t_ms)
        for i, (x, y) in enumerate(CARD_POS):
            tray = (x, y + SLOT_H + CARD_GAP, SLOT_W, CARD_TRAY)
            if i < len(party):
                self._slot(canvas, party[i], i, x, y, t_ms)
                fainted = not party[i].get('egg') and party[i].get('curr_hp', 0) == 0
                bw_box(canvas, tray, border=(232, 96, 112) if fainted else CYAN_LO if i else CYAN)
            else:
                p = self.art.panel('empty', SLOT_W)
                if p:
                    canvas.blit(p, (x, y))
                bw_box(canvas, tray, fill=(10, 20, 32), border=(40, 70, 90), hi=(16, 30, 44))
        canvas = self.o.lift(canvas)
        for i, mon in enumerate(party):
            x, y = CARD_POS[i]
            self._slot_info(canvas, mon, i, x, y, dt_ms)
            draw_tray(canvas, self.mini, x + 5, y + SLOT_H + CARD_GAP, SLOT_W - 10, mon, WHITE, MUTED)
        self.fx.draw_panels(canvas, panels)
        self.fx.draw_edges(canvas, HEADER_H, H, t_ms)
        self.fx.draw_front(canvas, t_ms, bool(ui.THEME['chroma']))

    def _party_header(self, canvas, d, t_ms):
        """The party screen's header: a ball, PARTY, your name; a BATTLE tag
        when one is going on underneath, and the play time."""
        pygame.draw.rect(canvas, INK, (0, 0, W, HEADER_H + 1))
        pygame.draw.line(canvas, CYAN_LO, (0, HEADER_H), (W - 1, HEADER_H))
        self.fx.draw_header(canvas, HEADER_H, t_ms)
        rows, pal = _BALL
        ui.pixels(canvas, 4, 4, rows, pal)
        self.font.draw(canvas, "PARTY", (12, 3), GOLD, SHADOW)
        self.font.draw(canvas, d.get('trainer_name') or '', (12 + self.font.width("PARTY") + 6, 3), WHITE, SHADOW)
        pt = d.get('playtime') or {}
        right = W - 4 - self.font.draw(canvas, f"{pt.get('hours', 0)}:{pt.get('minutes', 0):02d}", (W - 4, 3),
                                       WHITE, SHADOW, align='right') - 6
        if (d.get('battle') or {}).get('active'):
            ui.chip(canvas, self.mini, right - self.mini.width("BATTLE") - 4, 4, "BATTLE", (200, 56, 64))

    def _background(self, canvas):
        t = ui.THEME
        grid = self.art.grid()
        if t['chroma']:
            canvas.fill(t['chroma'])
        elif grid:
            canvas.blit(grid, (0, 0))
        else:
            canvas.fill(INK)

    def _header(self, canvas, d, t_ms):
        pygame.draw.rect(canvas, INK, (0, 0, W, HEADER_H))
        pygame.draw.line(canvas, CYAN_LO, (0, HEADER_H - 1), (W - 1, HEADER_H - 1))
        self.fx.draw_header(canvas, HEADER_H, t_ms)
        self.fx.icon(canvas, 2, 2, t_ms)
        pt = d.get('playtime') or {}
        clock = f"{pt.get('hours', 0)}:{pt.get('minutes', 0):02d}"
        right = W - 4 - self.font.draw(canvas, clock, (W - 4, 3), WHITE, SHADOW, align='right') - 5
        # Chips, right to left: Repel steps, items found here, trainers
        # beaten here (the season shows only in its icon and effects).
        route = d.get('route') or {}
        chips = []
        if d.get('repel'):
            chips.append((_REPEL, str(d['repel']), (220, 168, 248)))
        for key, art in (('items', _BALL), ('trainers', _TRAINER)):
            if key in route:
                done, total = route[key]
                chips.append((art, f"{done}/{total}", GOLD if done == total else WHITE))
        for art, text, col in chips:
            tw = self.mini.width(text)
            self.mini.draw(canvas, text, (right - tw, 5), col)
            right -= tw + 2
            if art:
                rows_, pal_ = art
                ui.pixels(canvas, right - len(rows_[0]), 7 - len(rows_) // 2, rows_, pal_)
                right -= len(rows_[0]) + 5
        loc = d.get('location') or {}
        name = loc.get('name') or loc.get('area') or 'Somewhere in Unova'
        self.font.draw(canvas, self.font.fit(name, right - 13 - 4), (13, 3), WHITE, SHADOW)

    # -- party -----------------------------------------------------------------

    def _slot(self, canvas, mon, i, x, y, t_ms):
        """A party slot's panel and icon (_slot_info draws the rest)."""
        egg = mon.get('egg')
        fainted = not egg and mon.get('curr_hp', 0) == 0
        kind = 'egg' if egg else 'fainted' if fainted else 'normal'
        if i == 0:
            kind = 'lead' if kind == 'normal' else kind + '_lead'
        panel = self.art.panel(kind, SLOT_W)
        if panel:
            canvas.blit(panel, (x, y))
        else:
            bw_box(canvas, (x, y, SLOT_W, SLOT_H))

        # The icon in the panel's light corner, bobbing unless fainted:
        # shrunk to fit (at the window's resolution when it can, so it keeps
        # its detail).
        icon = self.o.sprites.party_icon(mon['species_id'], mon.get('shiny')) if not egg else None
        if icon:
            frame = icon.frame(t_ms + i * 137)
            fw, fh = frame.get_size()
            k = min(1.0, ICON_BOX[0] / fw, ICON_BOX[1] / fh)
            w, h = max(1, round(fw * k)), max(1, round(fh * k))
            bob = 0 if fainted else ui.bob(t_ms + i * 200, 900, 1)
            self.o.blit_hires(canvas, frame, (x + 18 - w // 2, y + SLOT_H - 4 - h + bob, w, h),
                              clip=(x + 2, y + 12, 32, SLOT_H - 14), dim=fainted)

    def _slot_info(self, canvas, mon, i, x, y, dt_ms):
        """A party slot's held item, name, level, status and HP."""
        egg = mon.get('egg')
        fainted = not egg and mon.get('curr_hp', 0) == 0
        if mon.get('item') and mon['item'] not in ('None', '#0') and not egg:
            rows, pal = _ITEM
            ui.pixels(canvas, x + 28, y + 37, rows, pal)

        # Text keeps clear of the panel's cut corners (9 px diagonals).
        name = 'Egg' if egg else mon.get('nickname') or mon.get('species') or '?'
        star = self.art.shiny_star() if mon.get('shiny') and not egg else None
        room = SLOT_W - NAME_X - 8 - (10 if star else 0)
        sym, scol = (None, None) if egg else ui.gender_symbol(self.font, mon.get('gender'))
        nw = self.font.draw(canvas, self.font.fit(name, room - (7 if sym else 0)), (x + NAME_X, y + 4), WHITE, SHADOW)
        if sym:
            self.font.draw(canvas, sym, (x + NAME_X + 1 + nw, y + 4), scol, SHADOW)
        if star:
            canvas.blit(star, (x + SLOT_W - 17, y + 5))
        if egg:
            self.mini.draw(canvas, "HATCHING", (x + 36, y + 20), MUTED)
            self.mini.draw(canvas, "SOON...", (x + 36, y + 28), MUTED)
            return

        self.mini.draw(canvas, "Lv", (x + 36, y + 17), GOLD)
        lw = self.font.draw(canvas, str(mon.get('level', '?')), (x + 44, y + 14), WHITE, SHADOW)
        status = 'Fainted' if fainted else mon.get('status')
        tag = self.art.status_tag(status) if status else None
        if tag:
            canvas.blit(tag, (x + 46 + lw + 3, y + 17))
        elif status:
            ui.status_tag(canvas, self.mini, x + 46 + lw + 2, y + 15, status)
        max_hp = max(1, mon.get('max_hp', 1))
        hp = self.o._hp(('bw', i, mon['species_id']), mon.get('curr_hp', 0), max_hp, dt_ms)
        ui.hp_bar(canvas, self.mini, x + 35, y + 26, SLOT_W - 35 - HP_RIGHT, hp / max_hp)
        self.font.draw(canvas, f"{int(round(hp))}/{mon.get('max_hp', 0)}", (x + SLOT_W - HP_RIGHT - 1, y + 34),
                       WHITE, SHADOW, align='right')

    # -- achievements ----------------------------------------------------------

    def _achievements(self, canvas, ra, t_ms):
        """ra: the state (its RetroAchievements keys)."""
        x, y, w, h = ACH_RECT
        bw_box(canvas, ACH_RECT)
        rs = (ra or {}).get('ra_set')
        achs = rs.playable_achievements if rs else []
        p = (ra or {}).get('progress')
        ui.trophy(canvas, x + 5, y + 4, earned=bool(p and p[0]))
        if not rs:
            self.font.draw(canvas, "Achievements", (x + 17, y + 3), WHITE, SHADOW)
            note = ((ra or {}).get('ra_note') or "No RetroAchievements set loaded").rstrip('.') + '.'
            for k, line in enumerate(self.font.wrap(note + " Run Setup.bat to add it.", w - 12, 3)):
                self.font.draw(canvas, line, (x + 6, y + 17 + 11 * k), MUTED, SHADOW)
            return

        unlocked = (ra or {}).get('unlocked') or ()
        count = f"{p[0]}/{p[1]}" if p else f"-/{len(achs)}"
        cw = self.font.draw(canvas, count, (x + 17, y + 3), WHITE, SHADOW)
        pts = sum(a['points'] for a in achs if a['id'] in unlocked) if p else None
        ptext = f"{pts} PTS" if pts is not None else "SIGN IN"
        pw = self.mini.width(ptext)
        self.mini.draw(canvas, ptext, (x + w - 6 - pw, y + 5), GOLD)
        ui.meter(canvas, self.mini, x + 17 + cw + 6, y + 4, w - 17 - cw - 6 - pw - 12,
                 p[0] / max(1, p[1]) if p else 0)
        pygame.draw.line(canvas, CYAN_LO, (x + 5, y + 14), (x + w - 6, y + 14))
        if not achs:
            self.font.draw(canvas, "This set has no achievements yet.", (x + 6, y + 19), MUTED, SHADOW)
            return

        by_id = {a['id']: a for a in achs}
        latest = (ra or {}).get('latest') or ((ra or {}).get('recent') or [None])[-1]
        if latest and latest[0] not in by_id:
            latest = None
        pygame.draw.line(canvas, CYAN_LO, (x + ACH_SPLIT, y + 17), (x + ACH_SPLIT, y + h - 4))
        self._latest(canvas, by_id[latest[0]] if latest else None, latest[1] if latest else 0, bool(p), t_ms)
        locked = [a for a in achs if a['id'] not in unlocked]
        rx, rw = x + ACH_SPLIT + 5, w - ACH_SPLIT - 10
        if p and not locked:
            ui.chip(canvas, self.mini, rx, y + 18, "MASTERED", ui.THEME['ach_lo'])
            self.font.draw(canvas, "Every one!", (rx, y + 30), WHITE, SHADOW)
            ui.sparkle(canvas, x + w - 10, y + 22, t_ms)
        elif locked:
            a = locked[(t_ms // NEXT_EVERY_MS) % len(locked)]
            cw = ui.chip(canvas, self.mini, rx, y + 18, "NEXT", CYAN_LO)
            pts = f"{a['points']}"
            self.mini.draw(canvas, pts, (rx + rw - self.mini.width(pts), y + 20), GOLD)
            for k, line in enumerate(self.font.wrap(a['title'], rw, 2)):
                self.font.draw(canvas, line, (rx, y + 29 + 10 * k), WHITE, SHADOW)

    def _league(self, canvas, d, t_ms):
        """In the Elite Four's and the Champion's rooms: who's beaten this
        challenge, and who's in this room."""
        x, y, w, h = ACH_RECT
        bw_box(canvas, ACH_RECT, fill=(26, 18, 40), border=(200, 160, 255), hi=(56, 40, 84))
        lg = d['league']
        beaten = set(lg.get('beaten') or ())
        self.font.draw(canvas, "Elite Four", (x + 6, y + 3), WHITE, SHADOW)
        count = f"{len(beaten)}/4"
        self.font.draw(canvas, count, (x + w - 6, y + 3), GOLD if len(beaten) == 4 else WHITE, SHADOW, align='right')
        names = list(bw_data.ELITE_ORDER) + [bw_data.CHAMPION]
        slot = (w - 12) // len(names)
        for i, name in enumerate(names):
            cx = x + 6 + slot * i + slot // 2
            here = name == lg.get('here')
            done = name in beaten
            if here:  # the one in this room glows
                glow = pygame.Surface((30, 30), pygame.SRCALPHA)
                a = 90 + int(60 * math.sin(t_ms / 260))
                pygame.draw.ellipse(glow, (255, 210, 120, a), (0, 0, 30, 30))
                canvas.blit(glow, (cx - 15, y + 14))
            face = self.art.portrait(name, 22)
            if face:
                if not done and not here:
                    face = face.copy()
                    face.fill((70, 70, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
                canvas.blit(face, (cx - 11, y + 15))
            if done:
                pygame.draw.lines(canvas, (120, 240, 140), False, [(cx + 5, y + 30), (cx + 8, y + 33), (cx + 13, y + 26)], 2)
            label = name.upper()[:8]
            self.mini.draw(canvas, label, (cx - self.mini.width(label) // 2, y + 40),
                           GOLD if here else WHITE if done else MUTED)

    def _subway(self, canvas, sw, t_ms):
        """In the Battle Subway: the train you're on, its streak and record."""
        x, y, w, h = ACH_RECT
        bw_box(canvas, ACH_RECT, fill=(12, 26, 44), border=(120, 190, 255), hi=(32, 56, 84))
        rows, pal = _TRAIN
        ui.pixels(canvas, x + 6 + (t_ms // 120) % 3 - 1, y + 5, rows, pal)
        title = f"Battle Subway: {sw['train']} Train" if sw.get('train') else "Battle Subway"
        self.font.draw(canvas, self.font.fit(title, w - 70), (x + 16, y + 3), WHITE, SHADOW)
        bp = f"{sw.get('bp', 0)} BP"
        self.mini.draw(canvas, bp, (x + w - 6 - self.mini.width(bp), y + 5), GOLD)
        pygame.draw.line(canvas, CYAN_LO, (x + 5, y + 14), (x + w - 6, y + 14))
        for k, (label, value) in enumerate((("STREAK", sw.get('streak', 0)), ("RECORD", sw.get('record', 0)))):
            cx = x + 8 + k * 84
            self.mini.draw(canvas, label, (cx, y + 19), MUTED)
            big = str(value)
            hot = k == 0 and value and value >= sw.get('record', 0)
            num = pygame.Surface((self.font.width(big) + 1, self.font.height + 1), pygame.SRCALPHA)
            self.font.draw(num, big, (0, 0), GOLD if hot else WHITE, HUD_INK)
            canvas.blit(pygame.transform.scale_by(num, 2), (cx, y + 26))
        # this set of seven: one car lit per battle won, the next one blinking
        streak = sw.get('streak', 0) or 0
        done, sx = streak % 7, x + 134
        self.mini.draw(canvas, f"SET {streak // 7 + 1}", (sx, y + 19), MUTED)
        for c in range(7):
            lit = c < done or (c == done and (t_ms // 400) % 2)
            pygame.draw.rect(canvas, GOLD if c < done else (CYAN_LO if lit else HUD_INK), (sx + c * 7, y + 28, 6, 4))
            canvas.fill(MUTED, (sx + c * 7 + 1, y + 32, 1, 1))
            canvas.fill(MUTED, (sx + c * 7 + 4, y + 32, 1, 1))
        # the other trains you have streaks on
        others = [t for t in sw.get('trains') or () if t[0] != sw.get('train')][:3]
        for k, (name, cur, rec) in enumerate(others):
            text = f"{name.upper()[:12]} {cur}/{rec}"
            self.mini.draw(canvas, text, (x + w - 6 - self.mini.width(text), y + 19 + 9 * k), MUTED)

    def _institute(self, canvas, inst, t_ms):
        """In the Battle Institute: your rank and points."""
        x, y, w, h = ACH_RECT
        bw_box(canvas, ACH_RECT, fill=(36, 22, 16), border=(255, 196, 120), hi=(70, 44, 30))
        self.font.draw(canvas, "Battle Institute", (x + 6, y + 3), WHITE, SHADOW)
        rank = inst.get('rank', 'Beginner')
        self.font.draw(canvas, rank, (x + w - 6, y + 3), GOLD, SHADOW, align='right')
        pts = inst.get('points', 0)
        floor = next(f for f, n in bw_data.INSTITUTE_RANKS if pts >= f)
        nxt = next((f for f, n in reversed(bw_data.INSTITUTE_RANKS) if f > pts), None)
        frac = 1.0 if nxt is None else (pts - floor) / max(1, nxt - floor)
        ui.meter(canvas, self.mini, x + 6, y + 18, w - 12, frac, label="RANK")
        self.font.draw(canvas, f"{pts} points", (x + 6, y + 30), WHITE, SHADOW)
        if nxt is not None:
            text = f"{nxt - pts} TO {next(n for f, n in bw_data.INSTITUTE_RANKS if f == nxt).upper()}"
            self.mini.draw(canvas, text, (x + w - 6 - self.mini.width(text), y + 32), MUTED)

    def _latest(self, canvas, a, when, have_progress, t_ms):
        x, y, w, h = ACH_RECT
        lx, lw = x + 6, ACH_SPLIT - 10
        if not a:
            msg = "Nothing earned yet. Your next unlock shows up here." if have_progress else \
                "Sign in to RetroAchievements (Setup.bat) to see your progress."
            for k, line in enumerate(self.font.wrap(msg, lw, 3)):
                self.font.draw(canvas, line, (lx, y + 18 + 10 * k), MUTED, SHADOW)
            return
        new = when and time.time() - when < NEW_FOR_S
        cw = ui.chip(canvas, self.mini, lx, y + 18, "NEW" if new else "LATEST", ui.THEME['ach_lo'])
        when_text = ago(when).upper() if when else ''
        ww = self.mini.width(when_text)
        if when_text:
            self.mini.draw(canvas, when_text, (lx + lw - ww, y + 20), GOLD)
        title = self.font.fit(a['title'], lw - cw - 4 - (ww + 4 if when_text else 0))
        self.font.draw(canvas, title, (lx + cw + 4, y + 17), WHITE, SHADOW)
        if new:
            ui.sparkle(canvas, lx + cw + 6 + self.font.width(title), y + 17, t_ms)
        for k, line in enumerate(self.font.wrap(a.get('description') or '', lw, 2)):
            self.font.draw(canvas, line, (lx, y + 29 + 10 * k), MUTED, SHADOW)

    # -- battle ----------------------------------------------------------------

    def time_of_day(self, d):
        """'morning', 'day', 'evening' or 'night' by the clock (the game's,
        when it could be read) and the season's hours."""
        return bw_data.time_of_day((d.get('misc') or {}).get('clock'), season_of(d))

    def terrain(self, d):
        """(sky, platform) for the battle's place and season."""
        return bw_data.terrain(d.get('location') or {}, season_of(d))

    def weather(self, d):
        """The field's weather as the battle view's weather particles, or
        None (and never under a roof)."""
        if self.terrain(d)[0] in ('cave', 'indoor'):
            return None
        return (d.get('location') or {}).get('weather_kind')

    def draw_backdrop(self, canvas, d, when, t_ms):
        """The battle's background (overlay/unova_backdrop.py), by place,
        season and time of day; its particles rest while weather falls."""
        t = ui.THEME
        if t['chroma']:
            canvas.fill(t['chroma'])
            return
        self.backdrop.draw(canvas, self.terrain(d)[0], when, t_ms, particles=not self.weather(d))

    def draw_platforms(self, canvas, d, when, far_dx, near_dx):
        """The two turfs, slid by the intro's offsets. Returns where each
        side's Pokemon stand: {'foe': (x, y), 'you': (x, y)} (feet)."""
        return self.backdrop.draw_turfs(canvas, self.terrain(d)[1], when, far_dx, near_dx)

    def trainer_intro(self, d):
        """For a battle against a Gym Leader, an Elite Four member or the
        Champion: {'image': their battle sprite, 'name': 'Gym Leader
        LENORA'}; otherwise None."""
        b = d['battle']
        if b.get('wild') or not b.get('trainer'):
            return None
        img = self.art.battle_trainer(b['trainer'])
        if img is None:
            return None
        return {'image': img, 'name': f"{TITLES.get(b.get('kind'), '')} {b['trainer'].upper()}".strip()}

    def draw_trainer(self, canvas, intro, feet, t_ms):
        """The trainer standing at `feet` until intro['out_at'], then
        stepping off to the right."""
        out = intro['out_at']
        if t_ms >= out + TRAINER_OUT_MS:
            return
        img = intro['image']
        dx = 0 if t_ms < out else int((t_ms - out) / TRAINER_OUT_MS * 140)
        canvas.blit(img, (feet[0] - img.get_width() // 2 + dx, feet[1] - img.get_height() + 2))

    # -- battle HUD ------------------------------------------------------------
    #
    # Black and White's battle boxes, drawn in code in the Battle HUD
    # sheet's colours and shapes: a thin white bar with an arrow tip and a
    # dark underside, the name riding above it; the foe's runs in from the
    # left edge, yours from the right with a dark plate under it for the HP
    # numbers. Messages sit on a dark band with maroon edges.

    def _hud_bar(self, canvas, x0, x1, y, tip):
        """The bar body, 9 rows from y, between x0 and x1, with its arrow
        tip past x1 (tip='right') or before x0 (tip='left')."""
        rows = [HUD_MID, HUD_WHITE, HUD_WHITE, HUD_WHITE, HUD_LIGHT, HUD_MID, HUD_DARK, HUD_DARK, HUD_INK]
        for r, c in enumerate(rows):
            reach = r if r <= 5 else 10 - r   # the tip: out to 5 px at the white's bottom, back under it
            if tip == 'right':
                pygame.draw.line(canvas, c, (x0, y + r), (x1 + reach, y + r))
                canvas.set_at((x1 + reach + 1, y + r), HUD_INK)
            else:
                pygame.draw.line(canvas, c, (x0 - reach, y + r), (x1, y + r))
                canvas.set_at((x0 - reach - 1, y + r), HUD_INK)

    def _hud_gauge(self, canvas, x, y, width, frac):
        """'HP' on its dark plate, then the gauge, inside a bar at row y."""
        pygame.draw.rect(canvas, HUD_DARK, (x, y, 13, 6))
        self.mini.draw(canvas, "HP", (x + 2, y + 1), HUD_HP)
        gx, gw = x + 13, width - 13
        pygame.draw.rect(canvas, HUD_DARK, (gx, y, gw, 5))
        pygame.draw.rect(canvas, HUD_EMPTY[0], (gx + 1, y + 1, gw - 2, 2))
        pygame.draw.line(canvas, HUD_EMPTY[1], (gx + 1, y + 3), (gx + gw - 2, y + 3))
        frac = max(0.0, min(1.0, frac))
        fill = int(round((gw - 2) * frac))
        if frac > 0 and fill == 0:
            fill = 1
        if fill:
            hi, lo = HUD_GAUGE[0 if frac > 0.5 else 1 if frac > 0.2 else 2]
            pygame.draw.rect(canvas, hi, (gx + 1, y + 1, fill, 2))
            pygame.draw.line(canvas, lo, (gx + 1, y + 3), (gx + fill, y + 3))

    def _hp_pulse(self, canvas, rect, frac, hp):
        """A red glow pulsing behind a bar whose HP is in the red."""
        if hp <= 0 or frac > 0.2:
            return
        x, y, w, h = rect
        a = int(70 + 70 * (0.5 + 0.5 * math.sin(self.now / 140)))
        glow = pygame.Surface((w + 6, h + 6), pygame.SRCALPHA)
        for k, alpha in ((0, a // 3), (1, a // 2), (2, a)):
            pygame.draw.rect(glow, (255, 40, 40, alpha), (k, k, w + 6 - 2 * k, h + 6 - 2 * k), border_radius=4)
        canvas.blit(glow, (x - 3, y - 3))

    def draw_catch(self, canvas, feet, age):
        """A wild Pokemon being caught, `age` ms after the catch: the ball
        drops, wobbles three times, clicks shut in a burst of stars."""
        rows, pal = _BIG_BALL
        x, y = feet[0] - 4, feet[1] - 9
        if age < 250:
            y -= int((250 - age) / 250 * 30)
        dx = 0
        if 400 <= age < 1600:
            phase = (age - 400) % 400
            dx = int(round(math.sin(phase / 400 * math.pi * 2) * 2)) if phase < 260 else 0
        ui.pixels(canvas, x + dx, y, rows, pal)
        if age >= 1600:
            burst = age - 1600
            if burst < 700:
                for k in range(6):
                    ang = k / 6 * 2 * math.pi
                    r = 4 + burst / 700 * 14
                    ui.sparkle(canvas, int(x + 4 + math.cos(ang) * r), int(y + 4 + math.sin(ang) * r), burst + k * 60)

    def _hud_name(self, canvas, m, x, y, right):
        """Name and gender from x, 'Lv' and level ending at `right`."""
        sym, scol = ui.gender_symbol(self.font, m.get('gender'))
        lv = str(m.get('level', '?'))
        lw = self.font.width(lv) + 9
        room = right - x - lw - 4 - (7 if sym else 0)
        nw = self.font.draw(canvas, self.font.fit(m['nickname'], room), (x, y), WHITE, HUD_INK)
        if sym:
            self.font.draw(canvas, sym, (x + nw + 1, y), scol, HUD_INK)
        self.mini.draw(canvas, "Lv", (right - lw, y + 3), HUD_LV)
        self.font.draw(canvas, lv, (right, y), WHITE, HUD_INK, align='right')

    def _hud_status(self, canvas, m, x, y):
        tag = self.art.status_tag(m.get('status')) if m.get('status') else None
        if tag:
            canvas.blit(tag, (x, y))
            return tag.get_width() + 2
        return 0

    def foe_hud(self, canvas, m, x, y, hp, chips):
        """The foe's box with its top at y, sliding in with x (its usual x
        is 4). chips(canvas, m, x, y, width) draws stat-change chips and
        returns their height. Returns the box's height."""
        left = x - 4
        end = left + HUD_FOE_W
        nx = left + 4
        if m.get('owned'):  # a wild Pokemon you've caught before
            rows, pal = _BALL
            ui.pixels(canvas, nx, y + 2, rows, pal)
            nx += 7
        self._hud_name(canvas, m, nx, y, end - 2)
        by = y + 11
        self._hp_pulse(canvas, (left, by - 2, end + 8 - left, 13), hp / max(1, m['max_hp']), hp)
        self._hud_bar(canvas, left - 8, end, by, 'right')
        sx = left + 4 + self._hud_status(canvas, m, left + 4, by + 2)
        self._hud_gauge(canvas, max(sx, left + 26), by + 1, end - 4 - max(sx, left + 26), hp / max(1, m['max_hp']))
        return 20 + chips(canvas, m, left + 4, y + 21, HUD_FOE_W - 8)

    def your_hud(self, canvas, m, x, bottom, hp, chips, numbers=True):
        """Your box with its bottom at `bottom`, sliding in with x (its
        usual x is 136). Without numbers (doubles) it's just the bar.
        Returns its height."""
        left = x - 8
        rows = len(ui.chip_rows(self.mini, ui.stage_chips(m), W - left - 16))
        h = (29 if numbers else 20) + 10 * rows
        y = bottom - h
        self._hud_name(canvas, m, left + 8, y, W - 4)
        by = y + 11
        self._hp_pulse(canvas, (left - 8, by - 2, W - left + 8, 13), hp / max(1, m['max_hp']), hp)
        self._hud_bar(canvas, left, W + 8, by, 'left')
        sx = left + 6 + self._hud_status(canvas, m, left + 6, by + 2)
        gx = max(sx, left + 30)
        self._hud_gauge(canvas, gx, by + 1, W - 6 - gx, hp / max(1, m['max_hp']))
        if numbers:
            # The dark plate under the bar, its left edge slanting out.
            for r in range(8):
                pygame.draw.line(canvas, HUD_PLATE, (left + 14 - r, by + 9 + r), (W, by + 9 + r))
            pygame.draw.line(canvas, HUD_INK, (left + 6, by + 17), (W, by + 17))
            self.font.draw(canvas, f"{int(round(hp))}/{m['max_hp']}", (W - 6, by + 9), WHITE, HUD_INK,
                           align='right')
        chips(canvas, m, left + 8, y + h - 10 * rows, W - left - 16)
        return h

    def message_band(self, canvas, rect):
        """The message box: a dark see-through band with maroon edges."""
        x, y, w, h = rect
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        band.fill(BAND)
        canvas.blit(band, (x, y))
        for yy, c in ((y, BAND_EDGE), (y + 1, BAND_EDGE_LO), (y + h - 2, BAND_EDGE_LO), (y + h - 1, BAND_EDGE)):
            pygame.draw.line(canvas, c, (x, yy), (x + w - 1, yy))

    def message_text(self, canvas, l1, l2):
        self.font.draw(canvas, l1, (12, 156), WHITE, HUD_INK)
        self.font.draw(canvas, l2, (12, 170), WHITE, HUD_INK)

    def move_button(self, rect, canvas, name, mtype=None, pp=None, pp_max=None, selected=False, effect=None):
        """A move on the band: a dark button with its type's colour as a
        stripe and a glow when it was the one used last."""
        x, y, w, h = rect
        if name is None:
            pygame.draw.rect(canvas, (44, 46, 54), rect)
            pygame.draw.rect(canvas, (70, 72, 82), rect, 1)
            self.font.draw(canvas, "-", (x + 8, y + 5), (110, 114, 124), HUD_INK)
            return
        c = ui.TYPE_COLORS.get(mtype, (150, 150, 150))
        pygame.draw.rect(canvas, ui.darken(c, 70) if not selected else ui.darken(c, 30), rect)
        pygame.draw.rect(canvas, ui.darken(c, 40) if not selected else c, (x + 1, y + 1, w - 2, h // 2 - 1))
        pygame.draw.rect(canvas, c, (x, y, 4, h))
        pygame.draw.rect(canvas, WHITE if selected else ui.darken(c, 100), rect, 1)
        self.font.draw(canvas, name, (x + 8, y + 5), WHITE, HUD_INK)
        if pp is not None and pp_max:
            frac = pp / pp_max
            col = WHITE if frac > 0.5 else (248, 224, 96) if frac > 0.25 else (248, 160, 72) if pp else (248, 96, 88)
            text = f"{pp}/{pp_max}"
            self.mini.draw(canvas, text, (x + w - 5 - self.mini.width(text), y + 7), col)
            self.mini.draw(canvas, "PP", (x + w - 16 - self.mini.width(text), y + 7), ui.lighten(c, 70))
        label = ui.EFFECT_LABELS.get(effect)
        if label:
            text, lc = label
            lw = self.mini.width(text) + 4
            lx = x + w - 3 - lw
            pygame.draw.rect(canvas, ui.darken(lc, 60), (lx - 1, y, lw + 2, 7))
            pygame.draw.rect(canvas, lc, (lx, y + 1, lw, 5))
            self.mini.draw(canvas, text, (lx + 2, y + 1), WHITE)

    # -- footer ----------------------------------------------------------------

    def _footer(self, canvas, d, t_ms):
        pygame.draw.rect(canvas, INK, (0, FOOTER_Y, W, H - FOOTER_Y))
        pygame.draw.line(canvas, CYAN_LO, (0, FOOTER_Y), (W - 1, FOOTER_Y))

        # Your trainer, walking, running or riding the bike as you do (the
        # hub's `gait`; without one, walking a moment when you move).
        loc = d.get('location') or {}
        facing = loc.get('facing') if loc.get('facing') in ('up', 'down', 'left', 'right') else 'down'
        gait = loc.get('gait')
        if gait is None:
            pos = (loc.get('map_id'), loc.get('x'), loc.get('z'), facing)
            if self.last_pos is not None and pos != self.last_pos:
                self.walk_until = t_ms + 700
            self.last_pos = pos
            style, moving = 'walk', t_ms < self.walk_until
        else:
            style = gait if gait in ('run', 'bike', 'bike_stop') else 'walk'
            moving = gait in ('walk', 'run', 'bike')
        character = d.get('character') or 'Hilbert'
        anim = self.o.sprites.trainer(character, facing, style) or self.o.sprites.trainer(character, facing)
        if anim:
            frame = anim.frame(t_ms) if moving else anim.frames[0]
            canvas.blit(frame, (16 - frame.get_width() // 2, H + 1 - frame.get_height()))  # clear of the border

        name = d.get('trainer_name') or ''
        self.font.draw(canvas, self.font.fit(name, 62), (32, FOOTER_Y + 4), WHITE, SHADOW)
        self.font.draw(canvas, self.font.fit(f"${d.get('money', 0):,}", 62), (32, FOOTER_Y + 16), GOLD, SHADOW)

        # The badges, bottoms lined up.
        # The badges, bottoms lined up, as polished as you keep them (the
        # trainer card's dull, clean and polished art); polished ones glint.
        earned = set(d.get('badges') or ())
        shine = d.get('badge_shine')
        bx = 98
        for i, badge in enumerate(BADGES):
            row = (shine[i] if shine else 2) if badge in earned else 0
            img = self.art.small_badge(i, row)
            if img is None:
                ui.badge_pip(canvas, bx + 3, FOOTER_Y + 12, i, badge in earned)
                bx += 11
                continue
            if badge not in earned:
                img = img.copy()
                img.fill((90, 90, 100, 150), special_flags=pygame.BLEND_RGBA_MULT)
            by = H - 4 - img.get_height()
            canvas.blit(img, (bx, by))
            if badge in earned and row == 2 and (t_ms // 140 + i * 7) % 40 < 6:
                ui.sparkle(canvas, bx + img.get_width() // 2 + (i % 3) - 1, by + 4 + (i * 5) % 12, t_ms, (255, 255, 240))
            elif badge in earned and row == 0:
                for k in range(3):  # a little dust
                    canvas.set_at((bx + (k * 5 + i) % img.get_width(), by + 6 + k * 6), (150, 140, 120))
            bx += img.get_width() + 2

        dex = d.get('pokedex') or {}
        if dex.get('obtained', True):
            self.mini.draw(canvas, "CAUGHT", (W - 26, FOOTER_Y + 7), GOLD)
            self.font.draw(canvas, str(dex.get('caught', 0)), (W - 29, FOOTER_Y + 5), WHITE, SHADOW, align='right')
            self.mini.draw(canvas, "SEEN", (W - 26, FOOTER_Y + 19), GOLD)
            self.font.draw(canvas, str(dex.get('seen', 0)), (W - 29, FOOTER_Y + 17), WHITE, SHADOW, align='right')
