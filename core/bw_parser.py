"""
bw_parser.py - Pokemon Black and White (US) from main RAM: the trainer,
the party, where you are, the season, the Pokedex and battles.

The state is laid out like core/parser.py's (Platinum), so the overlay's
battle view and the hub's events work on it unchanged, plus:

    'kind': 'bw', 'version': 'Black' or 'White', 'season': 'spring'...,
    'zone': the zone ID, battlers' 'pp_max' (the game keeps it), and
    'battle' 'style' ('single', 'double', 'triple', 'rotation') and
    'trainer_id' (0 in a wild battle)

Addresses are Black's (IRBO); White's (IRAO) are all 0x20 higher. They come
from tools that read these games on emulators (PKHeX's save layout, which
sits 1:1 in RAM at 0x0221BBAC; the DevonStudios RNG scripts;
NDS-Ironmon-Tracker; pokebot-nds; the RetroAchievements rich presence; the
Action Replay codes): see docs/research.md. None was checked on a DSi yet,
so parse() checks what it reads (the party's checksums, the zone, the
trainer's name) and returns None when it doesn't look like the game, and
the hub shows the game card instead.

Not known yet, so left out: the opponent trainer's name and class (the
game looks it up in the ROM from the trainer ID), the battlers' types,
stat stages and status (the battle copy's layout isn't known), and the
battle music.
"""

import struct
import time

from . import bw_data as bw
from .parser import PlatinumParser

WHITE_SHIFT = 0x20

# Gen V text is UTF-16 ending in 0xFFFF; a few symbols live in private codes.
_CHARS = {0x2467: '×', 0x2468: '÷', 0x246C: '…', 0x246D: '♂', 0x246E: '♀'}


