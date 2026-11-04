"""
tetris.py - the overlay's view for Tetris DS while a Standard game is played
(core/tetris_reader.py's state, as the game card's 'tetris'). It keeps the
game card's header and footer (overlay/gamecard.py), with in between:

    left      the stored (held) block, then the mode, score, lines and level
    middle    the board as the game has it: the blocks that have landed, and
              the falling piece, moving the way the game does between reads
              (TetrisMotion: the piece a step at a time, line clears whole)
    right     achievements: progress, the latest unlock, and one still to earn

The blocks are drawn here in code, in the game's colours (RetroAchievements'
code notes: Z red, S green, L orange, J purple, T pink, O yellow, I blue).
Paused, the board is hidden, as the game hides it; after a game over it
greys out. Anywhere else in the game (its menus, the other modes) the game
card shows instead.
"""

import time

import pygame

from core.tetris_reader import CLEAR_GAP_S, CLEAR_GREY_S, CLEAR_ROW_S, SHAPES, cells

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


class TetrisMotion:
    """What the board shows between reads (a few a second): an animation
    buffer, so it moves the way the game does rather than in jumps.

    - The falling piece steps a row (and a column) at a time from where the
      read before had it to where the latest has it, over about the time
      between reads (so it's drawn a read behind). A new piece, or one that went up (the next one), is drawn where
      it is straight away.
    - When a read has full rows (the game marks the ones it's clearing grey),
      they play out whole however few reads catch them: grey for
      CLEAR_GREY_S, then gone one at a time from the top, then the gap for
      CLEAR_GAP_S. It's one clear for as long as reads go on having full
      rows (the game takes them away a row at a time too, so fewer each
      read): those don't start it again, and show collapsed. The next one
      starts at full rows after a read with none. The piece that filled the
      rows isn't drawn again, though reads have it falling for a while yet.
    - Reads that come in while a clear plays are kept, in order, and played
      back after it CATCH_UP times as fast as they came, so nothing the game
      did meanwhile is skipped; if that falls more than MAX_BEHIND_S behind,
      it jumps to the latest.

    take() each frame with the latest state, then frame() for what to draw:
    (board, piece); `latest` is then the state being shown (the newest, or
    one being caught up on), for the hold and the numbers."""

    CATCH_UP = 2.0
    MAX_BEHIND_S = 1.5

    def __init__(self):
        self.latest = None     # the read being shown (not always the newest: see queue)
        self.arrived = 0       # t_ms it was shown from
        self.interval = 100    # between reads, in ms (measured)
        self.clear = None      # {'board', 'rows' (from the top), 'start'} while a clear plays
        self.cleared = False   # reads still have full rows from the last clear played
        self.shown = None      # the piece as the read before had it: where it steps from
        self.queue = []        # [(state, t_ms it came in)]: reads waiting for a clear to finish
        self.taken = None      # the last state take() got
        self.replay = None     # (t_ms the last clear finished, t_ms the first waiting read came in)
        self.spent = None      # the piece that made the last clear, while reads still have it falling

    def take(self, tet, t_ms):
        if tet is self.taken:
            return
        self.taken = tet
        if self.clear or self.queue:
            self.queue.append((tet, t_ms))
        else:
            self._show(tet, t_ms)

    def _catch_up(self, t_ms):
        """Shows the waiting reads due by t_ms, played from when the clear
        ended at CATCH_UP times the pace they came in."""
        since, first = self.replay
        if (since - first) / 1000 > self.MAX_BEHIND_S:
            self.queue = self.queue[-1:]                      # too far behind: the latest only
            since, first = self.replay = (since, self.queue[0][1])
        while self.queue and not self.clear:
            tet, came = self.queue[0]
            due = since + (came - first) / self.CATCH_UP
            if due > t_ms:
                break
            self.queue.pop(0)
            self._show(tet, due)

    def _show(self, tet, t_ms):
        if self.latest is not None:
            self.interval = max(40, min(250, t_ms - self.arrived))
        # (a read behind: from where the last read had it, there by the next)
        self.shown = self.latest.get('piece') if self.latest else None
        self.latest, self.arrived = tet, t_ms
        full = [r for r, row in enumerate(tet['board']) if all(row)]
        p = tet.get('piece')
        if p and self.spent and p != self.spent:
            self.spent = None                                    # the next piece's come in
        if not full:
            self.cleared = False
        elif self.clear is None and not self.cleared:
            self.clear = {'board': [list(row) for row in tet['board']], 'rows': sorted(full, reverse=True),
                          'start': t_ms}
            self.cleared = True
            # The piece that filled the rows (a cell in them): reads go on
            # having it for a while, where it landed, and it's in the rows now
            for q in (p, self.shown):
                if q and q['kind'] in SHAPES and any(q['y'] + dy in full for _, dy in cells(q['kind'], q['turn'])):
                    self.spent = dict(q)
                    break

    def frame(self, t_ms):
        if self.clear:
            c = self.clear
            at = (t_ms - c['start']) / 1000
            length = CLEAR_GREY_S + len(c['rows']) * CLEAR_ROW_S + CLEAR_GAP_S
            if at < length:
                gone = 0 if at < CLEAR_GREY_S else min(len(c['rows']), int((at - CLEAR_GREY_S) / CLEAR_ROW_S) + 1)
                board = [list(row) for row in c['board']]
                for r in c['rows']:
                    board[r] = [0] * COLS if r in c['rows'][:gone] else ['X'] * COLS
                return board, None
            self.clear = None
            if self.queue:
                self.replay = (c['start'] + length * 1000, self.queue[0][1])
        if self.queue:
            self._catch_up(t_ms)
            if self.clear:                                    # another clear, caught up on
                return self.frame(t_ms)
        tet = self.latest
        board = tet['board']
        if self.cleared:   # the game's still clearing them: as they'll be once it's done
            board = [row for row in board if not all(row)]
            board += [[0] * COLS for _ in range(ROWS - len(board))]
        return board, self._piece(tet.get('piece'), board, t_ms)

    def _piece(self, p, board, t_ms):
        if p and self.spent and p == self.spent:
            return None                                         # gone with the rows it filled
        was = self.shown
        if not p or not was or was['kind'] != p['kind'] or p['y'] > was['y']:
            return p                                            # a new piece: no steps
        f = min(1.0, (t_ms - self.arrived) / self.interval)
        step = {'kind': p['kind'], 'turn': p['turn'],
                'x': was['x'] + int((p['x'] - was['x']) * f), 'y': was['y'] + int((p['y'] - was['y']) * f)}
        for dx, dy in cells(step['kind'], step['turn']):
            c, r = step['x'] + dx, step['y'] + dy
            if not 0 <= c < COLS or (0 <= r < ROWS and board[r][c]):
                return p                                        # (a step through the stack: straight there)
        return step


