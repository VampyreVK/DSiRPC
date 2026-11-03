"""Tetris DS: core/tetris_reader.py's reading of its memory (the board, the
pieces, the numbers, only in a Standard game), the overlay's Tetris view
(overlay/tetris.py: the pieces' turns, a frame drawn), Discord's text
(rpc/generic_presence.py), the toasts' events. DsiSource reading it from a fake
DSi is in test_hub.py."""

import struct
import time

import pytest

from core import hub, tetris_reader as tr


def memory(mode=0, board=None, piece=4, turn=0, x=4, y=18, hold=0xFF, state=0, score=1234, lines=12, level=2,
           hidden=0, in_game=2):
    """The bytes RANGES reads, as the game would have them."""
    cells = bytearray(tr.COLS * tr.ROWS)
    for (c, r), kind in (board or {}).items():
        cells[r * tr.COLS + c] = tr.PIECE_CELL + tr.PIECES.index(kind)
    block = bytearray(0x24)
    block[0], block[1], block[4], block[6], block[0x10], block[0x16] = piece, turn, x, y, hold, state
    block[0x18:0x24] = struct.pack("<III", score, lines, level)
    return [bytes([in_game]), bytes([0, 0, mode]), bytes(cells), bytes(block), bytes([hidden])]


def test_the_board_and_pieces_are_read():
    t = tr.parse(memory(board={(0, 0): 'I', (9, 0): 'Z', (4, 19): 'O'}, hold=tr.PIECES.index('L')))
    assert t['mode'] == "Marathon" and t['score'] == 1234 and t['lines'] == 12 and t['level'] == 2
    assert t['board'][0][0] == 'I' and t['board'][0][9] == 'Z' and t['board'][19][4] == 'O'
    assert sum(1 for row in t['board'] for c in row if c) == 3
    assert t['piece'] == {'kind': 'T', 'turn': 0, 'x': 4, 'y': 18} and t['hold'] == 'L'
    assert not t['over'] and not t['paused']


def test_only_a_standard_game():
    assert tr.parse(memory(in_game=0x10)) is None                    # out of the game
    assert tr.parse(memory(mode=3)) is None                          # How To Play
    assert tr.parse(memory(mode=1))['mode'] == "Line Clear"
    chunks = memory()
    chunks[1] = bytes([0, 2, 0])                                     # Mission mode: another layout
    assert tr.parse(chunks) is None


def test_states():
    t = tr.parse(memory(state=tr.GAME_OVER, hold=0xFF))
    assert t['over'] and t['piece'] is None and t['hold'] is None
    assert tr.parse(memory(hidden=1))['paused']
    assert tr.parse(memory(lines=0xFFFFFFFF))['lines'] == 0          # unset before the game starts


def test_the_pieces_turn_as_the_game_turns_them():
    from overlay.tetris import cells
    # An upright I two rows up fills the bottom four rows of the column to
    # the right of its centre (RetroAchievements' "Tower of I Pieces")
    assert sorted(cells('I', 1)) == [(1, -2), (1, -1), (1, 0), (1, 1)]
    assert sorted(cells('T', 2)) == [(-1, 0), (0, -1), (0, 0), (1, 0)]
    assert cells('O', 3) == cells('O', 0)
    assert sorted(cells('S', 4)) == sorted(cells('S', 0))


def test_discord_shows_the_numbers():
    # (rpc/ and pypresence aren't in the Tests workflow's checkout: skipped there)
    generic_presence = pytest.importorskip("rpc.generic_presence", exc_type=ImportError)
    t = tr.parse(memory(score=24680, lines=42, level=5, hold=tr.PIECES.index('Z')))
    p = generic_presence.from_state({'game': {'code': 'ATRE'}, 'title': "Tetris DS", 'tetris': t,
                                     'rich_presence': "Standard | Marathon"}, check_images=False)
    assert p['details'] == "Marathon · Level 5" and p['state'] == "Score 24,680 · 42 lines · Holding Z"
    t = tr.parse(memory(mode=1, lines=20, state=tr.GAME_OVER))
    assert generic_presence.tetris_text(t) == ("Line Clear · Level 2 · Game over", "Score 1,234 · 5 lines to go")
    p = generic_presence.from_state({'game': {'code': 'ATRE'}, 'title': "Tetris DS", 'tetris': None,
                                     'rich_presence': "Not In Any Gamemode"}, check_images=False)
    assert p['details'] == "Not In Any Gamemode"                     # anywhere else: its rich presence


def test_a_tetris_and_a_new_level_are_events():
    def state(lines, level):
        return {'kind': 'other', 'game': {'code': 'ATRE'}, 'tetris': tr.parse(memory(lines=lines, level=level))}
    assert [e['type'] for e in hub.diff_events(state(36, 4), state(40, 5))] == ['tetris', 'tetris_level']
    assert hub.diff_events(state(36, 4), state(38, 4)) == []


def test_the_demo_loop_ends_where_it_starts():
    from core import demo
    steps, flash_at, length = demo.tetris_loop()
    start = demo.tetris_board(0)[0]
    t = 0.0
    while t < length:                                             # a frame at a time
        board, piece, _ = demo.tetris_board(t)
        if piece:                                                 # inside the board's columns, never in a block
            for dx, dy in tr.cells(piece['kind'], piece['turn']):
                c, r = piece['x'] + dx, piece['y'] + dy
                assert 0 <= c < tr.COLS and (r >= tr.ROWS or not board[r][c]), (t, piece)
        t += 0.04
    end, piece, flashing = demo.tetris_board(length - 0.01)
    assert piece is None and flashing == [0, 1, 2, 3]
    assert all(all(end[r]) for r in range(4))                    # four full rows: a Tetris
    assert end[4:8] == start[:4] and not any(any(row) for row in end[8:])   # then the start again
    assert all(not row[9] for row in start) and sorted(k for k, _, _ in demo.TETRIS_PIECES) == sorted("LTZSOTZJI")


def test_the_view_draws():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.scenes import Overlay
    from overlay.sprites import SpriteBank
    from overlay.tetris import BOARD_X, BOARD_Y, CELL, COLORS
    pygame.init()
    try:
        canvas = pygame.Surface((256, 192), 0, 32)
        overlay = Overlay(SpriteBank("Assets"))
        source = demo.DemoSource()
        steps = demo.tetris_loop()[0]
        scene_at = sum(d for _, d in demo.SCENES[:[s for s, _ in demo.SCENES].index('tetris')])
        source.t0 = time.time() - scene_at - steps[-1][0] - 0.2      # just after the last piece, the I, comes in
        d = source.read()
        p = d['tetris']['piece']
        assert p['kind'] == 'I' and p['turn'] == 1                   # the I coming down the well
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 0, 16)
        x, y = BOARD_X + 9 * CELL + 3, BOARD_Y + (19 - p['y']) * CELL + 3
        assert canvas.get_at((x, y))[:3] == COLORS['I']
        d['tetris'] = dict(d['tetris'], paused=True)
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 100, 16)
        assert canvas.get_at((x, y))[:3] != COLORS['I']              # hidden while paused
    finally:
        pygame.quit()