def decode_text(raw):
    out = []
    for (c,) in struct.iter_unpack('<H', raw[:len(raw) // 2 * 2]):
        if c == 0xFFFF or c == 0:
            break
        out.append(_CHARS.get(c) or (chr(c) if c < 0xD800 or c >= 0xE000 else '?'))
    return ''.join(out)


class BWParser(PlatinumParser):
    # The save data, as it sits in RAM (Black).
    PARTY_COUNT = 0x022349B0       # u8
    PARTY = 0x022349B4             # 6 x 220 bytes
    SIZE_POKEMON = 0xDC
    TRAINER_NAME = 0x02234FB0      # 8 x u16
    TRAINER_ID = 0x02234FC0        # u16, secret ID (u16) right after
    GENDER = 0x02234FCD            # u8: 0 Hilbert, 1 Hilda
    PLAYTIME_SAVED = 0x02234FD0    # u16 hours, u8 minutes, u8 seconds (as last saved)
    MONEY = 0x0223CDAC             # u32
    BADGES = 0x0223CDB0            # u8, bit 0 = Trio ... bit 7 = Legend
    DEX = 0x0223D1B0               # u32 flags (bit 0: national dex), then caught, then 4 x seen
    DEX_BYTES = 0x54               # 649 bits each, padded
    PLAYTIME = 0x02256FD4          # the running clock: u16 hours, u8 minutes, u8 seconds
    # Field.
    ZONE = 0x0224F90C              # u16
    POSITION = 0x0224F910          # fx32 x, y (height), z; the tile is the upper u16
    FACING = 0x0224F924            # u8: 0 up, 4 left, 8 down, 12 right
    SEASON = 0x0224F9BC            # u8: 0 spring ... 3 winter
    MAX_ZONE = 0x1AA
    # Battle.
    IN_BATTLE = 0x0226ACE6         # u8, 0x41 in a battle
    BATTLE_TRAINER = 0x022697BE    # u16 trainer ID, 0 in a wild battle
    BATTLE_STYLE = 0x022A62F8      # u8: 0 single, 1 double, 2 triple, 3 rotation
    BATTLERS = 0x02269838          # 7 pointers to your side's battle copies, then 7 to the foe's
    SIDE_SLOTS = 7
    # A battle copy (BTL_POKEPARAM): the parts read, and where things are.
    BATTLER_READ = 0x13C
    B_SOURCE = 0x00                # pointer to the Pokemon's own 220 bytes
    B_SPECIES, B_MAX_HP, B_HP, B_LEVEL = 0x0C, 0x0E, 0x10, 0x18
    B_SPEED = 0xF6                 # stats from +0xEE: Atk, Def, SpA, SpD, Spe
    B_MOVES = 0x104                # 4 x 14 bytes: u16 move, u8 PP, u8 max PP, ...
    B_MOVE_SIZE = 14
    STYLES = ['single', 'double', 'triple', 'rotation']
    FACINGS = {0: 'up', 4: 'left', 8: 'down', 12: 'right'}

    def __init__(self, ram, charmap=None, version='Black'):
        super().__init__(ram, charmap)
        self.version = version
        self.shift = WHITE_SHIFT if version == 'White' else 0

    def a(self, address):
        """An address of Black's, for the version being read."""
        return address + self.shift

    # -- Pokemon ---------------------------------------------------------------

    def decode_pokemon(self, raw):
        """220-byte Gen V Pokemon -> dict (the same keys as Platinum's, and a
        few more). Encrypted like Gen IV's: the 128 bytes after the header
        shuffled and keyed by the checksum, the battle stats by the PID."""
        if len(raw) < self.SIZE_POKEMON:
            return None
        pid, flags, checksum = struct.unpack_from('<IHH', raw, 0)
        box = raw[0x08:0x88]
        party = raw[0x88:0xDC]
        if not flags & 0x2:
            box = self.crypt(box, checksum)
        if not flags & 0x1:
            party = self.crypt(party, pid)
        order = self.BLOCK_ORDERS[((pid >> 13) & 31) % 24]
        blocks = {letter: box[32 * i:32 * i + 32] for i, letter in enumerate(order)}
        a, b, c, d = blocks['A'], blocks['B'], blocks['C'], blocks['D']

        species, item, ot_id, ot_sid, exp = struct.unpack_from('<HHHHI', a, 0)
        ability = a[0x0D]
        moves = struct.unpack_from('<4H', b, 0)
        pp = list(b[0x08:0x0C])
        ivs = struct.unpack_from('<I', b, 0x10)[0]
        gender_bits, nature = b[0x18], b[0x19]
        status, level, _, hp, max_hp = struct.unpack_from('<IBBHH', party, 0)
        speed = struct.unpack_from('<H', party, 0x0E)[0]
        return {
            'species_id': species,
            'species': self.name(bw.SPECIES, species),
            'nickname': decode_text(c[0:22]),
            'level': level,
            'curr_hp': hp,
            'max_hp': max_hp,
            'status': self.status_text(status),
            'item': None if not item else f'#{item}',
            'moves': [self.name(bw.MOVES, m) for m in moves if m],
            'pp': [pp[k] for k, m in enumerate(moves) if m],
            'nature': bw.NATURES[nature] if nature < 25 else bw.NATURES[pid % 25],
            'gender': 'genderless' if gender_bits & 0x4 else ('F' if gender_bits & 0x2 else 'M'),
            'form': gender_bits >> 3,
            'shiny': (ot_id ^ ot_sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8,
            'egg': bool(ivs >> 30 & 1),
            'ability_id': ability,
            'exp': exp,
            'speed': speed,
            'ot_id': ot_id | ot_sid << 16,
            'ot_name': decode_text(d[0:16]),
            'checksum_ok': (sum(struct.unpack('<64H', box)) & 0xFFFF) == checksum,
        }

    def battler(self, raw, mon, side):
        """A battle copy (BATTLER_READ bytes) and its Pokemon's own decoded
        data -> a battle mon dict like Platinum's, or None if it doesn't
        look real."""
        if len(raw) < self.BATTLER_READ:
            return None
        species, max_hp, hp = struct.unpack_from('<HHH', raw, self.B_SPECIES)
        level = raw[self.B_LEVEL]
        if not (1 <= species <= bw.MAX_SPECIES and 1 <= level <= 100 and 0 < max_hp < 1000 and hp <= max_hp):
            return None
        moves, pps, maxes = [], [], []
        for k in range(4):
            move, pp, pp_max = struct.unpack_from('<HBB', raw, self.B_MOVES + self.B_MOVE_SIZE * k)
            if not move:
                continue
            if move >= len(bw.MOVES) or pp > pp_max or pp_max > 64:
                return None
            moves.append(bw.MOVES[move])
            pps.append(pp)
            maxes.append(pp_max)
        mon = mon if mon and mon.get('checksum_ok') else {}
        return {
            'species_id': species,
            'species': self.name(bw.SPECIES, species),
            'nickname': mon.get('nickname') or bw.SPECIES[species].upper(),
            'level': level,
            'curr_hp': hp,
            'max_hp': max_hp,
            'status': None,
            'moves': moves,
            'pp': pps,
            'pp_max': maxes,
            'pp_ups': [0] * len(moves),
            'shiny': bool(mon.get('shiny')),
            'gender': mon.get('gender', 'genderless'),
            'speed': struct.unpack_from('<H', raw, self.B_SPEED)[0],
            'speed_stage': 6,
            'ot_id': mon.get('ot_id', 0),
            'types': [],
            'stages': {},
            'conditions': [],
            'last_move': None,
            'side': side,
        }

    # -- state -----------------------------------------------------------------

    def _count_dex(self, raw):
        """Species flagged in a 0x54-byte dex bit array (bits 0-648)."""
        if len(raw) < 82:
            return 0
        return sum(bin(x).count('1') for x in raw[:81]) + (raw[81] & 1)

    def parse(self):
        A = self.a
        self.parsed_data = {}
        self.prefetch([
            (A(self.PARTY_COUNT), 4 + 6 * self.SIZE_POKEMON),
            (A(self.TRAINER_NAME), 0x24),
            (A(self.MONEY), 8),
            (A(self.DEX), 4 + 5 * self.DEX_BYTES),
            (A(self.PLAYTIME), 4),
            (A(self.ZONE), 0x1C),
            (A(self.SEASON), 1),
            (A(self.IN_BATTLE), 1),
            (A(self.BATTLE_TRAINER), 2),
            (A(self.BATTLE_STYLE), 1),
            (A(self.BATTLERS), 8 * self.SIDE_SLOTS),
        ])
        d = self.parsed_data
        d['kind'] = 'bw'
        d['version'] = self.version
        name = decode_text(self.read_bytes(A(self.TRAINER_NAME), 16))
        zone = self.read_u16(A(self.ZONE))
        count = self.read_u8(A(self.PARTY_COUNT))
        if count > 6 or zone > self.MAX_ZONE or not name:
            return None

        d['trainer_name'] = name
        d['trainer_id'] = self.read_u16(A(self.TRAINER_ID))
        d['secret_id'] = self.read_u16(A(self.TRAINER_ID) + 2)
        d['character'] = 'Hilda' if self.read_u8(A(self.GENDER)) == 1 else 'Hilbert'
        d['money'] = self.read_u32(A(self.MONEY))
        bits = self.read_u8(A(self.BADGES))
        d['badges'] = [n for i, n in enumerate(bw.BADGES) if bits >> i & 1]
        hours, minutes, seconds = struct.unpack('<HBB', self.read_bytes(A(self.PLAYTIME), 4) or b'\0' * 4)
        if minutes >= 60 or seconds >= 60 or hours > 999:
            hours, minutes, seconds = struct.unpack('<HBB', self.read_bytes(A(self.PLAYTIME_SAVED), 4) or b'\0' * 4)
        d['playtime'] = {'hours': hours, 'minutes': minutes, 'seconds': seconds}

        d['party_count'] = count
        d['party'] = []
        for slot in range(count):
            address = A(self.PARTY) + slot * self.SIZE_POKEMON
            mon = self.decode_pokemon(self.read_bytes(address, self.SIZE_POKEMON))
            if not mon or not mon['checksum_ok'] or not 1 <= mon['species_id'] <= bw.MAX_SPECIES:
                continue
            mon['slot'] = slot + 1
            mon['address'] = hex(address)
            d['party'].append(mon)
        if count and not d['party']:
            return None  # a party that doesn't decode: these aren't Black/White's addresses

        x, y, z = [self.read_s32(A(self.POSITION) + 4 * i) >> 16 for i in range(3)]
        place = bw.zone_name(zone)
        d['zone'] = zone
        d['location'] = {
            'map_id': zone, 'name': place, 'area': place, 'x': x, 'z': z, 'height': y,
            'facing': self.FACINGS.get(self.read_u8(A(self.FACING)), 'down'), 'weather': 0,
        }
        season = self.read_u8(A(self.SEASON))
        d['season'] = bw.SEASONS[season] if season < 4 else None

        flags = self.read_u32(A(self.DEX))
        caught = self._count_dex(self.read_bytes(A(self.DEX) + 4, self.DEX_BYTES))
        seen_bits = bytearray(self.DEX_BYTES)
        for k in range(4):  # seen as male, female, shiny male, shiny female
            for i, v in enumerate(self.read_bytes(A(self.DEX) + 4 + (1 + k) * self.DEX_BYTES, self.DEX_BYTES)):
                seen_bits[i] |= v
        seen = self._count_dex(bytes(seen_bits))
        d['pokedex'] = {'obtained': bool(seen or caught), 'national': bool(flags & 1),
                        'seen': max(seen, caught), 'caught': caught}

        d['battle'] = self._battle(d)
        d['misc'] = {'music_id': None, 'music': None, 'textbox_open': False,
                     'clock': time.strftime('%Y-%m-%d %H:%M')}
        return d

    def battler_pointers(self):
        """[(slot, side, pointer)] for the battlers out now, from the pointer
        lists: one a side, two in a double battle (the overlay shows at most
        two)."""
        A = self.a
        style = self.read_u8(A(self.BATTLE_STYLE))
        out_now = 2 if style in (1, 2) else 1
        found = []
        for side_index, side in enumerate(('yours', 'foe')):
            for k in range(out_now):
                ptr = self.read_u32(A(self.BATTLERS) + 4 * (side_index * self.SIDE_SLOTS + k))
                if self.is_ram_pointer(ptr):
                    found.append((k, side if k == 0 else f'{side} (2nd)', ptr))
        return found

    def _battle(self, d):
        A = self.a
        battle = {'pointer': '0x0', 'music_says_battle': False, 'active': False, 'wild': False,
                  'trainer': None, 'mons': [], 'style': None, 'trainer_id': 0}
        if self.read_u8(A(self.IN_BATTLE)) != 0x41:
            return battle
        style = self.read_u8(A(self.BATTLE_STYLE))
        battle['style'] = self.STYLES[style] if style < 4 else None
        battle['trainer_id'] = self.read_u16(A(self.BATTLE_TRAINER))
        pointers = self.battler_pointers()
        self.prefetch([(ptr, self.BATTLER_READ) for _, _, ptr in pointers])
        sources = [self.read_u32(ptr + self.B_SOURCE) for _, _, ptr in pointers]
        self.prefetch([(src, self.SIZE_POKEMON) for src in sources if self.is_ram_pointer(src)])
        for (slot, side, ptr), src in zip(pointers, sources):
            own = self.decode_pokemon(self.read_bytes(src, self.SIZE_POKEMON)) if self.is_ram_pointer(src) else None
            mon = self.battler(self.read_bytes(ptr, self.BATTLER_READ), own, side)
            if mon:
                mon['battler'] = hex(ptr)
                battle['mons'].append(mon)
        sides = {m['side'] for m in battle['mons']}
        battle['active'] = 'yours' in sides and 'foe' in sides
        player = d['trainer_id'] | d['secret_id'] << 16
        battle['wild'] = battle['trainer_id'] == 0 or any(
            m['ot_id'] == player for m in battle['mons'] if m['side'].startswith('foe'))
        if battle['active']:
            battle['pointer'] = hex(self.read_u32(A(self.BATTLERS)))
        return battle

    # -- quick battle reads (core/hub.py, between full reads) --------------------

    @classmethod
    def quick_ranges(cls, last, version):
        """The reads that update the battlers of `last` (a parsed state in a
        battle): HP and moves of each, and the battle flag and pointers to
        notice the battle changing."""
        shift = WHITE_SHIFT if version == 'White' else 0
        ranges = [(cls.IN_BATTLE + shift, 1), (cls.BATTLERS + shift, 8 * cls.SIDE_SLOTS)]
        for m in last['battle']['mons']:
            ptr = int(m['battler'], 16)
            ranges += [(ptr + cls.B_SPECIES, 6), (ptr + cls.B_MOVES, 4 * cls.B_MOVE_SIZE)]
        return ranges

    @classmethod
    def apply_quick(cls, last, got):
        """`last` with its battlers' HP and PP from `got` (the reads of
        quick_ranges, in order), or None if the battle changed and a full
        read is needed."""
        if not got or got[0][:1] != b'\x41':
            return None
        pointers = got[1]
        mons = []
        for i, m in enumerate(last['battle']['mons']):
            hp_raw, moves_raw = got[2 + 2 * i], got[3 + 2 * i]
            species, max_hp, hp = struct.unpack('<HHH', hp_raw)
            if species != m['species_id'] or max_hp != m['max_hp'] or hp > max_hp:
                return None
            side_index = 0 if m['side'].startswith('yours') else 1
            slot = 1 if '2nd' in m['side'] else 0
            ptr = struct.unpack_from('<I', pointers, 4 * (side_index * cls.SIDE_SLOTS + slot))[0]
            if ptr != int(m['battler'], 16):
                return None  # someone switched in
            pps = []
            for k in range(4):
                move, pp, _ = struct.unpack_from('<HBB', moves_raw, cls.B_MOVE_SIZE * k)
                if move:
                    pps.append(pp)
            if len(pps) != len(m['moves']):
                return None
            mons.append(dict(m, curr_hp=hp, pp=pps))
        data = dict(last)
        data['battle'] = dict(last['battle'], mons=mons)
        return data
