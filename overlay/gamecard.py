"""
gamecard.py - the overlay's view for a game DSiRPC has no parser for (every
game but Pokemon Platinum, for now). It's laid out like the party view, so
switching games keeps the same look:

    header        the game's name, and how long it's been played this session
    Now           its RetroAchievements rich presence (what you're doing in
                  the game), or why there isn't any
    Achievements  a progress bar, then the latest unlock (for a few minutes
                  after it happens) or one still to earn, a different one
                  every few seconds
    footer        a game card in the game's own colour, its game code and RA
                  game ID, and how many achievements and points you've earned

Everything comes from core/other_game.py's state. A game that gets its own
parser later (Pokemon Black and White, say) gets views of its own the way
Platinum has the party and battle views; this card stays the default for
everything else.
"""

import time

import pygame

from . import ui

W, H = 256, 192
HEADER_H = 16
FOOTER_Y = 162
NOW_RECT = (3, 18, 250, 54)
ACH_RECT = (3, 74, 250, 86)

LATEST_FOR_S = 300       # how long the latest unlock is shown instead of one to earn
NEXT_EVERY_MS = 6000     # how often the one to earn changes


def session_time(started):
    """'1:02' (hours:minutes) since `started` (a time.time())."""
    s = max(0, int(time.time() - started)) if started else 0
    return f"{s // 3600}:{s // 60 % 60:02d}"


def _sentence(text):
    text = (text or '').strip()
    return text[:1].upper() + text[1:] if text else text


