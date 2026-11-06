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
# A square course 2000 across, the finish line on the left side: its
# checkpoints' middles go round it anticlockwise from there
SQUARE = [(-1000, 0), (-1000, -1000), (0, -1000), (1000, -1000), (1000, 0), (1000, 1000), (0, 1000), (-1000, 1000)]


def checkpoints(mids=SQUARE, half=200):
    return [(x - half, z, x + half, z, i if i % 4 == 0 else -1) for i, (x, z) in enumerate(mids)]


def race_memory(racers, course=0x14, mode=0, place=None, lap=2, laps=3, finished=0, cps=None, timer_ms=83456,
                racers_at=RACERS_AT, mirror=0):
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
           (COURSE_AT + mk.CP_POINTER, struct.pack("<IH", CP_AT, len(cps)))]
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
    assert r['racers'][0]['player'] and r['racers'][0]['place'] == 6 and r['place'] is None


def test_the_players_own_place_wins():
    _, _, _, r = read_race(place=2)
    assert r['place'] == 2 and r['order'][1] == 0
    names = [r['racers'][s]['character'] for s in r['order']]
    assert names == ["Bowser", "Mario", "Yoshi", "Wario", "Peach", "Luigi", "Toad", "Donkey Kong"]
    assert [r['racers'][s]['place'] for s in r['order']] == list(range(1, 9))


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
        art, crop, k, ox, oy, finish = MAPS[course_file]
        assert os.path.exists(os.path.join("Assets", "MarioKartDS", ART.format(art))), art
        assert 9 < k < 16 and crop[2] > crop[0] and crop[3] > crop[1]


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
