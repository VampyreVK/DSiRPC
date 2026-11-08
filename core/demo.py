"""
demo.py - DemoSource: a made-up game state that plays through a loop of
scenes, so the overlay can be styled without the DSi or a save file:
Pokemon Black (its own main view, with an achievement unlocking, a battle
in the rain in Pinwheel Forest ending in a catch, Burgh at the Castelia
Gym, and the Battle Subway, Battle Institute and an Elite Four room, each
in another season), another game (the game card every game without its own
parser gets, with an achievement unlocking), Tetris DS (its board: nine
pieces and a Tetris, looping), Mario Kart DS (eight racers lapping Figure-8
Circuit, passing each other), Pokemon Platinum (overworld, a
wild battle by day, a shiny in the evening rain, the rival at night (who
switches Pokemon), a snowy route, a legendary in a cave, a level up), and
the DSi going offline.

All of the data here is invented (but the shape of Figure-8 Circuit, from
the course's own checkpoints). It follows the same dict layout as
core/parser.py (and core/bw_parser.py for Black), so anything that works
with the demo works with the real game.
"""

import copy
import time

from . import bw_data
from . import platinum_data as pdata
from . import ra_set

WILD_MUSIC, TRAINER_MUSIC, RIVAL_MUSIC = 0x45C, 0x45F, 0x464


def _mon(species_id, level, hp, max_hp, gender, nickname=None, shiny=False, status=None, moves=(), speed=30):
    species = bw_data.SPECIES[species_id]  # Platinum's names, and Black and White's after them
    return {
        'species_id': species_id, 'species': species,
        'nickname': nickname or species.upper(), 'level': level,
        'curr_hp': hp, 'max_hp': max_hp, 'status': status, 'item': 'None',
        'moves': list(moves), 'nature': 'Hardy', 'gender': gender,
        'shiny': shiny, 'egg': False, 'checksum_ok': True, 'speed': speed,
    }


def _battle_mon(mon, side, hp=None, uses=(), last_move=None, worn=(0, 0, 0, 0)):
    """uses: the moves used so far this battle (each spends 1 PP).
    worn: PP already spent per move before the battle."""
    base = [bw_data.MOVE_INFO.get(m, (None, None, 20))[2] for m in mon['moves']]
    return {
        'species_id': mon['species_id'], 'species': mon['species'],
        'nickname': mon['nickname'], 'level': mon['level'],
        'curr_hp': mon['curr_hp'] if hp is None else hp, 'max_hp': mon['max_hp'],
        'status': mon['status'], 'moves': mon['moves'], 'shiny': mon['shiny'],
        'gender': mon['gender'], 'side': side,
        'pp': [max(0, b - worn[i] - list(uses).count(m)) for i, (m, b) in enumerate(zip(mon['moves'], base))],
        'pp_ups': [0] * len(base), 'last_move': last_move,
        'speed': mon.get('speed', 30), 'speed_stage': 6, 'ot_id': 0,
        'types': DEMO_TYPES.get(mon['species_id'], []), 'stages': {}, 'conditions': [],
    }


# Types of the demo's battlers (the real ones come from the BattleMon).
DEMO_TYPES = {393: ['Water'], 396: ['Normal', 'Flying'], 77: ['Fire'], 387: ['Grass'],
              459: ['Grass', 'Ice'], 487: ['Ghost', 'Dragon'], 502: ['Water'], 540: ['Bug', 'Grass'],
              544: ['Bug', 'Poison']}

PARTY = [
    _mon(393, 18, 44, 52, 'M', moves=('Bubble', 'Peck', 'Growl', 'Bide')),
    _mon(396, 12, 30, 33, 'F', moves=('Tackle', 'Quick Attack')),
    _mon(403, 11, 21, 34, 'M', status='Paralyzed', moves=('Tackle', 'Leer', 'Spark')),
    _mon(406, 9, 26, 26, 'F', moves=('Absorb', 'Growth')),
    _mon(77, 15, 40, 41, 'F', shiny=True, moves=('Ember', 'Tackle')),
    _mon(399, 7, 0, 25, 'M', moves=('Tackle',)),
]

# Battles: where and when they happen, the foe(s) in order (seconds into the
# scene they appear), the moves used as (second, 'you' or 'foe', move,
# damage to the other side), in turns with a pause between them (when the
# move panel shows), and other changes as (second, 'you' or 'foe', stat
# stages to add / a status / conditions to add). Like the game, a move
# spends its PP first, the HP (and the other changes) come HIT_DELAY later
# (after the animation), and the battler's "last move used" updates
# LAST_DELAY after that.
HIT_DELAY, LAST_DELAY = 0.8, 0.2
LEAD_WORN = (3, 6, 0, 1)   # PP your lead had already spent, so the panel shows a mix

