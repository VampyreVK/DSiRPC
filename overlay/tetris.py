"""
tetris.py - the overlay's view for Tetris DS while a Standard game is played
(core/tetris_reader.py's state, as the game card's 'tetris'). It keeps the
game card's header and footer (overlay/gamecard.py), with in between:

    left      the stored (held) block, then the mode, score, lines and level
    middle    the board as the game has it: the blocks that have landed, and
              the falling piece
    right     achievements: progress, the latest unlock, and one still to earn

The blocks are drawn here in code, in the game's colours (RetroAchievements'
code notes: Z red, S green, L orange, J purple, T pink, O yellow, I blue).
Paused, the board is hidden, as the game hides it; after a game over it
greys out. Rows in the state's 'clearing' (only the demo's, core/demo.py)
flash white. Anywhere else in the game (its menus, the other modes) the game
card shows instead.
"""

import time

import pygame

from core.tetris_reader import SHAPES, cells

from . import ui
from .gamecard import FOOTER_Y, HEADER_H, NEW_FOR_S, NEXT_EVERY_MS, W, ago

CELL = 7                      # a board cell, in canvas pixels
COLS, ROWS = 10, 20
BOARD_X, BOARD_Y = 87, HEADER_H + 3       # the board's top left (inside its frame)
LEFT = (3, HEADER_H + 2, 81, FOOTER_Y - HEADER_H - 4)      # the hold and stats column
RIGHT_X = BOARD_X + COLS * CELL + 4
RIGHT = (RIGHT_X, HEADER_H + 2, W - 3 - RIGHT_X, FOOTER_Y - HEADER_H - 4)  # the achievements column
HOLD_H = 42

COLORS = {
    'Z': (232, 56, 56), 'S': (72, 200, 72), 'L': (240, 144, 32), 'J': (148, 80, 224),
    'T': (232, 96, 200), 'O': (240, 208, 40), 'I': (56, 136, 240), 'X': (140, 148, 156),
}
BOARD_BG, BOARD_GRID, BOARD_FRAME = (18, 22, 28), (28, 34, 42), (61, 75, 95)

_blocks = {}


def block(color, size=CELL):
    """One block, `size` pixels square: the colour with a lit top and left
    edge, a shaded bottom and right one and a glint (cached)."""
    key = (color, size)
    surf = _blocks.get(key)
    if surf is None:
        surf = pygame.Surface((size, size))
        surf.fill(color)
        hi, lo = ui.lighten(color, 70), ui.darken(color, 70)
        pygame.draw.line(surf, hi, (0, 0), (size - 1, 0))
        pygame.draw.line(surf, hi, (0, 0), (0, size - 1))
        pygame.draw.line(surf, lo, (1, size - 1), (size - 1, size - 1))
        pygame.draw.line(surf, lo, (size - 1, 1), (size - 1, size - 1))
        if size >= 5:
            surf.set_at((1, 1), (255, 255, 255))
        _blocks[key] = surf
    return surf


def _grey(color):
    v = sum(color) // 3
    return (v, v, v + 8)


