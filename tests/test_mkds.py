"""Mario Kart DS: core/mkds_reader.py's reading of a race (the pointers, the
racers, the places worked out from how far round they are, only in a race),
the overlay's race view (overlay/mkds.py: rows sliding to their places, dots
gliding between reads, a frame drawn), the course maps' table
(core/mkds_maps.py), the toasts' events. DsiSource reading it from a fake
DSi is in test_hub.py."""

import struct
import time

import pytest

from core import hub, mkds_reader as mk

MAIN = mk.MAIN_US
RACERS_AT, STATUS_AT, COURSE_AT, CP_AT = 0x0217D000, 0x02175700, 0x02180000, 0x02181000
ITEMS_AT, STANDINGS_AT = 0x02182000, 0x02183000
# A square course 2000 across, the finish line on the left side: its
# checkpoints' middles go round it anticlockwise from there
SQUARE = [(-1000, 0), (-1000, -1000), (0, -1000), (1000, -1000), (1000, 0), (1000, 1000), (0, 1000), (-1000, 1000)]


def checkpoints(mids=SQUARE, half=200):
    return [(x - half, z, x + half, z, i if i % 4 == 0 else -1) for i, (x, z) in enumerate(mids)]


def race_memory(racers, course=0x14, mode=0, place=None, lap=2, laps=3, finished=0, cps=None, timer_ms=83456,
                racers_at=RACERS_AT, mirror=0, item=(0x0B, 3), points=18):
    """[(address, bytes)] for a race as the game has it. racers: [(character
    number, x, z, lap, last checkpoint), ...] in slot order, the player first."""
    cps = checkpoints() if cps is None else cps
    fx = lambda v: struct.pack("<i", int(v * 4096))   # noqa: E731
    out = [(mk.MAIN_PTR, struct.pack("<I", MAIN)),
           (MAIN + mk.STATUS_AT, struct.pack("<II", STATUS_AT, COURSE_AT)),
           (MAIN + mk.RACERS_AT, struct.pack("<I", racers_at)),
           (mk.SETUP, bytes([course, 0, 0, 0, 1, 0, 0, 0, mode, 0, 0, 0, 0, 0, 0, 0, 2])),
           (mk.PLAYER, bytes([mirror])),
           (mk.PLACE, bytes([place or 0])),
           (MAIN + mk.PLAYER_LAP_AT, bytes([lap, 0, 0, 0, 0, 0, 0, 0, laps])),
           (MAIN + mk.FINISHED_AT, bytes([finished])),
           (COURSE_AT + mk.CP_POINTER, struct.pack("<IH", CP_AT, len(cps))),
           (MAIN + mk.ITEMS_AT, struct.pack("<I", ITEMS_AT)),
           (ITEMS_AT + 0x4C, bytes([item[0]]) + bytes(7) + bytes([item[1]])),
           (ITEMS_AT + 0x210 + 0x4C, bytes([mk.NO_ITEM])),                     # (racer 1's: not read)
           (mk.STANDINGS_PTR, struct.pack("<I", STANDINGS_AT)),
           (STANDINGS_AT + mk.CUP_POINTS, bytes([points]))]
    ms, s = timer_ms % 1000, timer_ms // 1000
    out.append((STATUS_AT + mk.STATUS_TIMER, struct.pack("<HBB", ms, s // 60, s % 60)))
    for i, (char, x, z, rlap, cp) in enumerate(racers):
        out.append((mk.DRIVERS + i * mk.DRIVER_SIZE, bytes([char])))
        out.append((racers_at + i * mk.RACER_SIZE + mk.RACER_POS, fx(x) + fx(5) + fx(z)))
        status = STATUS_AT + i * mk.STATUS_SIZE
        out.append((status + mk.STATUS_LAP, bytes([rlap & 0xFF])))
        out.append((status + 0x46, bytes([cp & 0xFF])))
    for i, (x1, z1, x2, z2, key) in enumerate(cps):
        out.append((CP_AT + i * mk.CP_SIZE, fx(x1) + fx(z1) + fx(x2) + fx(z2) + bytes(16) + struct.pack("<h", key)))
    return out


class FakeClient:
    """read_ranges() from 4 MB of made-up main RAM."""

    def __init__(self, pokes=()):
        self.ram = bytearray(0x400000)
        self.requests = 0
        self.poke_all(pokes)

    def poke_all(self, pokes):
        for addr, data in pokes:
            self.ram[addr - mk.RAM:addr - mk.RAM + len(data)] = data

    def read_ranges(self, ranges, timeout=None, retries=3):
        self.requests += 1
        return [bytes(self.ram[a - mk.RAM:a - mk.RAM + n]) for a, n in ranges]


# Mario in slot 0 on the left side, then seven others round the course
FIELD = [(0, -1000, -500, 2, 1), (7, 0, -1000, 2, 2), (4, 1000, -500, 2, 3), (6, 500, 1000, 2, 5),
         (3, -1000, 500, 2, 7), (2, -1000, -200, 2, 0), (1, -1000, 700, 1, 7), (5, 1000, 400, 2, 4)]


def read_race(**kw):
    client = FakeClient(race_memory(kw.pop('racers', FIELD), **kw))
    reader = mk.MkdsReader()
    first = reader.read(client)
    return reader, client, first, reader.read(client)


def test_a_race_is_read():
    _, _, first, r = read_race()
    assert first is None                         # (the first read learns the pointers)
    assert r['course_name'] == "Figure-8 Circuit" and r['mode'] == "Grand Prix" and r['cup'] == "Flower"
    assert r['cc'] == "150cc" and (r['lap'], r['laps']) == (2, 3) and r['time_ms'] == 83456
    assert len(r['checkpoints']) == 8 and r['checkpoints'][0][:2] == (-1200.0, 0.0)
    names = [r['racers'][s]['character'] for s in r['order']]
    # by how far round: Bowser (cp 7) is last of those on lap 2, DK's still on lap 1
    assert names == ["Bowser", "Yoshi", "Wario", "Peach", "Luigi", "Mario", "Toad", "Donkey Kong"]
    assert r['racers'][0]['player'] and r['racers'][0]['place'] == 6
    assert r['place'] == 6


def test_the_place_shown_is_the_players_place_in_the_ranking_whatever_the_games_byte_reads():
    for byte in (0, 1, 3, 8, 9, 0x7C, 0xFF):    # (the console's reads 08 or junk whatever the place)
        _, _, _, r = read_race(place=byte)
        mine = r['racers'][0]['place']
        assert r['place'] == mine == r['order'].index(0) + 1 == 6
        assert sorted(x['place'] for x in r['racers']) == list(range(1, len(r['racers']) + 1))


def test_the_item_held_and_the_cup_points():
    reader, client, _, r = read_race()
    assert r['item'] is None and r['cup_points'] is None          # (their pointers: from this read on)
    r = reader.read(client)
    assert r['item'] == {'id': 0x0B, 'name': "Triple Red Shells", 'count': 3} and r['cup_points'] == 18
    client.poke_all(race_memory(FIELD, item=(mk.NO_ITEM, 0)))
    assert reader.read(client)['item'] is None                    # nothing held
    client.poke_all(race_memory(FIELD, item=(0x0C, 1), mode=3))
    r = reader.read(client)
    assert r['item']['name'] == "Star" and r['cup_points'] is None   # VS: no cup
    assert mk.item_of(bytes([0x12, 0, 0, 0, 0, 0, 0, 0, 1])) is None  # (not an item we know: nothing shown)


def test_the_player_in_first_has_the_others_from_2nd_on_whatever_the_games_byte_reads():
    ahead = [(0, -1000, 0, 3, 1)] + FIELD[1:]                     # (the player a lap ahead of everyone)
    for byte in (0, 1, 8):                                        # (08: what the console's read all race)
        _, _, _, r = read_race(racers=ahead, place=byte)
        assert r['place'] == 1 and r['order'][0] == 0
        assert [r['racers'][s]['place'] for s in r['order']] == list(range(1, 9))


def test_the_numbers_on_the_map_match_the_ranking_with_the_player_first():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from core.mkds_reader import rank
    from overlay.font import PixelFont
    from overlay.gamecard import GameCard
    from overlay.mkds import MkdsView
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        race = demo.mkds_race(3.0)
        race['racers'][0]['progress'] += 100                      # (the player well ahead)
        race['order'] = rank(race['racers'])
        assert race['racers'][0]['place'] == 1
        places = {str(r['place']) for r in race['racers'] if not r['player']}
        assert places == {str(n) for n in range(2, len(race['racers']) + 1)}
        for flat, voxel in ((False, True), (False, False), (True, False)):   # voxel, tilted, flat
            font, mini = PixelFont(), PixelFont(mini=True)
            view = MkdsView(font, mini, GameCard(font, mini))
            view.voxel_sync = True
            if not voxel:
                view._voxel_view = lambda *a: False
            if flat:
                view._tilted = lambda *a: False
            drawn = []
            draw = mini.draw
            mini.draw = lambda surf, text, *a, **kw: (drawn.append(text), draw(surf, text, *a, **kw))[1]
            view.motion.take(race, 0)
            view._map(canvas, race, 0)
            numbers = {t for t in drawn if t.isdigit()}
            assert numbers and numbers <= places                  # (never a 1 by someone else's dot)
    finally:
        pygame.quit()


def test_a_probe_looks_for_where_the_game_keeps_the_places(caplog):
    import logging
    reader, client, _, r = read_race(timer_ms=5000)
    for slot in r['order']:                                       # a ranking at +0x5C, as the game might keep it
        client.ram[STATUS_AT + slot * mk.STATUS_SIZE + 0x5C - mk.RAM] = r['racers'][slot]['place']
    client.poke_all([(STATUS_AT + mk.STATUS_TIMER, struct.pack("<HBB", 0, 0, 25))])   # 25 s in
    with caplog.at_level(logging.INFO):
        reader.read(client)
        reader.read(client)                                       # (once: not again until PROBE_AT_MS's next)
    probes = [m for m in caplog.messages if "place probe" in m]
    assert len(probes) == 1 and "+0x5C (1-based, 8 of 8 agree)" in probes[0]
    assert "0x02368754 reads 00" in probes[0]


def test_why_theres_no_race_is_logged_when_it_changes(caplog):
    import logging
    reader, client, _, _ = read_race()
    client.poke_all([(MAIN + mk.RACERS_AT, bytes(4))])
    with caplog.at_level(logging.INFO):
        assert reader.read(client) is None and reader.read(client) is None
    assert [m for m in caplog.messages if "no race" in m] == ["Mario Kart DS: no race in this read (no racers)"]


def test_progress_goes_round_the_course():
    mids = [((x1 + x2) / 2, (z1 + z2) / 2) for x1, z1, x2, z2, _ in checkpoints()]
    p = lambda lap, cp, x, z: mk.progress(lap, cp, x, z, mids)   # noqa: E731
    assert p(1, 0, -1000, -100) < p(1, 0, -1000, -600) < p(1, 1, -900, -1000)
    assert p(1, 7, -1000, 900) < p(2, 0, -1000, -10)              # over the line: the next lap
    assert p(0, -1, -1000, 100) < p(1, 0, -1000, -10)             # before the first line at the start
    assert mk.progress(3, 5, 0, 0, []) == 3.0                     # no checkpoints yet: by lap


def test_only_in_a_race():
    _, _, _, r = read_race(racers_at=0)
    assert r is None                                              # no racers: the menus
    _, _, _, r = read_race(mode=2)
    assert r is None                                              # Battle
    _, _, _, r = read_race(course=0x2B)
    assert r is None                                              # a battle course
    _, _, _, r = read_race(mode=1)
    assert [x['slot'] for x in r['racers']] == [0] and r['order'] == [0] and r['mode'] == "Time Trial"


def test_an_empty_slot_is_left_out():
    field = FIELD[:5] + [(2, 0, 0, 0, 0)] + FIELD[6:]
    _, _, _, r = read_race(racers=field)
    assert 5 not in [x['slot'] for x in r['racers']] and len(r['order']) == 7


def requests_for(ranges):
    """How many requests core/dsirpc_client.py's read_ranges() makes of `ranges`."""
    from core.dsirpc_client import MAX_DATA, MAX_RANGES
    n, count, size = 1, 0, 0
    for _, length in ranges:
        assert length <= MAX_DATA
        if count == MAX_RANGES or size + length > MAX_DATA:
            n, count, size = n + 1, 0, 0
        count, size = count + 1, size + length
    return n


def test_reads_stay_light():
    reader, client, _, _ = read_race()
    assert requests_for(reader.ranges()) == 2                    # the positions in one, the laps in the other
    calls = []
    real = client.read_ranges
    client.read_ranges = lambda ranges, **kw: calls.append(ranges) or real(ranges, **kw)
    assert reader.read(client) and len(calls) == 1               # (the checkpoints aren't read again)


def test_a_moved_pointer_costs_one_read():
    reader, client, _, r = read_race()
    client.poke_all(race_memory(FIELD, racers_at=RACERS_AT + 0x100))   # a new race, its racers elsewhere
    assert reader.read(client) is None
    again = reader.read(client)
    assert again and [x['character'] for x in again['racers']][:2] == ["Mario", "Luigi"]


def test_the_checkpoints_are_read_again_for_a_new_course():
    reader, client, _, r = read_race()
    client.poke_all(race_memory(FIELD, course=0x19, cps=checkpoints([(x * 2, z * 2) for x, z in SQUARE])))
    r = reader.read(client)
    assert r['course_name'] == "Mario Circuit" and r['checkpoints'][0][:2] == (-2200.0, 0.0)


def test_a_final_lap_and_the_finish_are_events():
    def state(lap, finished=False, place=3):
        race = {'course': 0x14, 'lap': lap, 'laps': 3, 'finished': finished, 'place': place}
        return {'kind': 'other', 'game': {'code': 'AMCE'}, 'mkds': race}
    assert [e['type'] for e in hub.diff_events(state(2), state(3))] == ['mkds_final_lap']
    assert hub.diff_events(state(1), state(2)) == []
    assert hub.diff_events(state(3), state(4, True, 1)) == [{'type': 'mkds_finish', 'place': 1}]
    assert hub.diff_events(state(3), {'kind': 'other', 'game': {'code': 'AMCE'}, 'mkds': None}) == []


def test_every_race_course_has_a_map():
    import os
    from core.mkds_maps import ART, MAPS
    for course, (name, course_file) in mk.COURSES.items():
        assert course_file in MAPS, name
        art, k, ox, oy, finish = MAPS[course_file]
        assert os.path.exists(os.path.join("Assets", "MarioKartDS", ART.format(art))), art
        assert 9 < k < 16


def test_the_map_is_only_used_for_the_course_it_was_placed_by():
    from core import demo
    from overlay.mkds import MkdsView
    race = demo.mkds_race(0)
    assert MkdsView._mirror(race) is False                    # the demo's finish line is the course file's
    flipped = [(-x2, z1, -x1, z2, k) for x1, z1, x2, z2, k in race['checkpoints']]
    assert MkdsView._mirror(dict(race, checkpoints=flipped)) is True
    moved = [(x1 + 500, z1, x2 + 500, z2, k) for x1, z1, x2, z2, k in race['checkpoints']]
    assert MkdsView._mirror(dict(race, checkpoints=moved)) is None


def test_rows_slide_to_their_new_places():
    from overlay.mkds import ROW_H, SLIDE_MS, RankMotion
    m = RankMotion()
    m.take([0, 1, 2], 0)
    assert m.y(1, 0) == ROW_H
    m.take([1, 0, 2], 1000)                                   # 1 passes 0
    ys = [m.y(1, t) for t in range(1000, 1000 + SLIDE_MS + 50, 25)]
    assert ys[0] == ROW_H and ys[-1] == 0 and ys == sorted(ys, reverse=True) and len(set(ys)) > 5
    assert m.moving(1, 1100) and not m.moving(1, 1000 + SLIDE_MS) and not m.moving(2, 1100)


def test_dots_glide_between_reads():
    from overlay.mkds import MapMotion
    m = MapMotion()
    m.take({'racers': [{'slot': 0, 'x': 0.0, 'z': 0.0}]}, 0)
    assert m.at(0, 0) == (0.0, 0.0)
    m.take({'racers': [{'slot': 0, 'x': 100.0, 'z': -50.0}]}, 200)       # reads 200 ms apart
    xs = [m.at(0, t)[0] for t in range(200, 420, 20)]
    assert xs[0] == 0 and xs[-1] == 100 and xs == sorted(xs) and len(set(xs)) > 5
    assert m.at(0, 300) == (50.0, -25.0)


def test_names_and_numbers():
    from overlay.mkds import name_of, ordinal, race_time
    assert [ordinal(n) for n in (1, 2, 3, 4, 8, 11, 12, 21)] == ["1st", "2nd", "3rd", "4th", "8th", "11th", "12th", "21st"]
    assert race_time(83456) == "1:23.45" and race_time(5) == "0:00.00"
    assert name_of({'slot': 0, 'character': "Donkey Kong"}) == "DK"
    assert name_of({'slot': 3, 'character': None}) == "CPU 3"
    assert mk.character_name(0x0B) == "R.O.B." and mk.character_name(0x40) is None


def test_the_view_draws():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.mkds import MAP, RANK, ROW_H
    from overlay.scenes import Overlay
    from overlay.sprites import SpriteBank
    from overlay import ui
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        overlay = Overlay(SpriteBank("Assets"))
        source = demo.DemoSource()
        scene_at = sum(d for _, d in demo.SCENES[:[s for s, _ in demo.SCENES].index('mkds')])
        source.t0 = time.time() - scene_at - 5.0
        d = source.read()
        race = d['mkds']
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 0, 16)
        x, y, w, _ = RANK
        row = y + 3 + (race['place'] - 1) * ROW_H
        assert canvas.get_at((x + w - 6, row + 2))[:3] == ui.THEME['lead_fill']     # the player's row
        mx, my, mw, mh = MAP
        colours = {canvas.get_at((px, py))[:3] for px in range(mx + 4, mx + mw - 4, 3)
                   for py in range(my + 14, my + mh - 14, 3)}
        assert len(colours) > 20                                   # the course's map, not a bare panel
        overlay.mkds.art = None                                    # no art: dots and the line
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 50, 16)
        d['mkds'] = dict(race, checkpoints=())                     # before the checkpoints are read
        overlay.draw(canvas, hub.Snapshot(d, True, time.time()), 100, 16)
    finally:
        pygame.quit()


# -- the map table's decks and heights (tools/mkds_maps.py) ------------------------

def _tool():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import mkds_maps
    return mkds_maps


def test_a_crossing_at_two_heights_is_a_deck(monkeypatch):
    tool = _tool()
    # A figure of eight: up one diagonal (900 where they cross), back along the other (750 there)
    pts = [(-1000, 700, -1000), (1000, 1100, 1000), (1000, 800, -1000), (-1000, 700, 1000)]
    links = [(0, 1), (1, 2), (2, 3), (3, 0)]
    monkeypatch.setattr(tool, "cpu_path", lambda nkm: (pts, links))
    cps = [(x - 300, z, x + 300, z) for x, _, z in pts]
    (x, z, reach, low, high, upper), = tool.decks(b"", cps)
    assert (x, z) == (0, 0) and (low, high) == (750, 900) and reach == 360
    assert all(abs(px - pz) <= 1 for px, pz in upper) and len(upper) > 2   # (along the upper diagonal)
    assert tool.heights(b"", cps) == (700, 1100, 800, 700)
    pts[1] = (1000, 800, 1000)                                       # level where they cross: no deck
    assert tool.decks(b"", cps) == []


def test_the_table_has_decks_and_heights_for_its_courses():
    from core.mkds_maps import DECKS, HEIGHTS, MAPS
    files = {f for _, f in mk.COURSES.values()}
    assert set(DECKS) <= files and set(HEIGHTS) == files
    assert 'cross_course' in DECKS and 'old_baby_gc' not in DECKS   # Figure-8's bridge; Baby Park's flat
    for name, found in DECKS.items():
        for x, z, reach, low, high, upper in found:
            assert high - low >= 80 and reach > 0 and len(upper) >= 2
    assert all(len(h) >= 8 for h in HEIGHTS.values())


def test_past_a_maps_edge_its_edge_colour_carries_on():
    pygame = pytest.importorskip("pygame")
    from core.mkds_maps import MAPS
    from overlay.mkds_art import MkdsArt
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        art = MkdsArt("Assets")
        _, k, ox, oy, _ = MAPS['cross_course']
        right = (1024 - ox) * k                                       # the world x at the map's right edge
        piece = art.course_map('cross_course', (right - 500, -500, right + 500, 500), (100, 100))
        edge = piece.get_at((99, 50))[:3]
        assert all(piece.get_at((x, 50))[:3] == edge for x in range(55, 100))   # the map's edge colour carries on
    finally:
        pygame.quit()


def test_racers_on_the_bridge_are_drawn_over_it_and_those_below_under_it(monkeypatch):
    """The flat view (no heights for the course): the upper road, see-through,
    over the racers below. (Tilted, the bridge is raised on the screen, so a
    racer under it shows below it.)"""
    pygame = pytest.importorskip("pygame")
    monkeypatch.setattr("overlay.mkds.HEIGHTS", {})
    from core import demo
    from overlay.gamecard import GameCard
    from overlay.font import PixelFont
    from overlay.mkds import CHARACTER_COLORS, MkdsView
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        font, mini = PixelFont(), PixelFont(mini=True)
        race = demo.mkds_race(0)
        decks = MkdsView.decks(race, False)
        (x, z, reach, low, high, _), = decks
        me = dict(race['racers'][3], x=x, z=z)                        # Yoshi, at the crossing

        assert MkdsView.upper(dict(me, y=high - 20), decks) and not MkdsView.upper(dict(me, y=low + 20), decks)
        assert not MkdsView.upper(dict(me, x=x + 3 * reach, y=high), decks)   # (away from the crossing)
        found = {}
        for y in (low, high):
            view = MkdsView(font, mini, GameCard(font, mini))
            r = dict(race, racers=[dict(me, y=y)], order=[me['slot']])
            view.motion.take(r, 0)
            canvas.fill((0, 0, 0))
            view._map(canvas, r, 0)
            yoshi = CHARACTER_COLORS["Yoshi"]                   # (Yoshi's dot, in its own colour where nothing's over it)
            found[y] = sum(1 for px in range(256) for py in range(192) if canvas.get_at((px, py))[:3] == yoshi)
        assert found[high] > 0 and found[low] == 0                    # below: under the bridge's see-through road
    finally:
        pygame.quit()


# -- the course in 2.5D (overlay/mkds_tilt.py) --------------------------------------

def test_the_lap_goes_from_the_finish_line_round_by_distance():
    from overlay.mkds_tilt import lap_fraction, lap_lengths
    mids = [(0, 0), (100, 0), (100, 100), (0, 100)]               # a square, 400 round
    at, total = lap_lengths(mids)
    assert at == [0, 100, 200, 300] and total == 400
    assert lap_fraction(50, 0, 0, mids, at, total) == 0.125
    assert lap_fraction(100, 50, 1, mids, at, total) == 0.375
    assert lap_fraction(0, 50, 3, mids, at, total) == 0.875
    assert lap_fraction(0, 50, -1, mids, at, total) == 0.875     # (-1: the last checkpoint, before the line)


def test_heights_raise_points_but_a_flat_course_stays_flat():
    pytest.importorskip("pygame")
    from overlay.mkds_tilt import RISE_PX, TiltedCourse, usable
    cps = checkpoints()
    hilly = TiltedCourse(cps, (0, 100, 200, 300, 400, 300, 200, 100), (100, 92))
    (x, z) = SQUARE[4]
    low, high = hilly.point(x, z, 0), hilly.point(x, z, 400)
    assert low[0] == high[0] and 0 < low[1] - high[1] <= RISE_PX + 0.01    # (up, by at most RISE_PX)
    flat = TiltedCourse(cps, (500, 501, 502, 500, 501, 502, 500, 501), (100, 92))
    assert flat.point(x, z, 502)[1] - flat.point(x, z, 500)[1] > -1     # (2 units: next to nothing)
    assert usable(cps, (0,) * 8) and not usable(cps, (0,) * 7) and not usable((), (0,) * 8)


def test_the_demo_race_is_drawn_tilted_with_its_bridge():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.font import PixelFont
    from overlay.gamecard import GameCard
    from overlay.mkds import MkdsView
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        font, mini = PixelFont(), PixelFont(mini=True)
        view = MkdsView(font, mini, GameCard(font, mini))
        view.voxel = False                                            # (the 2.5D view, not the voxel one)
        race = demo.mkds_race(3.0)
        view.motion.take(race, 0)
        view._map(canvas, race, 0)
        _, course, strip = view._tilt
        assert course.upper_segments and strip is not None            # Figure-8's bridge; its heights get a strip
        assert all(course._segment_up(i) for i in course.upper_segments)
        flat = dict(race, course=0x09, checkpoints=race['checkpoints'])   # (Baby Park's file: not these checkpoints)
        view._map(canvas, flat, 0)
        assert view._tilt[0][0] == 0x14                               # (so the flat view: nothing tilted for it)
    finally:
        pygame.quit()


# -- the course as voxel terrain (overlay/mkds_voxel.py) ------------------------------

def _voxel(threaded=False):
    from core import demo
    from core.mkds_maps import DECKS, HEIGHTS
    from overlay.mkds_voxel import VoxelCourse
    race = demo.mkds_race(3.0)
    return race, VoxelCourse(race['checkpoints'], HEIGHTS['cross_course'], (100, 120), DECKS['cross_course'],
                             None, threaded=threaded)


def test_the_voxel_course_keeps_the_whole_course_in_view_all_the_way_round():
    pygame = pytest.importorskip("pygame")
    from overlay.mkds_voxel import ORBIT_MS, SCALE
    pygame.init()
    try:
        race, course = _voxel()
        assert course.ready and course.upper                      # (Figure-8's bridge: an upper deck)
        for t in range(0, ORBIT_MS, ORBIT_MS // 8):
            frame, view = course.frame(t)
            assert frame.get_size() == (100 * SCALE, 120 * SCALE)
            for i, (x, z) in enumerate(course.mids):
                sx, sy, _ = course.place(x, z, course.heights[i], view)
                assert 0 <= sx < frame.get_width() and 0 <= sy < frame.get_height()
        assert len(course.frames) <= 8                            # (only the frames around the one showing kept)
        assert any(course.tunnel)                                 # (Figure-8's overpass: a tunnel under it)
    finally:
        pygame.quit()


def test_racers_stand_on_the_voxel_ground_and_hills_hide_them():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    try:
        race, course = _voxel()
        frame, view = course.frame(0)
        me = race['racers'][0]
        sx, sy, d = course.place(me['x'], me['z'], me['y'], view)
        gx, gy, gd = course.place(me['x'], me['z'], None, view)
        assert abs(sx - gx) < 1 and abs(sy - gy) < 12             # (on the road: about where its ground is)
        assert not course.hidden(me['x'], me['z'], me['y'], view)
        cx, cz = course.centre                                    # a racer in the middle of the course...
        for i in range(len(course.hm)):                           # ... with hills all round it
            if not course.near[i]:
                course.hm[i] = 5000.0
        k = int((cz - course.z0) / course.cell) * course.gw + int((cx - course.x0) / course.cell)
        course.near[k] = True
        assert 0 <= course.place(cx, cz, course.base, view)[0] < course.w
        assert course.hidden(cx, cz, course.base, view)
    finally:
        pygame.quit()


def test_the_voxel_course_is_made_on_a_thread():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    try:
        race, course = _voxel(threaded=True)
        end = time.time() + 10
        while time.time() < end and course.frame(0) is None:
            time.sleep(0.05)
        assert course.frame(0) is not None and not course.failed
        course.close()
    finally:
        pygame.quit()


def test_the_race_view_draws_the_voxel_course_in_the_canvass_own_pixels():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.font import PixelFont
    from overlay.gamecard import GameCard
    from overlay.mkds import MkdsView
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        font, mini = PixelFont(), PixelFont(mini=True)
        view = MkdsView(font, mini, GameCard(font, mini))
        view.voxel_sync = True
        race = demo.mkds_race(3.0)
        view.motion.take(race, 0)
        view._map(canvas, race, 0)
        assert view._vox_frame.get_size() == (100, 120) and view._tilt is None
        assert canvas.get_at((124, 89)) == view._vox_frame.get_at((50, 60))     # (on the canvas, 1:1)
    finally:
        pygame.quit()


def test_a_live_hires_surface_is_scaled_afresh_each_frame():
    pygame = pytest.importorskip("pygame")
    from overlay.scenes import Overlay
    from overlay.sprites import SpriteBank
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        overlay = Overlay(SpriteBank("Assets"))
        surf = pygame.Surface((4, 4))
        surf.fill((255, 0, 0))
        assert overlay._sharp_scale(surf, (8, 8), cache=False).get_at((3, 3))[:3] == (255, 0, 0)
        surf.fill((0, 0, 255))                                    # (drawn again: the new one, not the last)
        assert overlay._sharp_scale(surf, (8, 8), cache=False).get_at((3, 3))[:3] == (0, 0, 255)
    finally:
        pygame.quit()
# -- which camera: the orbit, or following the player (overlay/mkds.py's CameraDirector) --

def _duel(gap, time_ms=60000, finished=False, me_place=4):
    """A race with the player and a rival a place ahead, `gap` checkpoints apart."""
    racers = [{'slot': 0, 'player': True, 'place': me_place, 'progress': 50.0},
              {'slot': 1, 'player': False, 'place': me_place - 1, 'progress': 50.0 + gap},
              {'slot': 2, 'player': False, 'place': me_place + 1, 'progress': 40.0}]
    return {'racers': racers, 'lap': 2, 'laps': 3, 'time_ms': time_ms, 'finished': finished}


def test_the_orbit_before_the_start_and_after_the_finish_following_between():
    from overlay.mkds import CUT_FADE_MS, CameraDirector
    d = CameraDirector()
    assert d.update(_duel(5.0, time_ms=0), 0) == 'orbit' and d.wipe(0) is None   # the countdown: timer at 0
    assert d.update(_duel(5.0, time_ms=16), 100) == 'follow'                      # GO
    assert d.wipe(100 + CUT_FADE_MS // 2) == (0.5, 'orbit')                       # (wiping from the orbit)
    assert d.wipe(100 + CUT_FADE_MS) is None
    assert d.update(_duel(5.0, finished=True), 5000) == 'orbit'                   # over the line
    assert d.wipe(5000) == (0.0, 'follow')


def test_a_battle_is_held_before_it_starts_and_before_it_ends():
    from overlay.mkds import CameraDirector as C
    d = C()
    d.update(_duel(0.4), 0)
    assert d.battle is None                                       # close, but not for long enough yet
    d.update(_duel(0.4), C.BATTLE_HOLD_MS - 1)
    assert d.battle is None
    d.update(_duel(0.4), C.BATTLE_HOLD_MS)
    assert d.battle == {'rival': 1, 'for': 3}
    d.update(_duel(1.0), 2000)                                    # (between GAP and END: still on)
    d.update(_duel(3.0), 3000)
    assert d.battle                                               # apart, but not for long enough yet
    d.update(_duel(3.0), 3000 + C.BATTLE_HOLD_MS)
    assert d.battle is None


def test_a_pass_thats_over_at_once_isnt_a_battle():
    from overlay.mkds import CameraDirector
    d = CameraDirector()
    for t in range(0, 3000, 200):                                 # close only every other read
        d.update(_duel(0.4 if t % 400 == 0 else 2.0), t)
        assert d.battle is None


def test_no_battle_in_the_orbit():
    from overlay.mkds import CameraDirector as C
    d = C()
    for t in (0, C.BATTLE_HOLD_MS, 2 * C.BATTLE_HOLD_MS):
        d.update(_duel(0.2, time_ms=0), t)
    assert d.battle is None


def test_the_chase_camera_keeps_the_rival_in_frame():
    pygame = pytest.importorskip("pygame")
    import math
    pygame.init()
    try:
        race, course = _voxel()
        me, rival = race['racers'][0], race['racers'][5]          # (Toad: well ahead)
        view = course.chase_view(me['x'], me['z'], me['y'], math.atan2(rival['z'] - me['z'], rival['x'] - me['x']),
                                 (rival['x'], rival['z'], rival['y']))
        for r in (me, rival):
            sx, sy, d = course.place(r['x'], r['z'], r['y'], view)
            assert d > 1 and 0 <= sx < course.w and 0 <= sy < course.h
        frame, drawn_in = course.chase_frame(view, 0)
        assert drawn_in == view and course.chase_frame(view, 10)[0] is frame   # (15 a second: the same one)
    finally:
        pygame.quit()


def test_the_overpass_is_ground_at_the_upper_roads_height_with_a_tunnel_under_it():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    try:
        race, course = _voxel()
        (x, z, reach, low, high, _), = course.decks
        k = int((z - course.z0) / course.cell) * course.gw + int((x - course.x0) / course.cell)
        assert abs(course.hm[k] - course.raised(high)) < course.raised(high) - course.raised(low) / 4
        floor, off = course.tunnel[k]                             # the lower road carries on under it
        assert abs(floor - course.raised(low)) < 20 and 0 <= off <= 1
        frame, view = course.frame(0)
        assert course.hidden(x, z, low, view)                     # a racer in the tunnel: hidden
        assert not course.hidden(x, z, high, view)                # one on top: not
    finally:
        pygame.quit()


def test_around_a_tunnel_mouth_the_road_stays_at_its_own_height_and_the_wall_is_wall():
    pygame = pytest.importorskip("pygame")
    from overlay.mkds_voxel import DECK_THICK, ROAD_EDGE, ROAD_FILL, SIDE
    pygame.init()
    try:
        race, course = _voxel()
        gw, gh = course.gw, course.gh
        mouth = [k for k, t in enumerate(course.tunnel) if t]
        assert mouth
        for k in mouth:                                           # (a real tunnel, not where a ramp meets the road)
            assert course.road[k] - course.tunnel[k][0] > DECK_THICK * course.exaggerate
        road_sides = {tuple(int(v * SIDE) for v in c) for c in (ROAD_FILL, ROAD_EDGE)}
        around = {(k // gw + dz) * gw + k % gw + dx for k in mouth for dx in range(-4, 5) for dz in range(-4, 5)
                  if 0 <= k % gw + dx < gw and 0 <= k // gw + dz < gh}
        for k in around:
            if course.cols[k] in (ROAD_FILL, ROAD_EDGE):          # road's colours: only on the road, at its height
                assert course.road[k] is not None and course.hm[k] == course.road[k]
            assert course.sides[k] not in road_sides              # the faces: wall, never road up a wall
    finally:
        pygame.quit()


def test_the_players_head_is_half_size_at_the_windows_resolution():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.font import PixelFont
    from overlay.gamecard import GameCard
    from overlay.mkds import HEAD_SMALL, MkdsView
    from overlay.mkds_art import MkdsArt
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        font, mini = PixelFont(), PixelFont(mini=True)
        queued, lifted = [], []
        view = MkdsView(font, mini, GameCard(font, mini), MkdsArt("Assets"),
                        hires=lambda c, surf, rect, clip=None, **kw: queued.append((surf.get_size(), tuple(rect)[2:])),
                        lift=lifted.append, hires_ok=lambda: True)
        view.voxel_sync = True
        race = demo.mkds_race(3.0)
        view.motion.take(race, 0)
        for _ in range(100):                                      # (the head's sheet loads on its own thread)
            queued.clear()
            view._map(canvas, race, 0)
            if queued:
                break
            time.sleep(0.02)
        assert queued == [((16, 14), HEAD_SMALL)] and lifted == [canvas]   # the 16x14 sprite, into 8x7
    finally:
        pygame.quit()


def test_the_players_head_still_draws_without_the_hires_path():
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.font import PixelFont
    from overlay.gamecard import GameCard
    from overlay.mkds import MkdsView
    from overlay.mkds_art import MkdsArt
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        font, mini = PixelFont(), PixelFont(mini=True)
        art = MkdsArt("Assets")
        view = MkdsView(font, mini, GameCard(font, mini), art)
        view.voxel_sync = True
        race = demo.mkds_race(3.0)
        view.motion.take(race, 0)
        for _ in range(100):
            view._map(canvas, race, 0)
            if not art.pending() and art.head("Mario"):
                break
            time.sleep(0.02)
        view._map(canvas, race, 0)
        assert ('small', 'Mario') in view._vox_sprites and view._head_at is None   # (drawn on the frame itself)
        assert view._vox_sprites[('small', 'Mario')].get_size() == (8, 7)
    finally:
        pygame.quit()


def test_items_come_from_the_games_textures_where_it_has_them():
    pygame = pytest.importorskip("pygame")
    from overlay.mkds_art import MkdsArt
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        art = MkdsArt("Assets")
        for _ in range(100):                                      # (the sheets load on their own thread)
            art.item("Banana"), art.item("Mushroom")
            if not art.pending():
                break
            time.sleep(0.02)
        icon, counted, half = art.item("Banana")
        assert half and not counted and max(icon.get_size()) <= 32       # Items.gif's, at twice the canvas's pixels
        assert icon.get_at((0, 0)).a == 0                                # (its background see-through)
        fake, _, half = art.item("Fake Item Box")
        assert half and fake.get_size()[0] > 20                          # the game's own, not a drawn one
        icon, counted, half = art.item("Triple Red Shells", 2)
        assert half and counted                                          # with the bottom screen's x2 badge on it
        icon, counted, half = art.item("Mushroom")
        assert not half and icon.get_size() == (12, 12)                  # (only half of one in Items.gif)
        icon, counted, half = art.item("Triple Mushrooms", 3)
        assert counted and not half                                      # the bottom screen's own x3
    finally:
        pygame.quit()


def test_the_start_line_is_a_checker_on_the_road_at_checkpoint_0():
    pygame = pytest.importorskip("pygame")
    import math
    from overlay.mkds_voxel import FINISH, ROAD_FILL
    pygame.init()
    try:
        race, course = _voxel()
        mx, mz = course.mids[0]
        cells = [k for k, c in enumerate(course.cols) if c in FINISH]
        assert {course.cols[k] for k in cells} == set(FINISH)         # both colours...
        for k in cells:                                               # ... only on the road, at checkpoint 0
            x, z = course.x0 + (k % course.gw + 0.5) * course.cell, course.z0 + (k // course.gw + 0.5) * course.cell
            assert course.road[k] is not None and math.hypot(x - mx, z - mz) < 2 * course.half_road
        assert ROAD_FILL in course.cols                               # (the rest of the road as it was)
    finally:
        pygame.quit()


def test_the_flat_map_draws_the_start_line(monkeypatch):
    pygame = pytest.importorskip("pygame")
    from core import demo
    from overlay.font import PixelFont
    from overlay.gamecard import GameCard
    from overlay.mkds import MkdsView
    from overlay.mkds_art import MkdsArt
    from overlay.mkds_tilt import FINISH
    monkeypatch.setattr("overlay.mkds.HEIGHTS", {})                   # (no heights: the flat map)
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        canvas = pygame.Surface((256, 192), 0, 32)
        font, mini = PixelFont(), PixelFont(mini=True)
        art = MkdsArt("Assets")
        view = MkdsView(font, mini, GameCard(font, mini), art)
        race = demo.mkds_race(3.0)
        view.motion.take(race, 0)
        for _ in range(100):
            view._map(canvas, race, 0)
            if not art.pending():
                break
            time.sleep(0.02)
        view._map(canvas, race, 0)
        seen = {tuple(canvas.get_at((x, y)))[:3] for x in range(74, 174) for y in range(29, 149)}
        assert set(FINISH) <= seen
    finally:
        pygame.quit()
