"""Tetris DS: core/tetris_reader.py's reading of its memory (the board, the
pieces, the numbers, only in a Standard game), the overlay's Tetris view
(overlay/tetris.py: the pieces' turns, a frame drawn), Discord's text
(rpc/generic_presence.py), the toasts' events. DsiSource reading it from a fake
DSi is in test_hub.py."""

import struct
import time

import pytest

from conftest import need

from core import hub, tetris_reader as tr


def memory(mode=0, board=None, piece=4, turn=0, x=4, y=18, hold=0xFF, state=0, score=1234, lines=12, level=2,
           hidden=0, in_game=2, options=0, queue=(1, 0, 6, 2, 3, 5), single=0, picked=0, extra=None):
    """The bytes ranges() reads, as the game would have them (Mission's:
    single=2 and `extra`, its score and mission number)."""
    cells = bytearray(tr.COLS * tr.ROWS)
    for (c, r), kind in (board or {}).items():
        cells[r * tr.COLS + c] = tr.PIECE_CELL + tr.PIECES.index(kind)
    block = bytearray(0x24)
    block[0], block[1], block[4], block[6], block[0x10], block[0x16] = piece, turn, x, y, hold, state
    block[8] = queue[0]
    block[0x18:0x24] = struct.pack("<III", score, lines, level)
    out = [bytes([in_game]), bytes([0, single, mode, 0, picked]), bytes(cells), bytes(block), bytes([hidden]),
           bytes([options])]
    out.append(bytes(queue[1:]))
    if extra:
        over = extra[2] if len(extra) > 2 else 0
        out.append(bytes([over]) + bytes(7) + struct.pack("<I", extra[0]) + bytes(4) + bytes([extra[1]]) + bytes(3))
    return out


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


def test_mission():
    chunks = memory(single=2, mode=0, picked=7, extra=(4321, 12), board={(0, 0): 'T'}, lines=0xFFFFFFFF)
    assert tr.parse(chunks) is None                               # not where Standard keeps things
    t = tr.parse(chunks, 'mission')
    assert (t['mode'], t['score'], t['mission'], t['level'], t['lines']) == ("Mission", 4321, 12, 7, None)
    assert t['board'][0][0] == 'T' and t['piece']['kind'] == 'T' and t['next'] == ['S', 'Z', 'I', 'L', 'J', 'O']
    assert tr.parse(memory(single=2, mode=1, extra=(0, 1)), 'mission')['mode'] == "Time Trial"
    over = tr.parse(memory(single=2, extra=(0, 1, tr.GAME_OVER)), 'mission')
    assert over['over'] and over['piece'] is None                 # its game over, from its own state byte
    assert tr.layout_of(b"\x02", bytes([0, 2, 0, 0, 0])) == 'mission' and tr.layout_of(b"\x02", bytes(5)) == 'standard'
    assert tr.layout_of(b"\x02", bytes([0, 5, 0, 0, 0])) is None          # Push: not read


def test_garbage_rows_are_grey():
    chunks = memory()
    chunks[2] = bytes([0x10, 0] + [0x10] * 8) + chunks[2][10:]   # Mission's rising row, with its hole
    assert tr.parse(chunks)['board'][0] == ['X', 0] + ['X'] * 8


def test_states():
    t = tr.parse(memory(state=tr.GAME_OVER, hold=0xFF))
    assert t['over'] and t['piece'] is None and t['hold'] is None
    assert tr.parse(memory(hidden=1))['paused']
    assert tr.parse(memory(lines=0xFFFFFFFF))['lines'] == 0          # unset before the game starts


def test_the_next_pieces_are_read():
    assert tr.parse(memory())['next'] == ['S', 'Z', 'I', 'L', 'J', 'O']
    assert tr.parse(memory(queue=(4, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF)))['next'] == ['T']   # (not set: left out)


def test_the_ghost_piece_follows_the_games_option():
    assert tr.parse(memory())['ghost']
    assert not tr.parse(memory(options=tr.GHOST_OFF))['ghost']   # Options: Ghost Piece Off