class TetrisView:
    def __init__(self, font, mini, card):
        """card: the game card (overlay/gamecard.py), for the header and footer."""
        self.font = font
        self.mini = mini
        self.card = card

    def draw(self, canvas, d, t_ms):
        tet = d['tetris']
        ra = d.get('ra_set')
        achs = ra.playable_achievements if ra else []
        ui.tiled_background(canvas, t_ms)
        self.card._header(canvas, d)
        self._hold(canvas, tet)
        self._stats(canvas, tet)
        self._board(canvas, tet, t_ms)
        self._achievements(canvas, d, achs, t_ms)
        self.card._footer(canvas, d, ra, achs, t_ms)

    # -- left: the stored block and the numbers ---------------------------------

    def _hold(self, canvas, tet):
        t = ui.THEME
        x, y, w, _ = LEFT
        ui.panel(canvas, (x, y, w, HOLD_H))
        ui.chip(canvas, self.mini, x + 5, y + 5, "HOLD", (104, 120, 132))
        kind = tet.get('hold')
        if not kind:
            self.mini.draw(canvas, "EMPTY", (x + w // 2 - self.mini.width("EMPTY") // 2, y + 25), t['text_muted'])
            return
        self.piece(canvas, kind, x + w // 2, y + 26, 6, grey=tet.get('over'))

    def piece(self, canvas, kind, cx, cy, size, grey=False):
        """A piece as it spawns, centred on (cx, cy), in `size`-pixel blocks."""
        pts = cells(kind, 0)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w, h = (max(xs) - min(xs) + 1) * size, (max(ys) - min(ys) + 1) * size
        color = COLORS[kind] if not grey else _grey(COLORS[kind])
        for px, py in pts:
            canvas.blit(block(color, size), (cx - w // 2 + (px - min(xs)) * size, cy - h // 2 + (max(ys) - py) * size))

    def _stats(self, canvas, tet):
        t = ui.THEME
        x, y, w, h = LEFT
        y += HOLD_H + 2
        h -= HOLD_H + 2
        ui.panel(canvas, (x, y, w, h))
        ui.chip(canvas, self.mini, x + 5, y + 5, tet['mode'].upper(), t['lead_border'])
        lines = tet['lines']
        rows = [("SCORE", f"{tet['score']:,}"), ("LINES", str(lines)), ("LEVEL", str(tet['level']))]
        if tet['mode'] == "Line Clear":
            from core.tetris_reader import LINE_CLEAR_GOAL
            rows[1] = ("LINES LEFT", str(max(0, LINE_CLEAR_GOAL - lines)))
        ly = y + 18
        for label, value in rows:
            self.mini.draw(canvas, label, (x + 6, ly), t['ach_lo'])
            self.font.draw(canvas, self.font.fit(value, w - 12), (x + 6, ly + 8), t['text'], t['text_shadow'])
            ly += 23

    # -- middle: the board -------------------------------------------------------

    def _board(self, canvas, tet, t_ms):
        t = ui.THEME
        bw, bh = COLS * CELL, ROWS * CELL
        pygame.draw.rect(canvas, BOARD_FRAME, (BOARD_X - 2, BOARD_Y - 2, bw + 4, bh + 4))
        pygame.draw.rect(canvas, t['bar_lo'], (BOARD_X - 1, BOARD_Y - 1, bw + 2, bh + 2))
        pygame.draw.rect(canvas, BOARD_BG, (BOARD_X, BOARD_Y, bw, bh))
        for c in range(1, COLS):
            pygame.draw.line(canvas, BOARD_GRID, (BOARD_X + c * CELL, BOARD_Y), (BOARD_X + c * CELL, BOARD_Y + bh - 1))
        for r in range(1, ROWS):
            pygame.draw.line(canvas, BOARD_GRID, (BOARD_X, BOARD_Y + r * CELL), (BOARD_X + bw - 1, BOARD_Y + r * CELL))
        if tet.get('paused'):
            self._banner(canvas, "PAUSED")
            return
        over = tet.get('over')
        for r, row in enumerate(tet['board']):
            for c, kind in enumerate(row):
                if kind:
                    self._cell(canvas, c, r, COLORS.get(kind, COLORS['X']), over)
        p = tet.get('piece')
        if p and p['kind'] in SHAPES and not over:
            for dx, dy in cells(p['kind'], p['turn']):
                c, r = p['x'] + dx, p['y'] + dy
                if 0 <= c < COLS and 0 <= r < ROWS:
                    self._cell(canvas, c, r, COLORS[p['kind']], False)
        for r in tet.get('clearing') or ():   # full rows on their way out (the demo's): flashing white
            if (t_ms // 120) % 2 == 0:
                for c in range(COLS):
                    canvas.blit(block((236, 240, 248)), (BOARD_X + c * CELL, BOARD_Y + (ROWS - 1 - r) * CELL))
        if over:
            self._banner(canvas, "GAME OVER")

    def _cell(self, canvas, c, r, color, grey):
        canvas.blit(block(_grey(color) if grey else color), (BOARD_X + c * CELL, BOARD_Y + (ROWS - 1 - r) * CELL))

    def _banner(self, canvas, text):
        t = ui.THEME
        bw = COLS * CELL
        y = BOARD_Y + ROWS * CELL // 2 - 9
        pygame.draw.rect(canvas, t['bar'], (BOARD_X, y, bw, 18))
        pygame.draw.line(canvas, t['bar_hi'], (BOARD_X, y), (BOARD_X + bw - 1, y))
        pygame.draw.line(canvas, t['bar_lo'], (BOARD_X, y + 17), (BOARD_X + bw - 1, y + 17))
        self.font.draw(canvas, text, (BOARD_X + bw // 2, y + 5), t['text_light'], t['text_light_shadow'], align='center')

    # -- right: achievements -----------------------------------------------------

    def _achievements(self, canvas, d, achs, t_ms):
        t = ui.THEME
        x, y, w, h = RIGHT
        ui.panel(canvas, RIGHT)
        p = d.get('progress')
        ui.trophy(canvas, x + 5, y + 5, earned=bool(p and p[0]))
        if p:
            self.font.draw(canvas, f"{p[0]}/{p[1]}", (x + w - 5, y + 5), t['text'], t['text_shadow'], align='right')
        elif achs:
            self.font.draw(canvas, str(len(achs)), (x + w - 5, y + 5), t['text_muted'], t['text_shadow'], align='right')
        ui.meter(canvas, self.mini, x + 5, y + 18, w - 10, p[0] / max(1, p[1]) if p else 0)
        ty = y + 30
        if not achs:
            note = d.get('ra_note') or "No RetroAchievements set for it."
            for i, line in enumerate(self.font.wrap(note, w - 10, 6)):
                self.font.draw(canvas, line, (x + 5, ty + 12 * i), t['text_muted'], t['text_shadow'])
            return
        unlocked = d.get('unlocked') or ()
        by_id = {a['id']: a for a in achs}
        latest = d.get('latest') or (d['recent'][-1] if d.get('recent') else None)
        if latest and latest[0] in by_id:
            a, when = by_id[latest[0]], latest[1]
            new = when and time.time() - when < NEW_FOR_S
            ui.chip(canvas, self.mini, x + 5, ty, "NEW" if new else "LATEST", t['ach_lo'])
            if new:
                ui.sparkle(canvas, x + w - 10, ty + 4, t_ms)
            ty += 12
            for line in self.font.wrap(a['title'], w - 10, 2):
                self.font.draw(canvas, line, (x + 5, ty), t['text'], t['text_shadow'])
                ty += 12
            for line in self.font.wrap(a.get('description') or '', w - 10, 3):
                self.font.draw(canvas, line, (x + 5, ty), t['text_muted'], t['text_shadow'])
                ty += 12
            if p and when:
                self.mini.draw(canvas, ago(when).upper(), (x + 5, ty), t['ach_lo'])
            ty += 10
        else:
            for line in self.font.wrap("Nothing earned yet.", w - 10, 2):
                self.font.draw(canvas, line, (x + 5, ty), t['text_muted'], t['text_shadow'])
                ty += 12
        locked = [a for a in achs if a['id'] not in unlocked]
        bottom = y + h - 5
        if ty > bottom - 40:
            return
        pygame.draw.line(canvas, t['panel_lo'], (x + 5, ty), (x + w - 6, ty))
        ty += 4
        if not locked:
            ui.chip(canvas, self.mini, x + 5, ty, "MASTERED", t['ach_lo'])
            return
        a = locked[(t_ms // NEXT_EVERY_MS) % len(locked)]
        ui.chip(canvas, self.mini, x + 5, ty, "TO EARN", (104, 120, 132))
        ty += 12
        room = max(1, (bottom - 8 - ty) // 12)
        for line in self.font.wrap(a['title'], w - 10, min(2, room)):
            self.font.draw(canvas, line, (x + 5, ty), t['text'], t['text_shadow'])
            ty += 12
        self.mini.draw(canvas, f"{a['points']} POINTS", (x + 5, bottom - 6), t['ach_lo'])