BATTLES = {
    'wild': dict(place='Route 203', clock='14:03', weather=0, music=WILD_MUSIC, trainer=None,
                 foes=[(0, _mon(396, 10, 29, 29, 'M', moves=('Tackle', 'Growl', 'Quick Attack')))],
                 moves=[(2, 'you', 'Bubble', 9), (3.5, 'foe', 'Tackle', 5),
                        (9, 'you', 'Peck', 10), (10.5, 'foe', 'Growl', 0),
                        (13, 'you', 'Bubble', 12)],
                 effects=[(10.5, 'you', dict(stages={'ATK': -1}))]),
    'shiny': dict(place='Route 212', clock='18:40', weather=2, music=WILD_MUSIC, trainer=None,
                  foes=[(0, _mon(77, 14, 38, 38, 'F', shiny=True, moves=('Ember', 'Tackle')))],
                  moves=[(4.5, 'you', 'Growl', 0), (6, 'foe', 'Ember', 6)],
                  effects=[(4.5, 'foe', dict(stages={'ATK': -1})), (6, 'you', dict(status='Burned'))]),
    'rival': dict(place='Route 205', clock='21:15', weather=0, music=RIVAL_MUSIC, trainer='rival',
                  foes=[(0, _mon(387, 17, 51, 51, 'M', moves=('Razor Leaf', 'Bite', 'Withdraw'))),
                        (15.5, _mon(396, 16, 44, 44, 'M', moves=('Wing Attack', 'Quick Attack')))],
                  moves=[(2.5, 'you', 'Bubble', 18), (4, 'foe', 'Razor Leaf', 8),
                         (8.5, 'you', 'Peck', 20), (10, 'foe', 'Withdraw', 0),
                         (12.5, 'you', 'Bubble', 13),
                         (18, 'foe', 'Wing Attack', 6), (19.5, 'you', 'Peck', 15)],
                  effects=[(10, 'foe', dict(stages={'DEF': 1})), (0, 'you', dict(conditions=['Leech Seed']))]),
    'snow': dict(place='Route 216', clock='11:20', weather=6, music=WILD_MUSIC, trainer=None,
                 foes=[(0, _mon(459, 32, 88, 88, 'F', moves=('Ice Shard', 'Razor Leaf')))],
                 moves=[(3, 'you', 'Peck', 20), (4.5, 'foe', 'Ice Shard', 9)],
                 effects=[(4.5, 'you', dict(status='Frozen'))]),
    'unova_battle': dict(place='Pinwheel Forest', clock='17:30', weather=2, weather_kind='rain', music=0x400, trainer=None,
                         owned=True, caught_at=11.0,
                         foes=[(0, _mon(540, 19, 47, 47, 'F', moves=('Bug Bite', 'String Shot', 'Razor Leaf')))],
                         moves=[(2.5, 'you', 'Razor Shell', 16), (4, 'foe', 'Razor Leaf', 9),
                                (8.5, 'you', 'Water Gun', 7), (10, 'foe', 'String Shot', 0)],
                         effects=[(10, 'you', dict(stages={'SPE': -1}))]),
    'unova_gym': dict(place='Castelia Gym', clock='12:10', weather=0, music=0x46C, trainer='Burgh', kind='gym',
                      foes=[(0, _mon(544, 21, 54, 54, 'M', moves=('Poison Tail', 'Screech', 'Pursuit')))],
                      moves=[(4.5, 'you', 'Razor Shell', 14), (6, 'foe', 'Poison Tail', 8), (8.5, 'foe', 'Poison Tail', 42)],
                      effects=[]),
    'legend': dict(place='Turnback Cave', clock='16:00', weather=0, music=0x0, trainer=None,
                   foes=[(0, _mon(487, 47, 190, 190, 'genderless', moves=('Shadow Force', 'Dragon Claw')))],
                   moves=[(4, 'you', 'Bubble', 30), (5.5, 'foe', 'Shadow Force', 12)],
                   effects=[(0, 'foe', dict(conditions=['Confused'], stages={'SPA': 2, 'SPE': -1})),
                            (5.5, 'you', dict(status='Paralyzed'))]),
}

# Another game, made up too (code DEMO): what any game without its own
# parser looks like (core/other_game.py's state), with a RetroAchievements set.
OTHER_SET = ra_set.RaSet({"ID": 1, "Title": "Demo Racer DS", "Achievements": [
    {"ID": i, "Title": title, "Description": desc, "Points": pts, "Flags": 3}
    for i, (title, desc, pts) in enumerate([
        ("Green Light", "Finish your first race", 1),
        ("Podium Finish", "Finish a race in the top three", 5),
        ("Drift King", "Hold one drift for five seconds", 10),
        ("Clean Lap", "Finish a lap without touching a wall", 5),
        ("Cup Winner", "Win any cup in the easy class", 10),
        ("Comeback", "Win a race after being in last place on the final lap", 25),
        ("Time Trial Ace", "Beat the staff ghost on any track in Time Trial", 25),
        ("Full Throttle", "Win every cup in the hard class", 50),
    ], 1)]})
OTHER_UNLOCK_AT = 6.0   # seconds into the scene that "Clean Lap" unlocks