class GameCard:
    def __init__(self, font, mini):
        self.font = font
        self.mini = mini

    def draw(self, canvas, d, t_ms):
        ra = d.get('ra_set')
        achs = ra.playable_achievements if ra else []
        ui.tiled_background(canvas, t_ms)
        self._header(canvas, d)
        self._now(canvas, d, ra)
        if ra:
            self._achievements(canvas, d, achs, t_ms)
        else:
            self._no_set(canvas, d)
        self._footer(canvas, d, ra, achs, t_ms)

    # -- header ----------------------------------------------------------------

    def _header(self, canvas, d):
        t = ui.THEME
        ui.bar(canvas, 0, HEADER_H)
        clock = session_time(d.get('started'))
        cw = self.font.draw(canvas, clock, (W - 5, 4), t['text_light'], t['text_light_shadow'], align='right')
        title = self.font.fit(d.get('title') or '', W - 10 - cw - 8)
        self.font.draw(canvas, title, (5, 4), t['text_light'], t['text_light_shadow'])

    # -- now -------------------------------------------------------------------

    def _now(self, canvas, d, ra):
        t = ui.THEME
        x, y, w, h = NOW_RECT
        ui.panel(canvas, NOW_RECT, fill=t['lead_fill'], lo=t['lead_lo'], border=t['lead_border'])
        ui.chip(canvas, self.mini, x + 5, y + 5, "NOW", t['lead_border'])
        text = d.get('rich_presence')
        if text:
            lines, col = self.font.wrap(text, w - 12, 3), t['text']
        elif ra:
            lines, col = ["No rich presence in this game's set."], t['text_muted']
        else:
            lines, col = ["No rich presence: that comes with", "the game's RetroAchievements set."], t['text_muted']
        ly = y + 17
        for line in lines:
            self.font.draw(canvas, line, (x + 6, ly), col, t['text_shadow'])
            ly += 12

    # -- achievements ----------------------------------------------------------

    def _achievements(self, canvas, d, achs, t_ms):
        t = ui.THEME
        x, y, w, h = ACH_RECT
        ui.panel(canvas, ACH_RECT)
        p = d.get('progress')
        total = len(achs)
        ui.trophy(canvas, x + 6, y + 5, earned=bool(p and p[0]))
        self.font.draw(canvas, "Achievements", (x + 19, y + 5), t['text'], t['text_shadow'])
        if p:
            self.font.draw(canvas, f"{p[0]}/{p[1]}", (x + w - 6, y + 5), t['text'], t['text_shadow'], align='right')
        else:
            self.font.draw(canvas, str(total), (x + w - 6, y + 5), t['text_muted'], t['text_shadow'], align='right')
        ui.meter(canvas, self.mini, x + 6, y + 18, w - 12, p[0] / max(1, p[1]) if p else 0)
        pygame.draw.line(canvas, t['panel_lo'], (x + 6, y + 29), (x + w - 7, y + 29))

        if not total:
            self.font.draw(canvas, "This set has no achievements yet.", (x + 6, y + 35), t['text_muted'], t['text_shadow'])
            return
        unlocked = d.get('unlocked') or ()
        by_id = {a['id']: a for a in achs}
        latest = None
        for aid, when in reversed(d.get('recent') or []):
            if aid in by_id and time.time() - when < LATEST_FOR_S:
                latest = by_id[aid]
                break
        locked = [a for a in achs if a['id'] not in unlocked]

        room = 3 if p else 2   # description lines (without progress, a line says why)
        if latest:
            self._entry(canvas, "LATEST", t['ach_lo'], latest, t_ms, room, sparkle=True)
        elif p and not locked:
            ui.chip(canvas, self.mini, x + 6, y + 34, "MASTERED", t['ach_lo'])
            self.font.draw(canvas, "Every achievement earned!", (x + 6, y + 46), t['text'], t['text_shadow'])
            ui.sparkle(canvas, x + w - 12, y + 40, t_ms)
            ui.sparkle(canvas, x + w - 22, y + 50, t_ms + 400)
        elif locked:
            a = locked[(t_ms // NEXT_EVERY_MS) % len(locked)]
            self._entry(canvas, "TO EARN", (104, 120, 132), a, t_ms, room)
        if not p:
            why = ("Asking RetroAchievements for your progress..." if d.get('signed_in')
                   else "Sign in with Setup.bat for your progress.")
            self.font.draw(canvas, self.font.fit(why, w - 12), (x + 6, y + h - 13), t['ach_lo'], t['text_shadow'])

    def _entry(self, canvas, label, color, a, t_ms, room, sparkle=False):
        """One achievement: a label chip, its title and points, and its
        description underneath."""
        t = ui.THEME
        x, y, w, h = ACH_RECT
        cw = ui.chip(canvas, self.mini, x + 6, y + 34, label, color)
        pts = f"{a['points']}"
        pw = self.mini.width(pts) + 5
        ui.chip(canvas, self.mini, x + w - 6 - pw, y + 34, pts, t['ach_lo'])
        title = self.font.fit(a['title'], w - 12 - cw - 4 - pw - 4)
        self.font.draw(canvas, title, (x + 6 + cw + 4, y + 33), t['text'], t['text_shadow'])
        if sparkle:
            ui.sparkle(canvas, x + w - 6 - pw - 6, y + 31, t_ms)
        lines = self.font.wrap(a.get('description') or '', w - 12, room)
        ly = y + 47
        for line in lines:
            self.font.draw(canvas, line, (x + 6, ly), t['text_muted'], t['text_shadow'])
            ly += 12

    def _no_set(self, canvas, d):
        t = ui.THEME
        x, y, w, h = ACH_RECT
        ui.panel(canvas, ACH_RECT)
        ui.trophy(canvas, x + 6, y + 5, earned=False)
        self.font.draw(canvas, "Achievements", (x + 19, y + 5), t['text'], t['text_shadow'])
        pygame.draw.line(canvas, t['panel_lo'], (x + 6, y + 18), (x + w - 7, y + 18))
        note = _sentence(d.get('ra_note')) or "No RetroAchievements set for it."
        lines = self.font.wrap(note + ('' if note.endswith(('.', '!', '?')) else '.'), w - 12, 2)
        lines += self.font.wrap("Run Setup.bat to add the game's set, and DSiRPC checks its achievements"
                                " as you play.", w - 12, 3)
        ly = y + 23
        for line in lines[:5]:
            self.font.draw(canvas, line, (x + 6, ly), t['text_muted'], t['text_shadow'])
            ly += 12

    # -- footer ----------------------------------------------------------------

    def _footer(self, canvas, d, ra, achs, t_ms):
        t = ui.THEME
        ui.bar(canvas, FOOTER_Y, H - FOOTER_Y)
        code = (d.get('game') or {}).get('code') or '????'
        ui.game_card(canvas, 14, H - 24 + ui.bob(t_ms, 1400, 1), ui.card_color(code))
        self.font.draw(canvas, code, (40, FOOTER_Y + 5), t['text_light'], t['text_light_shadow'])
        self.mini.draw(canvas, f"RA GAME {ra.id}" if ra else "NO RA SET", (40, FOOTER_Y + 19), t['hp_label'])

        p = d.get('progress')
        if not ra:
            return
        unlocked = d.get('unlocked') or ()
        earned = str(p[0]) if p else '-'
        points = str(sum(a['points'] for a in achs if a['id'] in unlocked)) if p else '-'
        self.mini.draw(canvas, "EARNED", (W - 30, FOOTER_Y + 7), t['hp_label'])
        self.font.draw(canvas, earned, (W - 34, FOOTER_Y + 5), t['text_light'], t['text_light_shadow'], align='right')
        self.mini.draw(canvas, "POINTS", (W - 30, FOOTER_Y + 19), t['hp_label'])
        self.font.draw(canvas, points, (W - 34, FOOTER_Y + 17), t['text_light'], t['text_light_shadow'], align='right')
