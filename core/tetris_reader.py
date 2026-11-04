"""
tetris_reader.py - Tetris DS (ATRE): the board, the falling piece, the
stored (held) block, the score, lines and level, read from the DSi's memory
for the overlay's Tetris view (overlay/tetris.py) and Discord.

Tetris DS has no parser of its own otherwise: it's an "other" game
(core/other_game.py) with its RetroAchievements set, and the hub adds this
reader's state to it as 'tetris' while a Standard game (Marathon, Line Clear
or VS CPU) or a Mission game (Marathon or Time Trial) is being played. The
addresses are RetroAchievements' code notes for the game (by Brylefi),
offsets into main RAM (0x02000000):

    0x076A2C    in game: 0x02 (0x10 out of the game, 0x20 the credits)
    0x07B3B0    menu: 0x00 single player
    0x07B3B1    single player mode: 0x00 Standard, 0x02 Mission
    0x07B3B2    Standard mode: 0x00 Marathon, 0x01 Line Clear, 0x02 VS CPU;
                Mission mode: 0x00 Marathon, 0x01 Time Trial
    0x07B3B4    the level picked (Mission shows it)
    0x17DB88    the board: 10 x 20 bytes, the bottom row first, left to
                right; 0 empty, 9-15 a piece's colour (PIECE_CELL), anything
                else a grey block (0x10: Mission's rising garbage)
    0x17DD1C    the falling piece (PIECES), 0x17DD1D its orientation,
                0x17DD20 its column, 0x17DD22 its row (from the bottom)
    0x17DD24    the next piece, 0x17DDA9-0x17DDAD the five after it
    0x17DD2C    the stored piece, 0xFF none
    0x17DD32    state: 0x00 falling, 0x01 dropped, 0x03 lines cleared,
                0x04 hard dropped, 0x07 game over
    0x17DD34    score (32-bit), 0x17DD38 lines (32-bit), 0x17DD3C level
                (32-bit)
    0x1C4214    pieces hidden (the game is paused)
    0x10A3D0    the options: bit 1 the ghost piece off (bit 0 hard drop off)

Mission keeps the same things elsewhere (LAYOUTS): the board at 0x1B88F8
(found on hardware: as Marathon's, just before its piece), the piece's block
at 0x1B8A88 (column +4, row +6, next +8, stored +0x10 in the notes, and the
turn +1, checked on hardware; the rest taken to be as Marathon's), the five
next pieces after the first at 0x1B8BA9 (found in a RAM dump: the six as the
game showed them at 0x1B8BA8, the only place they're in order), pieces
hidden at 0x1B3314, its state at 0x1B8B2C (as Marathon's, found on
hardware: 1 as a piece lands, 0 as the next comes in, 7 at the game over),
and the score (32-bit) at 0x1B8B34 and mission number at 0x1B8B3C. It has no
lines.

read() returns None when no Standard or Mission game is being played, else:

    {'mode': 'Marathon', 'board': [[cell, ...10], ...20] (row 0 at the
     bottom; 0 empty, else a piece's letter, 'X' for any other block),
     'piece': {'kind': 'T',
     'turn': 0-3, 'x': column, 'y': row} or None, 'hold': 'I' or None,
     'score': 1234, 'lines': 12 (None in Mission), 'level': 2, 'mission': None
     (Mission's number), 'state': 0, 'over': False,
     'paused': False, 'ghost': True (the game shows where the piece lands),
     'next': ['S', 'Z', ...] the next pieces, the soonest first (up to 6)}
"""

import struct

RAM = 0x02000000
IN_GAME = RAM + 0x076A2C
MENU = RAM + 0x07B3B0          # menu, single player mode, its mode, (unused), the level picked
OPTIONS = RAM + 0x10A3D0
GHOST_OFF = 0x02
# Where each kind of game keeps its board and pieces: the piece's block is
# 0x24 bytes (the piece's fields to the level), the queue the next pieces
# after the first (that one's in the block), 'extra' Mission's state, score and number
LAYOUTS = {
    'standard': {'board': RAM + 0x17DB88, 'piece': RAM + 0x17DD1C, 'queue': RAM + 0x17DDA9,
                 'hidden': RAM + 0x1C4214, 'extra': None},
    'mission': {'board': RAM + 0x1B88F8, 'piece': RAM + 0x1B8A88, 'queue': RAM + 0x1B8BA9,
                'hidden': RAM + 0x1B3314, 'extra': RAM + 0x1B8B2C},
}
BOARD, PIECE = LAYOUTS['standard']['board'], LAYOUTS['standard']['piece']