# Tetris DS (its board as core/tetris_reader.py reads it), with a set of its
# own (made up as well; "Four at Once" unlocks with the Tetris).
TETRIS_SET = ra_set.RaSet({"ID": 2, "Title": "Tetris DS", "Achievements": [
    {"ID": i, "Title": title, "Description": desc, "Points": pts, "Flags": 3}
    for i, (title, desc, pts) in enumerate([
        ("First Lines", "Clear a line in Marathon", 1),
        ("Two by Two", "Clear two lines at once in Marathon", 2),
        ("Four at Once", "Clear four lines at once in Marathon", 5),
        ("Spin Doctor", "Clear a line with a T-Spin in Marathon", 10),
        ("Level Ten", "Reach level 10 in Marathon", 10),
        ("Marathon Runner", "Clear 200 lines in Marathon", 25),
    ], 1)]})
# A loop that ends where it starts. The stack: three rows left from before
# (a hole each, so they never clear), then four rows full but for the well in
# the last column, and on top the first two pieces of a copy of those four.
# The other seven pieces finish the copy, two more start the next one, then
# an I down the well fills the four rows (a Tetris: the board marks them
# grey, and the overlay plays them going, overlay/tetris.py) and everything
# above drops into their place: the stack as it started. Each piece of the four rows as (kind, turns, its cells: column,
# row from the bottom of the four), in the order they come down; each lands
# with nothing empty under it.
TETRIS_LEFT = ["IIIIZZ.JLL", ".SSOOZTJJL", "SS.OOTTTJL"]      # the bottom rows, from the bottom
TETRIS_PIECES = [
    ('L', 0, [(0, 0), (1, 0), (2, 0), (2, 1)]), ('T', 0, [(3, 0), (4, 0), (4, 1), (5, 0)]),
    ('Z', 0, [(5, 1), (6, 0), (6, 1), (7, 0)]), ('S', 1, [(7, 1), (7, 2), (8, 0), (8, 1)]),
    ('O', 0, [(0, 1), (0, 2), (1, 1), (1, 2)]), ('T', 2, [(2, 2), (3, 1), (3, 2), (4, 2)]),
    ('Z', 0, [(4, 3), (5, 2), (5, 3), (6, 2)]), ('J', 2, [(6, 3), (7, 3), (8, 2), (8, 3)]),
    ('I', 0, [(0, 3), (1, 3), (2, 3), (3, 3)]),
]
TETRIS_CARRIED = 2       # the copy's first two pieces are on top at the start
TETRIS_WELL = ('I', 1, [(9, 0), (9, 1), (9, 2), (9, 3)])
# What comes down, in order: a piece of the copy (its index; 9 + i for the
# next copy's) or 'well', the turns it goes through on the way down (ending
# as it lands), and the piece that came in and went into hold for it (the
# held one coming out instead). The I held early is the one for the Tetris.
TETRIS_DROPS = [
    (2, [0], None), (3, [0, 1], None), (4, [0], None), (5, [0, 1, 2], 'I'), (6, [0], None),
    (7, [0, 3, 2], None), (8, [1, 0], None), (9, [0, 1, 2, 3, 0], None), (10, [0], None),
    ('well', [1], 'T'),
]
TETRIS_HOLD = 'T'        # held at the start (and the end)
TETRIS_ROW_S = 0.055     # a piece falls a row in this long
TETRIS_LOCK_S = 0.24     # and rests this long before the next one comes
TETRIS_SWAP_S = 0.4      # one that goes into hold shows this long first
TETRIS_REST_S = 1.0      # the stack waits this long after the Tetris
TETRIS_SPAWN = 21        # pieces come in with their lowest cell on this row,
TETRIS_SPAWN_X = 4       # their centre in this column (the middle, as in the game),
TETRIS_SHIFT_ROWS = 1    # and move a column over every this many rows on the way down


