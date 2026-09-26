"""
demo.py - DemoSource: a made-up game state that plays through a loop of
scenes (overworld, wild battle, shiny, rival, a legendary, a level up, the DSi
going offline), so the overlay can be styled without the DSi or a save file.

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


def _battle_mon(mon, side, hp=None):
    return {
        'species_id': mon['species_id'], 'species': mon['species'],
        'nickname': mon['nickname'], 'level': mon['level'],
        'curr_hp': mon['curr_hp'] if hp is None else hp, 'max_hp': mon['max_hp'],
        'status': mon['status'], 'moves': mon['moves'], 'shiny': mon['shiny'],
        'gender': mon['gender'], 'side': side,
    }


PARTY = [
    _mon(393, 18, 44, 52, 'M', moves=('Bubble', 'Peck', 'Growl', 'Bide')),
    _mon(396, 12, 30, 33, 'F', moves=('Tackle', 'Quick Attack')),
    _mon(403, 11, 21, 34, 'M', status='Paralyzed', moves=('Tackle', 'Leer', 'Spark')),
    _mon(406, 9, 26, 26, 'F', moves=('Absorb', 'Growth')),
    _mon(77, 15, 40, 41, 'F', shiny=True, moves=('Ember', 'Tackle')),
    _mon(399, 7, 0, 25, 'M', moves=('Tackle',)),
]

# (name, seconds) in playing order. The short overworld stretches between
# battles let each battle start fresh (transition, shiny banner).
SCENES = [
    ('overworld', 10), ('wild', 12), ('overworld', 3), ('shiny', 10), ('overworld', 3),
    ('rival', 12), ('overworld', 3), ('legend', 10), ('levelup', 8), ('offline', 6),
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

        # Battles: the foe loses HP over the scene, and so do you a little.
        frac = min(1.0, into / (dur * 0.8))
        if name == 'wild':
            foe, music, trainer = _mon(396, 10, 29, 29, 'M'), WILD_MUSIC, None
        elif name == 'shiny':
            foe, music, trainer = _mon(77, 14, 38, 38, 'F', shiny=True), WILD_MUSIC, None
        elif name == 'rival':
            foe, music, trainer = _mon(387, 17, 51, 51, 'M'), RIVAL_MUSIC, d['rival_name']
            d['battle']['trainer_class'] = 0x3F
        else:  # legend
            foe, music, trainer = _mon(487, 47, 190, 190, 'genderless'), 0x0, None
        foe_hp = max(1, round(foe['max_hp'] * (1.0 - 0.85 * frac)))
        your_hp = max(1, round(lead['curr_hp'] - 14 * frac))
        lead['curr_hp'] = your_hp
        d['battle'].update(active=True, trainer=trainer, music_says_battle=True,
                           mons=[_battle_mon(lead, 'yours'), _battle_mon(foe, 'foe', foe_hp)])
        d['misc']['music_id'] = music
        return d
