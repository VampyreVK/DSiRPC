"""
gamecard.py - the overlay's view for a game DSiRPC has no parser for (every
game but Pokemon Platinum, for now). It's laid out like the party view, so
switching games keeps the same look:

    header        the game's name, and how long it's been played this session
    Now           its RetroAchievements rich presence (what you're doing in
                  the game), or why there isn't any
    Achievements  a progress bar, then side by side: the latest unlock
                  (left two thirds: "NEW" for a few minutes after it happens,
                  with how long ago) and one still to earn (right third, a
                  different one every few seconds)
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

NEW_FOR_S = 300          # how long the latest unlock is marked NEW
NEXT_EVERY_MS = 6000     # how often the one to earn changes
SPLIT_X = 164            # the divider between the latest unlock and the one to earn (from the panel's left)


def session_time(started):
    """'1:02' (hours:minutes) since `started` (a time.time())."""
    s = max(0, int(time.time() - started)) if started else 0
    return f"{s // 3600}:{s // 60 % 60:02d}"


def ago(when, now=None):
    """'just now', '5 min ago', '3 h ago', 'yesterday', 'Oct 8'."""
    now = time.time() if now is None else now
    s = max(0, int(now - when))
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    if s < 2 * 86400:
        return "yesterday"
    t = time.localtime(when)
    return f"{time.strftime('%b', t)} {t.tm_mday}"


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
        latest = d.get('latest')
        if not latest and d.get('recent'):
            latest = d['recent'][-1]
        if latest and latest[0] not in by_id:
            latest = None
        locked = [a for a in achs if a['id'] not in unlocked]

        pygame.draw.line(canvas, t['panel_lo'], (x + SPLIT_X, y + 33), (x + SPLIT_X, y + h - 5))
        self._latest(canvas, d, by_id[latest[0]] if latest else None, latest[1] if latest else 0, p, t_ms)
        if p and not locked:
            self._mastered(canvas, t_ms)
        elif locked:
            self._to_earn(canvas, locked[(t_ms // NEXT_EVERY_MS) % len(locked)])

    def _latest(self, canvas, d, a, when, p, t_ms):
        """The left two thirds: the latest unlock, or why there's none."""
        t = ui.THEME
        x, y, w, h = ACH_RECT
        lw = SPLIT_X - 10           # its width
        bottom = y + h - 13
        if not p:                   # its last line says why there's no progress
            why = "Asking RetroAchievements..." if d.get('signed_in') else "Sign in: run Setup.bat"
            self.font.draw(canvas, self.font.fit(why, lw), (x + 6, bottom), t['ach_lo'], t['text_shadow'])
        if not a:
            lines = self.font.wrap("Nothing earned yet. Your next unlock shows up here.", lw, 3)
            for i, line in enumerate(lines):
                self.font.draw(canvas, line, (x + 6, y + 35 + 12 * i), t['text_muted'], t['text_shadow'])
            return
        new = when and time.time() - when < NEW_FOR_S
        cw = ui.chip(canvas, self.mini, x + 6, y + 34, "NEW" if new else "LATEST", t['ach_lo'])
        pts = f"{a['points']}"
        pw = self.mini.width(pts) + 5
        ui.chip(canvas, self.mini, x + 6 + lw - pw, y + 34, pts, t['ach_lo'])
        title = self.font.fit(a['title'], lw - cw - 4 - pw - 4)
        self.font.draw(canvas, title, (x + 6 + cw + 4, y + 33), t['text'], t['text_shadow'])
        if new:
            ui.sparkle(canvas, x + 6 + lw - pw - 6, y + 31, t_ms)
        room = 2
        lines = self.font.wrap(a.get('description') or '', lw, room)
        for i, line in enumerate(lines):
            self.font.draw(canvas, line, (x + 6, y + 47 + 12 * i), t['text_muted'], t['text_shadow'])
        if p and when:
            self.mini.draw(canvas, f"EARNED {ago(when).upper()}", (x + 6, bottom + 3), t['ach_lo'])

    def _to_earn(self, canvas, a):
        """The right third: one still to earn (title and points; there's no
        room for its description)."""
        t = ui.THEME
        x, y, w, h = ACH_RECT
        rx, rw = x + SPLIT_X + 5, w - SPLIT_X - 11
        ui.chip(canvas, self.mini, rx, y + 34, "TO EARN", (104, 120, 132))
        lines = self.font.wrap(a['title'], rw, 2)
        for i, line in enumerate(lines):
            self.font.draw(canvas, line, (rx, y + 46 + 12 * i), t['text'], t['text_shadow'])
        self.mini.draw(canvas, f"{a['points']} POINTS", (rx, y + h - 10), t['ach_lo'])

    def _mastered(self, canvas, t_ms):
        t = ui.THEME
        x, y, w, h = ACH_RECT
        rx = x + SPLIT_X + 5
        ui.chip(canvas, self.mini, rx, y + 34, "MASTERED", t['ach_lo'])
        for i, line in enumerate(self.font.wrap("Every one earned!", w - SPLIT_X - 11, 2)):
            self.font.draw(canvas, line, (rx, y + 46 + 12 * i), t['text'], t['text_shadow'])
        ui.sparkle(canvas, x + w - 12, y + 66, t_ms)
        ui.sparkle(canvas, x + w - 24, y + 74, t_ms + 400)

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
