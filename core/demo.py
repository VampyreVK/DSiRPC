"""
demo.py - DemoSource: a made-up game state that plays through a loop of
scenes, so the overlay can be styled without the DSi or a save file:
overworld, a wild battle by day, a shiny in the evening rain, the rival at
night (who switches Pokemon), a snowy route, a legendary in a cave, a level
up, Pokemon Black (its own main view, with an achievement unlocking, a
battle in the rain in Pinwheel Forest, and Burgh at the Castelia Gym),
another game (the game card every game
without its own parser gets, with an achievement unlocking), and the DSi
going offline.

All of the data here is invented. It follows the same dict layout as
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
                         foes=[(0, _mon(540, 19, 47, 47, 'F', moves=('Bug Bite', 'String Shot', 'Razor Leaf')))],
                         moves=[(2.5, 'you', 'Razor Shell', 16), (4, 'foe', 'Razor Leaf', 9),
                                (8.5, 'you', 'Water Gun', 7), (10, 'foe', 'String Shot', 0)],
                         effects=[(10, 'you', dict(stages={'SPE': -1}))]),
    'unova_gym': dict(place='Castelia Gym', clock='12:10', weather=0, music=0x46C, trainer='Burgh', kind='gym',
                      foes=[(0, _mon(544, 21, 54, 54, 'M', moves=('Poison Tail', 'Screech', 'Pursuit')))],
                      moves=[(4.5, 'you', 'Razor Shell', 14), (6, 'foe', 'Poison Tail', 8)],
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
BW_PARTY[1]['item'] = '#155'
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
    ('overworld', 10), ('wild', 17), ('overworld', 3), ('shiny', 11), ('overworld', 3),
    ('rival', 23), ('overworld', 3), ('snow', 10), ('overworld', 3), ('legend', 11),
    ('levelup', 8), ('unova', 16), ('unova_battle', 13), ('unova', 3), ('unova_gym', 11), ('other', 16),
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
        if name == 'unova':
            return self._unova(into)
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
                         'z': 512, 'height': 0, 'facing': ['down', 'right', 'up', 'left'][step], 'weather': 0},
            'season': 'autumn', 'pokedex': {'obtained': True, 'national': False, 'seen': 58, 'caught': 31},
            'battle': {'pointer': '0x0', 'music_says_battle': False, 'active': False, 'wild': False,
                       'trainer': None, 'mons': [], 'style': None, 'trainer_id': 0},
            'misc': {'music_id': None, 'music': None, 'textbox_open': False, 'clock': '2026-10-09 17:30'},
            'game': {'code': 'IRBO'}, 'title': BW_SET.title, 'header_title': None, 'ra_set': BW_SET,
            'rich_presence': "Castelia City • Autumn • 4 badges • Pokedex: 31/58",
            'progress': (len(earned), len(achs)), 'started': time.time() - into - 2400,
            'unlocked': frozenset(earned), 'recent': recent, 'latest': latest, 'ra_note': None, 'signed_in': True,
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
