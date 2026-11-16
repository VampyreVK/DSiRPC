"""
activity_card.py - the overlay window's popup for what the launcher is doing
with DSiRPC (core/launcher_activity.py): syncing saves, checking its games
with RetroAchievements, getting the achievement sets ready and sending them,
or updating the console's files. It slides down from the top of whatever
view is on, over it, in the toasts' cream (an achievement's, a level up's),
under a toast while one is up:

            +------------------------------------------+
            | Syncing saves                     2 of 5 |
            | Uploading Pokemon Platinum               |
            | [=============.......................]   |
            +------------------------------------------+

The bar is the whole job's (every save of a sync, both files of an update,
by their bytes) and glides to each new count instead of jumping; without a
count it's a block going back and forth. The card:

  - only comes up once something has gone on for SHOW_AFTER seconds, so the
    quick ones don't flash it
  - says "done" (or "failed") with how it went for a few seconds once it's
    over (core/launcher_activity.py's DONE_S), then slides away; one it
    never showed isn't shown just to say it's done

Overlay.draw() draws it last, over everything (overlay/scenes.py), from the
view its `activity` callable returns each frame (app/engine.py's, None while
the tray menu's "Activity popup" is off).
"""

import math

import pygame

from core.launcher_activity import fraction
from . import ui

W, H = 256, 192          # the canvas (overlay/scenes.py's)
CARD_W, CARD_H = 192, 34
CARD_X = (W - CARD_W) // 2
TOP = 4                  # its place at the top, as the toasts'
SHOW_AFTER = 1.0         # seconds something goes on before the card comes up
SLIDE_MS = 250
GLIDE_MS = 60            # the bar closes most of the way to the real count in about this long
MOVE_MS = 80             # the same for its place, moving under a toast and back


def should_show(view, now, shown):
    """Whether the card shows this view (core/launcher_activity.py's
    current()): `shown` is the generation it last showed."""
    if not view:
        return False
    if view['finished'] is not None:
        return view['generation'] == shown      # (only to say how one it showed went)
    return view['generation'] == shown or now - view['started'] >= SHOW_AFTER


def count_text(view):
    """The count at the title's right: "2 of 5" (the items, or the count),
    "40%" (bytes), "" without one."""
    if not view or view['finished'] is not None:
        return ""
    if view.get('items') and view.get('item'):
        return f"{view['item']} of {view['items']}"
    if not view['total']:
        return ""
    if view.get('unit') == "bytes":
        return f"{int(fraction(view) * 100)}%"
    return f"{min(view['done'], view['total'])} of {view['total']}"


class ActivityCard:
    def __init__(self, font, mini):
        self.font = font
        self.mini = mini
        self.shown = 0          # the generation last shown
        self.view = None        # what's on the card (kept while it slides away)
        self.since = None       # t_ms it came up
        self.leaving = None     # t_ms it started sliding away
        self.bar = 0.0          # the bar's fill as drawn, gliding to the real one
        self.top = None         # its place as drawn, moving to `top`
        self.last = None        # t_ms of the last frame

    def draw(self, canvas, view, t_ms, now, top=TOP):
        """Draws the card for `view` (None: nothing going on), sliding in or
        out as needed. `now` is time.time(), for SHOW_AFTER; `top` is where
        it goes (under a toast that's up)."""
        dt = 0 if self.last is None else max(0, t_ms - self.last)
        self.last = t_ms
        if should_show(view, now, self.shown):
            if self.view is None or self.leaving is not None:
                self.since = t_ms               # (coming down, or back while it was sliding away)
            if self.view is None or view['generation'] != self.view['generation']:
                self.bar = 0.0                  # (a new one: the bar from empty)
            if self.view is None:
                self.top = top
            self.leaving = None
            self.shown = view['generation']
            self.view = view
        elif self.view is not None and self.leaving is None:
            self.leaving = t_ms
        if self.view is None:
            return
        if self.leaving is not None:
            out = (t_ms - self.leaving) / SLIDE_MS
            if out >= 1:
                self.view = self.since = self.leaving = self.top = None
                return
            slide = 1 - out
        else:
            slide = min(1.0, (t_ms - self.since) / SLIDE_MS)
        self.top += (top - self.top) * (1 - math.exp(-dt / MOVE_MS))
        if abs(top - self.top) < 0.5:
            self.top = top
        y = int(round(self.top)) - int((CARD_H + self.top) * (1 - ui.ease_out(max(0.0, slide))))
        self._card(canvas, self.view, CARD_X, y, t_ms, dt)

    def _card(self, canvas, v, x, y, t_ms, dt):
        t = ui.THEME
        done = v['finished'] is not None
        failed = done and not v['ok']
        ui.panel(canvas, (x, y, CARD_W, CARD_H), fill=t['lead_fill'], lo=t['lead_lo'], border=t['lead_border'])

        # What it's doing, the count at the right, and what it's on
        left, right = x + 8, x + CARD_W - 8
        count = count_text(v)
        cw = self.font.width(count) + 6 if count else 0
        title = v['title'] if not done else f"{v['title']}: {'failed' if failed else 'done'}"
        self.font.draw(canvas, self.font.fit(title, right - left - cw), (left, y + 4), t['text'], t['text_shadow'])
        if count:
            self.font.draw(canvas, count, (right, y + 4), t['text_muted'], t['text_shadow'], align='right')
        detail = v['summary'] if done else v['detail']
        if detail:
            self.font.draw(canvas, self.font.fit(detail, right - left), (left, y + 14), t['text_muted'],
                           t['text_shadow'])

        # The bar: how far the whole job is (gliding there), or a block going
        # back and forth without a count
        bx, by, bw, bh = left, y + CARD_H - 8, right - left, 3
        pygame.draw.rect(canvas, t['lead_lo'], (bx, by, bw, bh))
        fill, hi = (t['hp_red'], t['hp_red_hi']) if failed else (t['hp_green'], t['hp_green_hi']) if done \
            else (t['ach'], t['ach_hi'])
        frac = 1.0 if done and not failed else fraction(v)
        if frac is None and not failed:
            seg = max(12, bw // 5)
            span = bw - seg
            pos = (t_ms // 8) % (2 * span) if span > 0 else 0
            sx = pos if pos <= span else 2 * span - pos
            pygame.draw.rect(canvas, fill, (bx + sx, by, seg, bh))
            pygame.draw.line(canvas, hi, (bx + sx, by), (bx + sx + seg - 1, by))
            return
        if failed:
            frac = self.bar         # (stays where it got to)
        self.bar += (frac - self.bar) * (1 - math.exp(-dt / GLIDE_MS))
        if abs(frac - self.bar) < 0.002:
            self.bar = frac
        fw = int(bw * self.bar)
        if fw > 0:
            pygame.draw.rect(canvas, fill, (bx, by, fw, bh))
            pygame.draw.line(canvas, hi, (bx, by), (bx + fw - 1, by))