def test_the_ghost_piece_lands_where_the_piece_would():
    pytest.importorskip("pygame")
    from overlay.tetris import landing
    board = [[0] * tr.COLS for _ in range(tr.ROWS)]
    board[0] = ['X'] * 9 + [0]                                    # a stack with a well on the right
    assert landing({'kind': 'T', 'turn': 0, 'x': 4, 'y': 18}, board) == 1
    assert landing({'kind': 'I', 'turn': 1, 'x': 8, 'y': 15}, board) == 2   # upright, down the well
    assert landing({'kind': 'O', 'turn': 0, 'x': 4, 'y': 1}, board) == 1    # already resting


def test_the_pieces_turn_as_the_game_turns_them():
    from overlay.tetris import cells
    # An upright I two rows up fills the bottom four rows of the column to
    # the right of its centre (RetroAchievements' "Tower of I Pieces")
    assert sorted(cells('I', 1)) == [(1, -2), (1, -1), (1, 0), (1, 1)]
    assert sorted(cells('T', 2)) == [(-1, 0), (0, -1), (0, 0), (1, 0)]
    assert cells('O', 3) == cells('O', 0)
    assert sorted(cells('S', 4)) == sorted(cells('S', 0))


def test_discord_shows_the_numbers():
    try:
        from rpc import generic_presence
    except ImportError as e:                                      # (pypresence not installed: fails in CI)
        need(False, f"Discord's text needs rpc/ and pypresence: {e}")
    t = tr.parse(memory(score=24680, lines=42, level=5, hold=tr.PIECES.index('Z')))
    p = generic_presence.from_state({'game': {'code': 'ATRE'}, 'title': "Tetris DS", 'tetris': t,
                                     'rich_presence': "Standard | Marathon"}, check_images=False)
    assert p['details'] == "Marathon · Level 5" and p['state'] == "Score 24,680 · 42 lines · Holding Z"
    t = tr.parse(memory(mode=1, lines=20, state=tr.GAME_OVER))
    assert generic_presence.tetris_text(t) == ("Line Clear · Level 2 · Game over", "Score 1,234 · 5 lines to go")
    p = generic_presence.from_state({'game': {'code': 'ATRE'}, 'title': "Tetris DS", 'tetris': None,
                                     'rich_presence': "Not In Any Gamemode"}, check_images=False)
    assert p['details'] == "Not In Any Gamemode"                     # anywhere else: its rich presence
    t = tr.parse(memory(single=2, extra=(900, 3), hold=tr.PIECES.index('I')), 'mission')
    assert generic_presence.tetris_text(t) == ("Mission · Level 0", "Score 900 · Mission 3 · Holding I")


def test_a_tetris_and_a_new_level_are_events():
    def state(lines, level):
        return {'kind': 'other', 'game': {'code': 'ATRE'}, 'tetris': tr.parse(memory(lines=lines, level=level))}
    assert [e['type'] for e in hub.diff_events(state(36, 4), state(40, 5))] == ['tetris', 'tetris_level']
    assert hub.diff_events(state(36, 4), state(38, 4)) == []


def test_the_demo_loop_ends_where_it_starts():
    from core import demo
    drops, flash_at, length = demo.tetris_loop()
    start, _, _, held = demo.tetris_board(0)
    t, holds = 0.0, [held]
    while t < length:                                             # a frame at a time
        board, piece, _, hold = demo.tetris_board(t)
        if piece:                                                 # inside the board's columns, never in a block
            for dx, dy in tr.cells(piece['kind'], piece['turn']):
                c, r = piece['x'] + dx, piece['y'] + dy
                assert 0 <= c < tr.COLS and (r >= tr.ROWS or not board[r][c]), (t, piece)
        if hold != holds[-1]:
            holds.append(hold)
        t += 0.02
    assert holds == ['T', 'I', 'T']                               # the I in and out of hold, for the Tetris
    full, piece, flashing, _ = demo.tetris_board(flash_at + 0.15)
    assert piece is None and len(flashing) == 4 and all(all(full[r]) for r in flashing)   # a Tetris
    assert [r for r in range(tr.ROWS) if all(full[r])] == flashing  # (the rows below have holes)
    end, _, _, hold = demo.tetris_board(length - 0.01)            # (grey to the end: the overlay plays them going)
    kept = [row for r, row in enumerate(end) if r not in flashing]
    assert kept + [[0] * tr.COLS] * 4 == start and hold == held   # and the rest dropped: the start again
    assert any(any(row) for row in start[flashing[-1] + 1:])      # with pieces above what clears
    assert sum(len(d['turns']) > 1 for d in drops) >= 3           # some turning as they fall