class TetrisView:
    def __init__(self, font, mini, card):
        """card: the game card (overlay/gamecard.py), for the header and footer."""
        self.font = font
        self.mini = mini
        self.card = card
        self.motion = TetrisMotion()

    def draw(self, canvas, d, t_ms):
        tet = d['tetris']
        ra = d.get('ra_set')
        achs = ra.playable_achievements if ra else []
        self.motion.take(tet, t_ms)
        board_piece = self.motion.frame(t_ms)
        tet = self.motion.latest      # (a read being caught up on: its hold and numbers too)
        ui.tiled_background(canvas, t_ms)
        self.card._header(canvas, d)
        self._hold(canvas, tet)
        self._stats(canvas, tet)
        self._board(canvas, tet, board_piece)
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

    def _board(self, canvas, tet, board_piece):
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
        board, p = board_piece
        for r, row in enumerate(board):
            for c, kind in enumerate(row):
                if kind:
                    self._cell(canvas, c, r, COLORS.get(kind, COLORS['X']), over)
        if p and p['kind'] in SHAPES and not over:
            for dx, dy in cells(p['kind'], p['turn']):
                c, r = p['x'] + dx, p['y'] + dy
                if 0 <= c < COLS and 0 <= r < ROWS:
                    self._cell(canvas, c, r, COLORS[p['kind']], False)
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