COLS, ROWS = 10, 20
PIECES = "ZSLJTOI"             # the falling and stored piece's numbers
PIECE_CELL = 9                 # a board cell: 9 + the piece's number
MODES = {0: "Marathon", 1: "Line Clear", 2: "VS CPU"}
MISSION_MODES = {0: "Mission", 1: "Time Trial"}
LINE_CLEAR_GOAL = 25           # Line Clear: lines to clear (the set's rich presence)
GAME_OVER = 7
# How the overlay plays a line clear once it sees full rows (overlay/tetris.py's
# TetrisMotion; the demo's loop leaves it this long): the rows grey, then gone
# one at a time from the top, then the gap, before the board after it shows
CLEAR_GREY_S, CLEAR_ROW_S, CLEAR_GAP_S = 0.3, 0.1, 0.12



def ranges(layout='standard'):
    """What read() reads for a kind of game, in parse()'s order."""
    at = LAYOUTS[layout]
    out = [(IN_GAME, 1), (MENU, 5), (at['board'], COLS * ROWS), (at['piece'], 0x24), (at['hidden'], 1),
           (OPTIONS, 1)]
    if at['queue']:
        out.append((at['queue'], 5))
    if at['extra']:
        out.append((at['extra'], 20))
    return out


RANGES = ranges()

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


def layout_of(in_game, menu):
    """The kind of game being played ('standard', 'mission') from the in-game
    and menu bytes, or None (the menus, or a mode that isn't read)."""
    if in_game[0] != 0x02 or menu[0] != 0:
        return None
    if menu[1] == 0 and menu[2] in MODES:
        return 'standard'
    if menu[1] == 2 and menu[2] in MISSION_MODES:
        return 'mission'
    return None


def _cell(c):
    """A board cell: 0, a piece's letter, or 'X' for a block of no piece's colour."""
    if not c:
        return 0
    return _piece((c & 0x0F) - PIECE_CELL) or 'X'         # (by the low four bits, as the code notes read it)


def parse(chunks, layout='standard'):
    """ranges(layout)'s bytes, in order -> the state above, or None (also
    when the game isn't that kind of game)."""
    in_game, menu, board, piece, hidden, options = chunks[:6]
    rest = list(chunks[6:])
    queue = rest.pop(0) if LAYOUTS[layout]['queue'] else b''
    if layout_of(in_game, menu) != layout:
        return None
    rows = [[_cell(c) for c in board[r * COLS:(r + 1) * COLS]] for r in range(ROWS)]
    extra = rest.pop(0) if LAYOUTS[layout]['extra'] else None
    state = extra[0] if extra else piece[0x16]
    kind = _piece(piece[0])
    falling = None
    if kind and state != GAME_OVER:
        falling = {'kind': kind, 'turn': piece[1] & 3, 'x': struct.unpack("<b", piece[4:5])[0],
                   'y': struct.unpack("<b", piece[6:7])[0]}
    out = {
        'mode': MODES.get(menu[2]),
        'board': rows,
        'piece': falling,
        'hold': _piece(piece[0x10]),
        'score': _count(piece[0x18:0x1C]),
        'lines': _count(piece[0x1C:0x20]),
        'level': _count(piece[0x20:0x24]),
        'mission': None,
        'state': state,
        'over': state == GAME_OVER,
        'paused': hidden[0] != 0,
        'ghost': not options[0] & GHOST_OFF,
        'next': [k for k in (_piece(n) for n in bytes(piece[8:9]) + bytes(queue)) if k],
    }
    if layout == 'mission':
        out.update(mode=MISSION_MODES[menu[2]], score=_count(extra[8:12]), lines=None, level=menu[4],
                   mission=extra[16])
    return out


def read(client, timeout=None, layout='standard'):
    """(the state now or None, the kind of game the console's playing or
    None), reading where `layout` keeps things (two requests). Another kind
    of game gives None: read again with that one. Raises TimeoutError or
    RuntimeError if the DSi doesn't answer."""
    chunks = client.read_ranges(ranges(layout), timeout=timeout, retries=1)
    return parse(chunks, layout), layout_of(chunks[0], chunks[1])
