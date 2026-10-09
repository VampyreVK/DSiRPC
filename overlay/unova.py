"""
unova.py - the overlay's main view for Pokemon Black and White, in the
games' own look (overlay/unova_art.py cuts the art from the sprite sheets):

    header        the season, where you are, and the play time
    party         the six Pokemon in the party screen's chevron panels,
                  three to a row: name, gender, level, HP, status, held
                  item, shiny star; the lead's panel is the brighter one,
                  a fainted one's is red, an egg's green
    achievements  the RetroAchievements progress, the latest unlock (left
                  two thirds) and one still to earn (right third), as on
                  the game card
    footer        your trainer walking the way you face, name and money,
                  the eight Unova badges (dull until earned), the Pokedex

Everything comes from the Black/White parser's state (core/bw_parser.py),
which is laid out like the Platinum parser's, plus 'season' and the
RetroAchievements keys the game card uses (core/other_game.py's
ra_summary). The battle view is the shared one in overlay/scenes.py, with
these games' own sky and platforms (draw_backdrop, draw_platforms).
"""

import time

import pygame

from core import bw_data
from . import ui
from .gamecard import NEW_FOR_S, NEXT_EVERY_MS, ago

W, H = 256, 192
HEADER_H = 14
SLOT_W, SLOT_H = 84, 46
SLOT_POS = [(1 + (i % 3) * (SLOT_W + 1), 15 + (i // 3) * (SLOT_H + 1)) for i in range(6)]
ACH_RECT = (1, 110, 254, 51)
ACH_SPLIT = 168            # the divider between the latest unlock and the one to earn
FOOTER_Y = 162
BOX_TOP = 146              # the battle view's message box
FAR_PLATFORM = (190, 106)  # centre x, bottom y (as the Platinum battle view)
NEAR_PLATFORM_X = 0        # left edge; its top shows above the message box

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

SEASONS = ['spring', 'summer', 'autumn', 'winter']
# 7x7 season marks: a blossom, a sun, a leaf, a snowflake.
_SEASON_ART = {
    'spring': ([".#.#.", "#####", ".#o#.", "#####", ".#.#."], {'#': (248, 152, 192), 'o': (248, 232, 120)}),
    'summer': (["#.#.#", ".###.", "##o##", ".###.", "#.#.#"], {'#': (248, 168, 40), 'o': (248, 232, 120)}),
    'autumn': (["...##", "..###", ".###.", "###..", "#...."], {'#': (232, 112, 40)}),
    'winter': (["#.#.#", ".###.", "##.##", ".###.", "#.#.#"], {'#': (168, 220, 248)}),
}
_ITEM = ([".##.", "#oo#", "#oo#", ".##."], {'#': (120, 72, 40), 'o': (232, 184, 96)})


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
        self.font = owner.font
        self.mini = owner.mini
        self.walk_until = 0
        self.last_pos = None

    # -- main view -------------------------------------------------------------

    def draw(self, canvas, d, t_ms, dt_ms):
        self._background(canvas)
        self._header(canvas, d)
        party = d.get('party') or []
        for i, (x, y) in enumerate(SLOT_POS):
            if i < len(party):
                self._slot(canvas, party[i], i, x, y, t_ms, dt_ms)
            else:
                p = self.art.panel('empty', SLOT_W)
                if p:
                    canvas.blit(p, (x, y))
        self._achievements(canvas, d, t_ms)
        self._footer(canvas, d, t_ms)

    def _background(self, canvas):
        t = ui.THEME
        grid = self.art.grid()
        if t['chroma']:
            canvas.fill(t['chroma'])
        elif grid:
            canvas.blit(grid, (0, 0))
        else:
            canvas.fill(INK)

    def _header(self, canvas, d):
        pygame.draw.rect(canvas, INK, (0, 0, W, HEADER_H))
        pygame.draw.line(canvas, CYAN_LO, (0, HEADER_H - 1), (W - 1, HEADER_H - 1))
        season = season_of(d)
        rows, pal = _SEASON_ART[season]
        ui.pixels(canvas, 4, 4, rows, pal)
        pt = d.get('playtime') or {}
        clock = f"{pt.get('hours', 0)}:{pt.get('minutes', 0):02d}"
        cw = self.font.draw(canvas, clock, (W - 4, 3), WHITE, SHADOW, align='right')
        sw = self.mini.width(season.upper())
        self.mini.draw(canvas, season.upper(), (W - 4 - cw - 6 - sw, 5), pal['#'])
        loc = d.get('location') or {}
        name = loc.get('name') or loc.get('area') or 'Somewhere in Unova'
        self.font.draw(canvas, self.font.fit(name, W - 22 - cw - sw - 16), (13, 3), WHITE, SHADOW)

    # -- party -----------------------------------------------------------------

    def _slot(self, canvas, mon, i, x, y, t_ms, dt_ms):
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

        # The icon in the panel's light corner, bobbing unless fainted.
        icon = self.o.sprites.party_icon(mon['species_id'], mon.get('shiny')) if not egg else None
        if icon:
            frame = self.o._fit(icon.frame(t_ms + i * 137), 34, 32)
            if fainted:
                frame = frame.copy()
                frame.fill((130, 130, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
            clip = canvas.get_clip()
            canvas.set_clip((x + 2, y + 12, 32, SLOT_H - 14))
            bob = 0 if fainted else ui.bob(t_ms + i * 200, 900, 1)
            canvas.blit(frame, (x + 18 - frame.get_width() // 2, y + SLOT_H - 4 - frame.get_height() + bob))
            canvas.set_clip(clip)
        if mon.get('item') and mon['item'] not in ('None', '#0') and not egg:
            rows, pal = _ITEM
            ui.pixels(canvas, x + 28, y + 37, rows, pal)

        name = 'Egg' if egg else mon.get('nickname') or mon.get('species') or '?'
        star = self.art.shiny_star() if mon.get('shiny') and not egg else None
        room = SLOT_W - 10 - (9 if star else 0)
        sym, scol = (None, None) if egg else ui.gender_symbol(self.font, mon.get('gender'))
        nw = self.font.draw(canvas, self.font.fit(name, room - (7 if sym else 0)), (x + 6, y + 3), WHITE, SHADOW)
        if sym:
            self.font.draw(canvas, sym, (x + 7 + nw, y + 3), scol, SHADOW)
        if star:
            canvas.blit(star, (x + SLOT_W - 12, y + 4))
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
        ui.hp_bar(canvas, self.mini, x + 35, y + 26, SLOT_W - 39, hp / max_hp)
        self.font.draw(canvas, f"{int(round(hp))}/{mon.get('max_hp', 0)}", (x + SLOT_W - 5, y + 34),
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

    def draw_backdrop(self, canvas, d, when):
        """The battle's sky, by place, season and time of day."""
        t = ui.THEME
        if t['chroma']:
            canvas.fill(t['chroma'])
            return
        sky = self.art.sky(bw_data.terrain(d.get('location') or {}, season_of(d))[0], when)
        if not sky:
            canvas.fill(INK)
            return
        canvas.blit(sky, (0, 0))
        for y in range(sky.get_height(), BOX_TOP):  # down to the message box
            canvas.blit(sky, (0, y), (0, sky.get_height() - 1, sky.get_width(), 1))

    def draw_platforms(self, canvas, d, when, far_dx, near_dx):
        """The two platforms, slid by the intro's offsets. Returns where each
        side's Pokemon stand: {'foe': (x, y), 'you': (x, y)} (feet), or {}
        without the art."""
        far, near = self.art.platforms(bw_data.terrain(d.get('location') or {}, season_of(d))[1], when)
        if not far or not near:
            return {}
        cx, bottom = FAR_PLATFORM
        fx, fy = cx - far.get_width() // 2 + far_dx, bottom - far.get_height()
        canvas.blit(far, (fx, fy))
        nx, ny = NEAR_PLATFORM_X + near_dx, BOX_TOP - near.get_height()
        canvas.blit(near, (nx, ny))
        return {'foe': (cx + far_dx, fy + far.get_height() * 2 // 3),
                'you': (nx + near.get_width() * 9 // 20, ny + 21)}

    # -- footer ----------------------------------------------------------------

    def _footer(self, canvas, d, t_ms):
        pygame.draw.rect(canvas, INK, (0, FOOTER_Y, W, H - FOOTER_Y))
        pygame.draw.line(canvas, CYAN_LO, (0, FOOTER_Y), (W - 1, FOOTER_Y))

        # Your trainer, walking when you move.
        loc = d.get('location') or {}
        facing = loc.get('facing') if loc.get('facing') in ('up', 'down', 'left', 'right') else 'down'
        pos = (loc.get('map_id'), loc.get('x'), loc.get('z'), facing)
        if self.last_pos is not None and pos != self.last_pos:
            self.walk_until = t_ms + 700
        self.last_pos = pos
        anim = self.o.sprites.trainer(d.get('character') or 'Hilbert', facing)
        if anim:
            frame = anim.frame(t_ms) if t_ms < self.walk_until else anim.frames[0]
            canvas.blit(frame, (16 - frame.get_width() // 2, H - 2 - frame.get_height()))

        name = d.get('trainer_name') or ''
        self.font.draw(canvas, self.font.fit(name, 62), (32, FOOTER_Y + 4), WHITE, SHADOW)
        self.font.draw(canvas, self.font.fit(f"${d.get('money', 0):,}", 62), (32, FOOTER_Y + 16), GOLD, SHADOW)

        # The badges, bottoms lined up.
        earned = set(d.get('badges') or ())
        bx = 98
        for i, badge in enumerate(BADGES):
            img = self.art.small_badge(i, badge in earned)
            if img is None:
                ui.badge_pip(canvas, bx + 3, FOOTER_Y + 12, i, badge in earned)
                bx += 11
                continue
            if badge not in earned:
                img = img.copy()
                img.fill((90, 90, 100, 150), special_flags=pygame.BLEND_RGBA_MULT)
            canvas.blit(img, (bx, H - 1 - img.get_height()))
            bx += img.get_width() + 2

        dex = d.get('pokedex') or {}
        if dex.get('obtained', True):
            self.mini.draw(canvas, "CAUGHT", (W - 26, FOOTER_Y + 7), GOLD)
            self.font.draw(canvas, str(dex.get('caught', 0)), (W - 29, FOOTER_Y + 5), WHITE, SHADOW, align='right')
            self.mini.draw(canvas, "SEEN", (W - 26, FOOTER_Y + 19), GOLD)
            self.font.draw(canvas, str(dex.get('seen', 0)), (W - 29, FOOTER_Y + 17), WHITE, SHADOW, align='right')
