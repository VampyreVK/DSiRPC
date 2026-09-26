"""
demo.py - DemoSource: a made-up game state that plays through a loop of
scenes, so the overlay can be styled without the DSi or a save file:
overworld, a wild battle by day, a shiny in the evening rain, the rival at
night (who switches Pokemon), a snowy route, a legendary in a cave, a level
up, and the DSi going offline.

All of the data here is invented. It follows the same dict layout as
core/parser.py, so anything that works with the demo works with the real
game.
"""

import copy
import time

from . import platinum_data as pdata

WILD_MUSIC, TRAINER_MUSIC, RIVAL_MUSIC = 0x45C, 0x45F, 0x464


def _mon(species_id, level, hp, max_hp, gender, nickname=None, shiny=False, status=None, moves=()):
    species = pdata.SPECIES[species_id]
    return {
        'species_id': species_id, 'species': species,
        'nickname': nickname or species.upper(), 'level': level,
        'curr_hp': hp, 'max_hp': max_hp, 'status': status, 'item': 'None',
        'moves': list(moves), 'nature': 'Hardy', 'gender': gender,
        'shiny': shiny, 'egg': False, 'checksum_ok': True,
    }


def _battle_mon(mon, side, hp=None, used=0):
    """`used`: how much PP each move has spent, for the move panel."""
    base = [pdata.MOVE_INFO.get(m, (None, None, 20))[2] for m in mon['moves']]
    return {
        'species_id': mon['species_id'], 'species': mon['species'],
        'nickname': mon['nickname'], 'level': mon['level'],
        'curr_hp': mon['curr_hp'] if hp is None else hp, 'max_hp': mon['max_hp'],
        'status': mon['status'], 'moves': mon['moves'], 'shiny': mon['shiny'],
        'gender': mon['gender'], 'side': side,
        'pp': [max(0, b - used * (i + 1)) for i, b in enumerate(base)], 'pp_ups': [0] * len(base),
    }


PARTY = [
    _mon(393, 18, 44, 52, 'M', moves=('Bubble', 'Peck', 'Growl', 'Bide')),
    _mon(396, 12, 30, 33, 'F', moves=('Tackle', 'Quick Attack')),
    _mon(403, 11, 21, 34, 'M', status='Paralyzed', moves=('Tackle', 'Leer', 'Spark')),
    _mon(406, 9, 26, 26, 'F', moves=('Absorb', 'Growth')),
    _mon(77, 15, 40, 41, 'F', shiny=True, moves=('Ember', 'Tackle')),
    _mon(399, 7, 0, 25, 'M', moves=('Tackle',)),
]

# Battles: where and when they happen, the foe(s) in order (seconds into the
# scene they appear), and hits as (second, 'foe' or 'you', damage).
BATTLES = {
    'wild': dict(place='Route 203', clock='14:03', weather=0, music=WILD_MUSIC, trainer=None,
                 foes=[(0, _mon(396, 10, 29, 29, 'M', moves=('Tackle', 'Growl', 'Quick Attack')))],
                 hits=[(3, 'foe', 9), (4.5, 'you', 5), (6.5, 'foe', 10), (8, 'you', 4), (10, 'foe', 12)]),
    'shiny': dict(place='Route 212', clock='18:40', weather=2, music=WILD_MUSIC, trainer=None,
                  foes=[(0, _mon(77, 14, 38, 38, 'F', shiny=True, moves=('Ember', 'Tackle')))],
                  hits=[(4, 'foe', 7), (6, 'you', 6)]),
    'rival': dict(place='Route 205', clock='21:15', weather=0, music=RIVAL_MUSIC, trainer='rival',
                  foes=[(0, _mon(387, 17, 51, 51, 'M', moves=('Razor Leaf', 'Bite', 'Withdraw'))),
                        (8, _mon(396, 16, 44, 44, 'M', moves=('Wing Attack', 'Quick Attack')))],
                  hits=[(2.5, 'foe', 18), (4, 'you', 8), (5.5, 'foe', 20), (7, 'foe', 13), (10.5, 'foe', 15),
                        (12, 'you', 6)]),
    'snow': dict(place='Route 216', clock='11:20', weather=6, music=WILD_MUSIC, trainer=None,
                 foes=[(0, _mon(459, 32, 88, 88, 'F', moves=('Ice Shard', 'Razor Leaf')))],
                 hits=[(3, 'foe', 20), (5, 'you', 9)]),
    'legend': dict(place='Turnback Cave', clock='16:00', weather=0, music=0x0, trainer=None,
                   foes=[(0, _mon(487, 47, 190, 190, 'genderless', moves=('Shadow Force', 'Dragon Claw')))],
                   hits=[(4, 'foe', 30), (6, 'you', 12)]),
}

# (name, seconds) in playing order. The short overworld stretches between
# battles let each battle start fresh (transition, shiny banner).
SCENES = [
    ('overworld', 10), ('wild', 13), ('overworld', 3), ('shiny', 9), ('overworld', 3),
    ('rival', 14), ('overworld', 3), ('snow', 8), ('overworld', 3), ('legend', 9),
    ('levelup', 8), ('offline', 6),
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
                       'trainer': None, 'mons': []},
            'misc': {'music_id': 0x3F0, 'music': None, 'textbox_open': False,
                     'clock': '2026-09-25 14:03'},
        }

    def read(self):
        name, into, dur = self._scene()
        if name == 'offline':
            return None
        d = self._base_state(time.time() - self.t0)
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
        d['location'].update(map_id=1, name=cfg['place'], area=cfg['place'], weather=cfg['weather'])
        d['misc']['clock'] = f"2026-09-25 {cfg['clock']}"
        d['misc']['music_id'] = cfg['music']
        started, foe = [(s, m) for s, m in cfg['foes'] if s <= into][-1]
        foe = copy.deepcopy(foe)
        foe_hp = foe['max_hp'] - sum(dmg for s, who, dmg in cfg['hits'] if who == 'foe' and started <= s <= into)
        your_hp = lead['curr_hp'] - sum(dmg for s, who, dmg in cfg['hits'] if who == 'you' and s <= into)
        lead['curr_hp'] = max(1, your_hp)
        trainer = d['rival_name'] if cfg['trainer'] == 'rival' else None
        d['battle'].update(active=True, trainer=trainer, music_says_battle=True,
                           mons=[_battle_mon(lead, 'yours', used=int(into // 4)),
                                 _battle_mon(foe, 'foe', max(0, foe_hp))])
        if trainer:
            d['battle']['trainer_class'] = 0x3F
        return d