def tetris_loop():
    """The loop's drops: [{'start', 'kind', 'x' (its centre's column where
    it lands; it comes in at TETRIS_SPAWN_X), 'spawn' and 'land' (its
    centre's row), 'turns', 'swap': the piece that went into hold first,
    'swap_at': when the held one came out}], when the flash starts and the
    loop's length in seconds."""
    from .tetris_reader import CLEAR_GAP_S, CLEAR_GREY_S, CLEAR_ROW_S, cells
    left = len(TETRIS_LEFT)
    drops, t = [], TETRIS_REST_S
    for which, turns, swap in TETRIS_DROPS:
        if which == 'well':
            (kind, turn, where), lift = TETRIS_WELL, left
        else:   # the copy, or the next one above it
            (kind, turn, where), lift = TETRIS_PIECES[which % 9], left + 4 * (1 + which // 9)
        offs, first = cells(kind, turn), cells(kind, turns[0])
        ox, oy = min(offs, key=lambda c: (c[1], c[0]))
        cx, cy = min(where, key=lambda c: (c[1], c[0]))
        drop = {'kind': kind, 'x': cx - ox, 'land': cy - oy + lift, 'turns': turns, 'swap': swap,
                'spawn': TETRIS_SPAWN - min(dy for _, dy in first), 'start': t, 'swap_at': t}
        if swap:
            drop['swap_at'] = t = t + TETRIS_SWAP_S
        drops.append(drop)
        t += (drop['spawn'] - drop['land']) * TETRIS_ROW_S + TETRIS_LOCK_S
    flash_at = t - TETRIS_LOCK_S     # (the overlay's clear of the four rows takes the rest)
    return drops, flash_at, flash_at + CLEAR_GREY_S + 4 * CLEAR_ROW_S + CLEAR_GAP_S


def tetris_queue(into):
    """The next six pieces `into` seconds in (of one loop): what comes in
    after the one that came in last (a piece that goes into hold counts, the
    held one that comes out doesn't), round the loop."""
    drops = tetris_loop()[0]
    came = [d['swap'] or d['kind'] for d in drops]
    now = sum(1 for d in drops if d['start'] <= into)
    return [came[(now + i) % len(came)] for i in range(6)]


def tetris_board(into):
    """The loop's board, falling piece, the Tetris's rows (or []) and held
    piece, `into` seconds in (of one loop). From the Tetris to the end of
    the loop the four rows are full and grey, as the game's board has them
    while it clears them (tetris_reader's 'X'): the overlay plays them
    going (overlay/tetris.py's TetrisMotion) in that time."""
    from .tetris_reader import cells
    drops, flash_at, _ = tetris_loop()
    left = len(TETRIS_LEFT)
    board = [[c if c != '.' else 0 for c in row] for row in TETRIS_LEFT] + [[0] * 10 for _ in range(20 - left)]
    for i, (kind, _, where) in enumerate(TETRIS_PIECES):
        for c, r in where:
            board[r + left][c] = kind
            if i < TETRIS_CARRIED:
                board[r + left + 4][c] = kind
    piece, hold = None, TETRIS_HOLD
    for d in drops:
        if into < d['start']:
            break
        if d['swap']:
            if into < d['swap_at']:                        # the one going into hold, coming in
                k = d['swap']
                piece = {'kind': k, 'turn': 0, 'x': 4,
                         'y': TETRIS_SPAWN - min(dy for _, dy in cells(k, 0)) - int((into - d['start']) / TETRIS_ROW_S)}
                break
            hold = d['swap']
        fell = int((into - d['swap_at']) / TETRIS_ROW_S)
        rows = d['spawn'] - d['land']
        # its turns, spread over the first two thirds of the way down
        n = len(d['turns'])
        turn = d['turns'][min(n - 1, fell * 3 * (n - 1) // max(1, 2 * rows))]
        # and over from the middle to its column, a column a row
        shift = d['x'] - TETRIS_SPAWN_X
        x = TETRIS_SPAWN_X + (1 if shift > 0 else -1) * min(abs(shift), fell // TETRIS_SHIFT_ROWS)
        if into - d['swap_at'] < rows * TETRIS_ROW_S + TETRIS_LOCK_S / 2:
            piece = {'kind': d['kind'], 'turn': turn, 'x': x, 'y': max(d['land'], d['spawn'] - fell)}
        else:                                                  # landed: part of the board now
            for dx, dy in cells(d['kind'], d['turns'][-1]):
                board[d['land'] + dy][d['x'] + dx] = d['kind']
            piece = None
    flashing = []
    if into >= flash_at:
        piece = None                                           # (the I's landed: it's in the grey rows)
        flashing = list(range(left, left + 4))
        for r in flashing:
            board[r] = ['X'] * 10
    return board, piece, flashing, hold

# Mario Kart DS (its race as core/mkds_reader.py reads it), with a set of
# its own (made up as well; "Last Lap" unlocks as the last lap starts).
MKDS_SET = ra_set.RaSet({"ID": 4, "Title": "Mario Kart DS", "Achievements": [
    {"ID": i, "Title": title, "Description": desc, "Points": pts, "Flags": 3}
    for i, (title, desc, pts) in enumerate([
        ("First Cup", "Win any cup in 50cc", 5),
        ("Mushroom Rush", "Use three mushrooms in one lap", 3),
        ("Figure It Out", "Finish Figure-8 Circuit without hitting a wall", 5),
        ("Last Lap", "Reach the last lap of a Grand Prix race", 2),
        ("Photo Finish", "Win a race by less than a tenth of a second", 10),
        ("Star Rank", "Get a star rank in any 150cc cup", 25),
    ], 1)]})
# The course: the middles of Figure-8 Circuit's checkpoints (x, z, rounded),
# the finish line first, and how far each line reaches either side of them
MKDS_COURSE = 0x14
MKDS_MIDS = [(-80, 0), (720, 10), (1300, -40), (1860, -220), (2260, -650), (2390, -1160), (2270, -1660),
             (1900, -2010), (1440, -2080), (970, -1970), (510, -1670), (30, -1140), (-520, -520), (-1030, 40),
             (-1620, 640), (-2120, 1160), (-2550, 1460), (-3000, 1570), (-3500, 1420), (-3730, 950),
             (-3600, 410), (-3220, 80), (-2750, -10), (-2250, 0), (-1550, 0), (-850, 0)]
MKDS_HALF_WIDTH = 350
# The racers in slot order (the player first): character, how far ahead
# they start (world units), and how they speed up and drop back: by how much,
# over how long (s), from where in that (radians), and how far off the
# middle of the road they drive
MKDS_RACERS = [
    ("Mario", -1100, 1700, 40.0, -1.57, -90), ("Luigi", 1900, 450, 9.0, 1.3, 110),    # (Mario: up from last)
    ("Peach", 1400, 420, 8.0, 4.4, -140), ("Yoshi", 700, 380, 11.0, 4.1, 60),
    ("Bowser", -100, 450, 6.5, 0.7, 150), ("Toad", 2500, 300, 10.0, 3.6, -40),
    ("Donkey Kong", -800, 400, 8.5, 5.2, 20), ("Wario", -1500, 350, 12.0, 2.2, -110),
]
MKDS_SPEED = 980          # world units a second (a lap in about 16 s)
# Heights: the diagonal (checkpoints 9-15, from the far loop to the near one)
# is the bridge, over the straight the race starts on (as the course file has
# it), with ramps up and down either side
MKDS_LOW, MKDS_HIGH = 772, 965
MKDS_BRIDGE = (8.0, 9.0, 15.0, 16.0)      # (checkpoint + how far on) up from, up at, down from, down at
MKDS_START = 3000         # how far into lap 2 the scene starts


def mkds_checkpoints():
    """The demo course's checkpoints, as core/mkds_reader.py reads them: a
    line across the road at each middle, square to the way it runs."""
    out = []
    n = len(MKDS_MIDS)
    for i, (x, z) in enumerate(MKDS_MIDS):
        (ax, az), (bx, bz) = MKDS_MIDS[i - 1], MKDS_MIDS[(i + 1) % n]
        dx, dz = bx - ax, bz - az
        length = (dx * dx + dz * dz) ** 0.5
        nx, nz = -dz / length * MKDS_HALF_WIDTH, dx / length * MKDS_HALF_WIDTH
        out.append((x - nx, z - nz, x + nx, z + nz, i if i % 6 == 0 else -1))
    return tuple(out)


def mkds_race(into):
    """The race `into` seconds into the scene: each racer's lap, last
    checkpoint and place worked out from how far round it is, as the reader
    does from the console's."""
    import math
    from .mkds_reader import COURSES, progress, rank
    cps = mkds_checkpoints()
    n = len(MKDS_MIDS)
    seg = [math.dist(MKDS_MIDS[i], MKDS_MIDS[(i + 1) % n]) for i in range(n)]
    lap_len = sum(seg)
    racers = []
    for slot, (char, ahead, amp, period, phase, side) in enumerate(MKDS_RACERS):
        s = lap_len + MKDS_START + ahead + MKDS_SPEED * into + amp * math.sin(2 * math.pi * into / period + phase)
        lap, rest = int(s // lap_len) + 1, s % lap_len
        cp = 0
        while rest >= seg[cp]:
            rest -= seg[cp]
            cp += 1
        (ax, az), (bx, bz) = MKDS_MIDS[cp], MKDS_MIDS[(cp + 1) % n]
        f = rest / seg[cp]
        nx, nz = -(bz - az) / seg[cp], (bx - ax) / seg[cp]
        x, z = ax + (bx - ax) * f + nx * side, az + (bz - az) * f + nz * side
        a, b, c, d = MKDS_BRIDGE
        at = cp + f
        up = min(1.0, max(0.0, (at - a) / (b - a))) * min(1.0, max(0.0, (d - at) / (d - c)))
        racers.append({'slot': slot, 'player': slot == 0, 'character': char, 'x': x, 'z': z,
                       'y': MKDS_LOW + (MKDS_HIGH - MKDS_LOW) * up, 'lap': lap,
                       'checkpoint': cp, 'progress': progress(lap, cp, x, z, MKDS_MIDS), 'place': None})
    order = rank(racers)
    me = racers[0]
    return {
        'course': MKDS_COURSE, 'course_name': COURSES[MKDS_COURSE][0], 'mode': 'Grand Prix',
        'cup': 'Mushroom', 'cc': '150cc', 'mirror': False, 'lap': me['lap'], 'laps': 3,
        'place': me['place'], 'finished': False, 'time_ms': int((48.2 + into) * 1000),
        'character': me['character'], 'kart': 0, 'racers': racers, 'order': order, 'checkpoints': cps,
        'item': mkds_item(into), 'cup_points': 18,
    }


# The player's items through the scene: (from second, item byte, how many),
# using them up (a triple a shell at a time) with nothing held between
MKDS_ITEMS = [(0.0, 0x0B, 3), (2.5, 0x0B, 2), (4.5, 0x0B, 1), (6.0, None, 0), (8.0, 0x05, 3), (10.5, 0x05, 2),
              (12.0, 0x05, 1), (13.5, None, 0), (16.0, 0x0C, 1)]


def mkds_item(into):
    """The player's item `into` seconds into the scene, as the reader has it."""
    from .mkds_reader import item_of
    _, n, count = [i for i in MKDS_ITEMS if i[0] <= into][-1]
    return item_of(bytes([n, 0, 0, 0, 0, 0, 0, 0, count])) if n is not None else None


def mkds_last_lap_at():
    """Seconds into the scene that the player starts the last lap."""
    t = 0.0
    while mkds_race(t)['lap'] < 3 and t < 60:
        t += 0.05
    return t


# Pokemon Black, made up as well: a party, and a set (unlocked: the first
# four; "Bug Out" unlocks during the scene).
BW_PARTY = [
    _mon(502, 24, 61, 70, 'M', nickname='Dewott', moves=('Razor Shell', 'Water Gun', 'Fury Cutter', 'Focus Energy')),
    _mon(521, 22, 50, 66, 'F', nickname='Unfezant', moves=('Air Cutter', 'Quick Attack', 'Leer')),
    _mon(523, 23, 19, 64, 'M', nickname='Zebstrika', status='Paralyzed', moves=('Spark', 'Flame Charge')),
    _mon(570, 21, 48, 48, 'F', nickname='Zorua', shiny=True, moves=('Pursuit', 'Fury Swipes')),
    _mon(554, 20, 0, 58, 'M', nickname='Darumaka', moves=('Tackle', 'Fire Fang')),
    dict(_mon(637, 1, 10, 10, 'genderless', nickname='Egg'), egg=True),
]
BW_PARTY[1]['item'] = 'Oran Berry'
BW_SET = ra_set.RaSet({"ID": 3887, "Title": "Pokemon Black Version", "Achievements": [
    {"ID": i, "Title": title, "Description": desc, "Points": pts, "Flags": 3}
    for i, (title, desc, pts) in enumerate([
        ("New Adventure", "Choose your first partner in Nuvema Town", 1),
        ("Trio Badge", "Beat the Striaton City Gym", 5),
        ("Basic Badge", "Beat Lenora at the Nacrene City Gym", 5),
        ("Dream Mist", "Find Munna in the Dreamyard", 3),
        ("Bug Out", "Beat Burgh in Castelia City and earn the Insect Badge", 10),
        ("Castelia Cone", "Buy a Casteliacone on a Tuesday", 5),
        ("Ferris Wheel", "Ride the Nimbasa Ferris wheel", 5),
        ("Legend Badge", "Earn all eight Unova badges", 25),
        ("Hall of Fame", "Become the Champion of Unova", 50),
    ], 1)]})
BW_UNLOCK_AT = 6.0

# (name, seconds) in playing order. The short overworld stretches between
# battles let each battle start fresh (transition, shiny banner).
SCENES = [
    ('unova', 16), ('unova_battle', 13), ('unova', 3), ('unova_gym', 11), ('unova_places', 15),
    ('other', 16), ('tetris', 24),   # (two of the Tetris loop's 11.71 s)
    ('mkds', 20),
    ('overworld', 10), ('wild', 17), ('overworld', 3), ('shiny', 11), ('overworld', 3),
    ('rival', 23), ('overworld', 3), ('snow', 10), ('overworld', 3), ('legend', 11),
    ('levelup', 8),
    ('offline', 6),
]


class DemoSource:
    status = "Demo mode"

    def __init__(self, base=None, name=None):
        """base: optional real parsed state to start from (its trainer and
        party are kept); otherwise everything is invented. name: trainer
        name to show instead of the demo's (or the base state's)."""
        self.base = base
        self.name = name
        self.t0 = time.time()
        self.skip = 0.0

    def next_scene(self):
        """Jump to the start of the next scene (bound to a key in the window)."""
        _, into, dur = self._scene()
        self.skip += dur - into

    def _scene(self):
        total = sum(d for _, d in SCENES)
        t = (time.time() - self.t0 + self.skip) % total
        for name, dur in SCENES:
            if t < dur:
                return name, t, dur
            t -= dur
        return SCENES[-1][0], 0.0, SCENES[-1][1]

    def _base_state(self, elapsed):
        if self.base:
            return copy.deepcopy(self.base)
        minutes = 34 + int(elapsed // 60)
        return {
            'trainer_name': 'DAWN', 'live_save_addr': '0x0', 'trainer_id': 12345,
            'secret_id': 54321, 'money': 3000, 'coins': 0, 'rival_name': 'BARRY',
            'character': 'Dawn', 'badges': pdata.BADGES[:2],
            'playtime': {'hours': 12, 'minutes': minutes % 60, 'seconds': int(elapsed) % 60},
            'party_count': len(PARTY), 'party': copy.deepcopy(PARTY),
            'location': {'map_id': 3, 'name': 'Jubilife City', 'area': 'Jubilife City',
                         'x': 100, 'z': 200, 'facing': 'down', 'weather': 0},
            'position_live': {'x': 0, 'height': 0, 'z': 0, 'stable_x': 0, 'stable_z': 0},
            'direction_raw': 1,
            'pokedex': {'obtained': True, 'seen': 24, 'caught': 11},
            'battle': {'pointer': '0x0', 'music_says_battle': False, 'active': False,
                       'wild': False, 'trainer': None, 'mons': []},
            'misc': {'music_id': 0x3F0, 'music': None, 'textbox_open': False,
                     'clock': '2026-09-25 14:03'},
        }

    def read(self):
        name, into, dur = self._scene()
        if name == 'offline':
            return None
        if name == 'other':
            return self._other(into)
        if name == 'tetris':
            return self._tetris(into)
        if name == 'mkds':
            return self._mkds(into)
        if name == 'unova':
            return self._unova(into)
        if name == 'unova_places':
            return self._unova_places(into)
        d = self._unova(into) if name.startswith('unova_') else self._base_state(time.time() - self.t0)
        if self.name:
            d['trainer_name'] = self.name
        lead = d['party'][0]

        if name == 'overworld':
            step = int(into // 2) % 4
            d['direction_raw'] = [1, 3, 0, 2][step]  # down, right, up, left
            d['location']['facing'] = pdata.DIRECTIONS[d['direction_raw']]
            return d

        if name == 'levelup':
            lead['level'] += 1 if into > 2 else 0
            lead['max_hp'] += 3 if into > 2 else 0
            d['location'].update(map_id=0, name='Route 203', area='Route 203')
            return d

        cfg = BATTLES[name]
        d['location'].update(map_id=1, name=cfg['place'], area=cfg['place'], weather=cfg['weather'],
                             weather_kind=cfg.get('weather_kind'))
        d['misc']['clock'] = f"2026-09-25 {cfg['clock']}"
        d['misc']['music_id'] = cfg['music']
        started, foe = [(s, m) for s, m in cfg['foes'] if s <= into][-1]
        foe = copy.deepcopy(foe)
        # Moves by the foe that's out now, and all of yours.
        mine = [(s, mv, dmg) for s, who, mv, dmg in cfg['moves'] if who == 'you' and s <= into]
        theirs = [(s, mv, dmg) for s, who, mv, dmg in cfg['moves'] if who == 'foe' and started <= s <= into]
        foe_hp = foe['max_hp'] - sum(dmg for s, _, dmg in mine if s >= started and s + HIT_DELAY <= into)
        lead['curr_hp'] = max(1, lead['curr_hp'] - sum(dmg for s, _, dmg in theirs if s + HIT_DELAY <= into))

        def last(used):
            done = [mv for s, mv, _ in used if s + HIT_DELAY + LAST_DELAY <= into]
            return done[-1] if done else None

        trainer = d.get('rival_name') if cfg['trainer'] == 'rival' else cfg['trainer']
        mons = [_battle_mon(lead, 'yours', uses=[mv for _, mv, _ in mine], last_move=last(mine), worn=LEAD_WORN),
                _battle_mon(foe, 'foe', max(0, foe_hp), uses=[mv for _, mv, _ in theirs], last_move=last(theirs))]
        for s, who, changes in cfg.get('effects', []):
            mon = mons[0] if who == 'you' else mons[1]
            if s + HIT_DELAY > into or (who == 'foe' and s < started):
                continue
            for stat, n in changes.get('stages', {}).items():
                mon['stages'][stat] = mon['stages'].get(stat, 0) + n
            mon['status'] = changes.get('status', mon['status'])
            mon['conditions'] += changes.get('conditions', [])
        d['battle'].update(active=True, wild=cfg['trainer'] is None, trainer=trainer, music_says_battle=True,
                           mons=mons)
        if d.get('kind') == 'bw':
            d['battle']['kind'] = cfg.get('kind') or ('trainer' if trainer else 'wild')
            mons[1]['owned'] = bool(cfg.get('owned'))
            if cfg.get('caught_at') is not None and into >= cfg['caught_at']:
                d['misc']['music_id'] = bw_data.CATCH_MUSIC
        elif trainer:
            d['battle']['trainer_class'] = 0x3F
        return d

    def _unova(self, into):
        """Pokemon Black's state (core/bw_parser.py's layout, with the game
        card's RetroAchievements keys)."""
        achs = BW_SET.playable_achievements
        earned = {a['id'] for a in achs[:4]}
        latest, recent = (4, time.time() - 3 * 3600), []
        if into >= BW_UNLOCK_AT:
            earned.add(5)
            recent = [(5, time.time() - (into - BW_UNLOCK_AT))]
            latest = recent[-1]
        step = int(into // 2) % 4
        return {
            'kind': 'bw', 'version': 'Black', 'trainer_name': self.name or 'Hilda', 'trainer_id': 31337,
            'secret_id': 4242, 'character': 'Hilda', 'money': 12850,
            'badges': bw_data.BADGES[:3] + (bw_data.BADGES[3:4] if into >= BW_UNLOCK_AT else []),
            'playtime': {'hours': 21, 'minutes': 7 + int(into // 60), 'seconds': int(into) % 60},
            'party_count': len(BW_PARTY), 'party': copy.deepcopy(BW_PARTY), 'zone': 0x1C,
            'location': {'map_id': 0x1C, 'name': 'Castelia City', 'area': 'Castelia City', 'x': 300 + step,
                         'z': 512, 'height': 0, 'facing': ['down', 'right', 'up', 'left'][step], 'weather': 0,
                         'gait': ['walk', 'run', 'bike', 'stand'][step]},
            'season': 'autumn', 'pokedex': {'obtained': True, 'national': False, 'seen': 58, 'caught': 31},
            'repel': max(0, 87 - int(into)), 'badge_shine': [2, 1, 2, 2, 0, 0, 0, 0],
            'route': {'trainers': (3, 5), 'items': (4, 4)}, 'subway': None, 'institute': None, 'league': None,
            'battle': {'pointer': '0x0', 'music_says_battle': False, 'active': False, 'wild': False,
                       'trainer': None, 'mons': [], 'style': None, 'trainer_id': 0},
            'misc': {'music_id': None, 'music': None, 'textbox_open': False, 'clock': '2026-10-09 17:30'},
            'game': {'code': 'IRBO'}, 'title': BW_SET.title, 'header_title': None, 'ra_set': BW_SET,
            'rich_presence': "Castelia City • Autumn • 4 badges • Pokedex: 31/58",
            'progress': (len(earned), len(achs)), 'started': time.time() - into - 2400,
            'unlocked': frozenset(earned), 'recent': recent, 'latest': latest, 'ra_note': None, 'signed_in': True,
        }

    def _unova_places(self, into):
        """Pokemon Black around the places with panels of their own, a
        season each: the Battle Subway (spring), the Battle Institute
        (summer), an Elite Four room (winter, at night)."""
        d = self._unova(30)
        part = min(2, int(into // 5))
        place, zone, season = [('Gear Station', 0x42, 'spring'), ('Battle Institute', 0x50, 'summer'),
                               ("Grimsley's Room", 0x8D, 'winter')][part]
        d['location'].update(name=place, area=place, map_id=zone)
        d.update(zone=zone, season=season, route={}, repel=0)
        if part == 0:
            d['subway'] = {'bp': 126, 'train': 'Super Single', 'streak': 23 + int(into), 'record': 49,
                           'trains': [('Single', 21, 21), ('Super Single', 23 + int(into), 49), ('Double', 0, 14)]}
        elif part == 1:
            d['institute'] = {'points': 4620, 'last': 4620, 'rank': bw_data.institute_rank(4620)}
        else:
            d['league'] = {'beaten': ['Shauntal'], 'here': 'Grimsley'}
            d['misc']['clock'] = '2026-01-09 22:15'
        return d

    def _tetris(self, into):
        """The Tetris loop (tetris_board()), over and over: a Tetris at the
        end of each, which counts in the lines and the score."""
        achs = TETRIS_SET.playable_achievements
        length = tetris_loop()[2]
        done, at = int(into // length), into % length
        board, piece, flashing, hold = tetris_board(at)
        lines, score = 38 + 4 * done, 21480 + 3200 * done
        earned = {1, 2, 3} if done else {1, 2}
        recent = [(3, time.time() - at)] if done else []
        latest = recent[-1] if done else (2, time.time() - 3 * 86400)
        return {
            'kind': 'other', 'game': {'code': 'ATRE'}, 'title': TETRIS_SET.title, 'header_title': None,
            'ra_set': TETRIS_SET, 'rich_presence': "Standard | Marathon | Score: 21480 | Lines Cleared: 38",
            'progress': (len(earned), len(achs)), 'started': time.time() - into - 900,
            'unlocked': frozenset(earned), 'recent': recent, 'latest': latest, 'ra_note': None, 'signed_in': True,
            'tetris': {'mode': 'Marathon', 'board': board, 'piece': piece, 'hold': hold,
                       'score': score, 'lines': lines, 'level': 1 + lines // 10, 'state': 0, 'over': False,
                       'paused': False, 'ghost': True, 'next': tetris_queue(at)},
        }

    def _mkds(self, into):
        """Mario Kart DS: the race (mkds_race()), and "Last Lap" unlocking as
        the player's last lap starts."""
        achs = MKDS_SET.playable_achievements
        race = mkds_race(into)
        earned, recent, latest = {1, 2, 3}, [], (3, time.time() - 4 * 86400)
        last_lap = mkds_last_lap_at()
        if into >= last_lap:
            earned.add(4)
            recent = [(4, time.time() - (into - last_lap))]
            latest = recent[-1]
        return {
            'kind': 'other', 'game': {'code': 'AMCE'}, 'title': MKDS_SET.title, 'header_title': None,
            'ra_set': MKDS_SET, 'rich_presence': "Grand Prix: Mario drives 'Standard MR' on 'Figure 8 Circuit'",
            'progress': (len(earned), len(achs)), 'started': time.time() - into - 1200,
            'unlocked': frozenset(earned), 'recent': recent, 'latest': latest, 'ra_note': None, 'signed_in': True,
            'mkds': race,
        }

    def _other(self, into):
        achs = OTHER_SET.playable_achievements
        earned = {a['id'] for a in achs[:3]}
        recent = []
        latest = (3, time.time() - 2 * 86400 - 3600)  # earned before, as RetroAchievements has it
        if into >= OTHER_UNLOCK_AT:
            earned.add(4)
            recent = [(4, time.time() - (into - OTHER_UNLOCK_AT))]
            latest = recent[-1]
        lap = min(3, 1 + int(into // 6))
        place = ['5th', '3rd', '1st'][lap - 1]
        return {
            'kind': 'other', 'game': {'code': 'DEMO'}, 'title': OTHER_SET.title, 'header_title': None,
            'ra_set': OTHER_SET, 'rich_presence': f"Lap {lap}/3 on Seaside Loop, in {place} place",
            'progress': (len(earned), len(achs)), 'started': time.time() - into - 1500,
            'unlocked': frozenset(earned), 'recent': recent, 'latest': latest, 'ra_note': None, 'signed_in': True,
        }