def test_the_demo_queue_is_what_comes_in_next():
    from core import demo
    drops, _, length = demo.tetris_loop()
    came = [d['swap'] or d['kind'] for d in drops]               # (one that goes into hold came in too)
    for i, d in enumerate(drops):
        assert demo.tetris_queue(d['start'] + 0.01) == [came[(i + 1 + k) % len(came)] for k in range(6)]
    assert demo.tetris_queue(length - 0.01) == demo.tetris_queue(0)   # round the loop: the same at both ends


def _motion():
    pytest.importorskip("pygame")
    from overlay.tetris import TetrisMotion
    return TetrisMotion()


def _state(tet_board, piece):
    return {'board': tet_board, 'piece': piece}


def test_a_clear_plays_out_whole():
    from core import demo
    motion = _motion()
    drops, flash_at, length = demo.tetris_loop()
    rows = demo.tetris_board(flash_at)[2]
    after = demo.tetris_board(0)[0]                               # the board once the game's done
    # One read catches the full rows, the next already has them gone
    motion.take(_state(*demo.tetris_board(flash_at)[:2]), 0)
    motion.take(_state(after, None), 100)
    gone, t = [], 0
    while t < 1000 * (length - flash_at) - 5:
        board, piece = motion.frame(t)
        assert piece is None
        empty = [r for r in rows if not any(board[r])]
        assert all(all(board[r]) for r in rows if r not in empty)   # the rest still there, grey
        if empty != gone:                                         # one at a time, from the top
            assert len(empty) == len(gone) + 1 and max(set(empty) - set(gone)) == max(rows) - len(gone)
            gone = empty
        t += 10
    assert gone == rows
    assert motion.frame(t + 50)[0] == after                       # then the board after it


def test_reads_during_a_clear_are_caught_up_on():
    from core import demo
    motion = _motion()
    _, flash_at, length = demo.tetris_loop()
    clearing = demo.tetris_board(flash_at)[0]
    after = [row for r, row in enumerate(clearing) if r not in range(3, 7)] + [[0] * tr.COLS] * 4
    motion.take(_state(clearing, None), 0)
    for k in range(1, 9):                                         # the game carries on: a piece falls a row a read
        motion.take(_state(after, {'kind': 'T', 'turn': 0, 'x': 4, 'y': 19 - k}), 100 * k)
        assert motion.frame(100 * k)[1] is None                   # (the clear still playing)
    ended = 1000 * (length - flash_at)
    seen = []
    for t in range(int(ended) + 10, int(ended) + 600, 10):
        board, piece = motion.frame(t)
        assert board == after
        if piece and (not seen or seen[-1] != piece['y']):
            seen.append(piece['y'])
    assert seen == list(range(18, 10, -1))                        # every read played, in order, none skipped
    assert motion.latest['piece']['y'] == 11 and not motion.queue  # and caught up within 400 ms (twice as fast)


