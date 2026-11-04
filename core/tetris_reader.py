"""
tetris_reader.py - Tetris DS (ATRE): the board, the falling piece, the
stored (held) block, the score, lines and level, read from the DSi's memory
for the overlay's Tetris view (overlay/tetris.py) and Discord.

Tetris DS has no parser of its own otherwise: it's an "other" game
(core/other_game.py) with its RetroAchievements set, and the hub adds this
reader's state to it as 'tetris' while a Standard game (Marathon, Line Clear
or VS CPU) is being played. The addresses are RetroAchievements' code notes
for the game (by Brylefi), offsets into main RAM (0x02000000):

    0x076A2C    in game: 0x02 (0x10 out of the game, 0x20 the credits)
    0x07B3B0    menu: 0x00 single player
    0x07B3B1    single player mode: 0x00 Standard
    0x07B3B2    Standard mode: 0x00 Marathon, 0x01 Line Clear, 0x02 VS CPU
    0x17DB88    the board: 10 x 20 bytes, the bottom row first, left to
                right; 0 empty, else the block's colour (PIECE_CELL)
    0x17DD1C    the falling piece (PIECES), 0x17DD1D its orientation,
                0x17DD20 its column, 0x17DD22 its row (from the bottom)
    0x17DD24    the next piece (0x17DDA9-0x17DDAD the five after it; not
                read yet)
    0x17DD2C    the stored piece, 0xFF none
    0x17DD32    state: 0x00 falling, 0x01 dropped, 0x03 lines cleared,
                0x04 hard dropped, 0x07 game over
    0x17DD34    score (32-bit), 0x17DD38 lines (32-bit), 0x17DD3C level
                (32-bit)
    0x1C4214    pieces hidden (the game is paused)

read() returns None when no Standard game is being played, else:

    {'mode': 'Marathon', 'board': [[cell, ...10], ...20] (row 0 at the
     bottom; 0 empty, else a piece's letter, 'X' for any other block),
     'piece': {'kind': 'T',
     'turn': 0-3, 'x': column, 'y': row} or None, 'hold': 'I' or None,
     'score': 1234, 'lines': 12, 'level': 2, 'state': 0, 'over': False,
     'paused': False}
"""

import struct

RAM = 0x02000000
IN_GAME = RAM + 0x076A2C
MENU = RAM + 0x07B3B0          # menu, single player mode, Standard mode
BOARD = RAM + 0x17DB88
PIECE = RAM + 0x17DD1C         # 0x24 bytes: the piece's fields to the level
HIDDEN = RAM + 0x1C4214

COLS, ROWS = 10, 20
PIECES = "ZSLJTOI"             # the falling and stored piece's numbers
PIECE_CELL = 9                 # a board cell: 9 + the piece's number
MODES = {0: "Marathon", 1: "Line Clear", 2: "VS CPU"}
LINE_CLEAR_GOAL = 25           # Line Clear: lines to clear (the set's rich presence)
GAME_OVER = 7
# How the overlay plays a line clear once it sees full rows (overlay/tetris.py's
# TetrisMotion; the demo's loop leaves it this long): the rows grey, then gone
# one at a time from the top, then the gap, before the board after it shows
CLEAR_GREY_S, CLEAR_ROW_S, CLEAR_GAP_S = 0.3, 0.1, 0.12

RANGES = [(IN_GAME, 1), (MENU, 3), (BOARD, COLS * ROWS), (PIECE, 0x24), (HIDDEN, 1)]

# Each piece's cells as it spawns, from its centre of rotation (x right, y
# up, as the board's rows count), as in the Super Rotation System; the I
# turns about the corner up and to the right of its (0, 0) cell, the O not at all.
SHAPES = {
    'T': [(-1, 0), (0, 0), (1, 0), (0, 1)],
    'S': [(-1, 0), (0, 0), (0, 1), (1, 1)],
    'Z': [(-1, 1), (0, 1), (0, 0), (1, 0)],
    'J': [(-1, 1), (-1, 0), (0, 0), (1, 0)],
    'L': [(1, 1), (-1, 0), (0, 0), (1, 0)],
    'I': [(-1, 0), (0, 0), (1, 0), (2, 0)],
    'O': [(0, 0), (1, 0), (0, 1), (1, 1)],
}


def cells(kind, turn):
    """A piece's cells (dx, dy) from its centre, turned clockwise `turn` times."""
    out = SHAPES[kind]
    for _ in range(turn % 4 if kind != 'O' else 0):
        out = [(y + 1, -x) if kind == 'I' else (y, -x) for x, y in out]
    return out


def _piece(n):
    return PIECES[n] if 0 <= n < len(PIECES) else None


def _count(raw):
    """A 32-bit counter, 0 while it's still unset (0xFFFFFFFF before the game starts)."""
    v = struct.unpack("<I", raw)[0]
    return 0 if v >= 0x80000000 else v


def parse(chunks):
    """RANGES' bytes, in order -> the state above, or None."""
    in_game, menu, board, piece, hidden = chunks
    if in_game[0] != 0x02 or menu[0] != 0 or menu[1] != 0 or menu[2] not in MODES:
        return None
    # Each cell: 0, a piece's letter, or 'X' for a block of no piece's colour
    rows = [[(_piece((c & 0x0F) - PIECE_CELL) or 'X') if c & 0x0F else 0 for c in board[r * COLS:(r + 1) * COLS]]
            for r in range(ROWS)]
    state = piece[0x16]
    kind = _piece(piece[0])
    falling = None
    if kind and state != GAME_OVER:
        falling = {'kind': kind, 'turn': piece[1] & 3, 'x': struct.unpack("<b", piece[4:5])[0],
                   'y': struct.unpack("<b", piece[6:7])[0]}
    return {
        'mode': MODES[menu[2]],
        'board': rows,
        'piece': falling,
        'hold': _piece(piece[0x10]),
        'score': _count(piece[0x18:0x1C]),
        'lines': _count(piece[0x1C:0x20]),
        'level': _count(piece[0x20:0x24]),
        'state': state,
        'over': state == GAME_OVER,
        'paused': hidden[0] != 0,
    }


def read(client, timeout=None):
    """The state now (two requests), or None outside a Standard game.
    Raises TimeoutError or RuntimeError if the DSi doesn't answer."""
    return parse(client.read_ranges(RANGES, timeout=timeout, retries=1))