def test_the_game_taking_the_rows_away_doesnt_start_another_clear():
    from core import demo
    motion = _motion()
    _, flash_at, length = demo.tetris_loop()
    clearing = demo.tetris_board(flash_at)[0]
    after = [row for r, row in enumerate(clearing) if r not in range(3, 7)] + [[0] * tr.COLS] * 4
    motion.take(_state(clearing, None), 0)
    for k, left in enumerate((3, 2, 1, 1, 0), 1):                 # the game's own clear: a row fewer a read
        board = [row for r, row in enumerate(clearing) if r not in range(3 + left, 7)]
        board += [[0] * tr.COLS] * (tr.ROWS - len(board))
        motion.take(_state(board, None), 300 * k)
    motion.take(_state(after, None), 1800)
    ended = 1000 * (length - flash_at)
    for t in range(int(ended) + 10, 2500, 10):
        board, _ = motion.frame(t)
        assert not any(all(row) for row in board), t              # no grey row coming back
    assert motion.frame(2500)[0] == after


def test_the_piece_that_made_the_clear_doesnt_come_back():
    from core import demo
    motion = _motion()
    _, flash_at, length = demo.tetris_loop()
    well = demo.tetris_loop()[0][-1]
    landed = {'kind': 'I', 'turn': 1, 'x': well['x'], 'y': well['land']}
    before = demo.tetris_board(flash_at - 0.05)[0]
    clearing = demo.tetris_board(flash_at)[0]
    after = [row for r, row in enumerate(clearing) if r not in range(3, 7)] + [[0] * tr.COLS] * 4
    motion.take(_state(before, dict(landed, y=landed['y'] + 1)), 0)
    motion.take(_state(clearing, dict(landed)), 100)              # the I's still the game's falling piece,
    motion.take(_state(after, dict(landed)), 400)                 # even once the rows are gone
    motion.take(_state(after, dict(landed)), 500)
    nxt = {'kind': 'T', 'turn': 0, 'x': 4, 'y': 18}
    motion.take(_state(after, nxt), 1500)                         # then the next piece
    drawn = [motion.frame(t)[1] for t in range(110, 2000, 10)]
    assert not any(p and p['kind'] == 'I' for p in drawn)         # the I never drawn again
    assert drawn[-1] == nxt                                       # (the T, caught up on)


def test_the_piece_steps_between_reads():
    motion = _motion()
    empty = [[0] * tr.COLS for _ in range(tr.ROWS)]
    motion.take(_state(empty, {'kind': 'T', 'turn': 0, 'x': 4, 'y': 18}), 0)
    assert motion.frame(0)[1]['y'] == 18
    motion.take(_state(empty, {'kind': 'T', 'turn': 0, 'x': 1, 'y': 10}), 200)   # reads 200 ms apart
    ys = [motion.frame(t)[1]['y'] for t in range(200, 420, 20)]
    xs = [motion.frame(t)[1]['x'] for t in range(200, 420, 20)]
    assert ys[0] == 18 and ys[-1] == 10 and ys == sorted(ys, reverse=True) and len(set(ys)) > 4
    assert xs[0] == 4 and xs[-1] == 1
    motion.take(_state(empty, {'kind': 'T', 'turn': 0, 'x': 4, 'y': 18}), 400)   # the next one: straight there
    assert motion.frame(400)[1]['y'] == 18


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
        well = demo.tetris_loop()[0][-1]
        scene_at = sum(d for _, d in demo.SCENES[:[s for s, _ in demo.SCENES].index('tetris')])
        source.t0 = time.time() - scene_at - well['swap_at'] - 0.2  # just after the I comes out of hold
        d = source.read()
        p = d['tetris']['piece']
        assert p['kind'] == 'I' and p['turn'] == 1                   # the I coming down the well
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 0, 16)
        x, y = BOARD_X + (p['x'] + 1) * CELL + 3, BOARD_Y + (19 - (p['y'] - 2)) * CELL + 3   # its lowest cell
        assert canvas.get_at((x, y))[:3] == COLORS['I']
        d['tetris'] = dict(d['tetris'], paused=True)
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 100, 16)
        assert canvas.get_at((x, y))[:3] != COLORS['I']              # hidden while paused
    finally:
        pygame.quit()
