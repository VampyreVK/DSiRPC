import struct
import logging

from . import platinum_data as pdata

class TrainerMemory:
    """Keeps the opponent's name steady for a whole battle.

    The trainer class at battle +0x3C6 can read something else for a moment
    (seen once while a Gym Leader sent out her last Pokemon), so each battle
    shows the name it has read most often. Give it every parsed state, in
    order; a new battle starts after two good reads without one (or a new
    battle pointer)."""

    def __init__(self):
        self.votes = {}
        self.pointer = None
        self.idle = 0

    def apply(self, data):
        if not data:
            return data  # a failed read says nothing about the battle
        battle = data['battle']
        if not battle['active']:
            self.idle += 1
            if self.idle >= 2:
                self.votes = {}
            return data
        if self.idle >= 2 or battle['pointer'] != self.pointer:
            self.votes = {}
        self.idle = 0
        self.pointer = battle['pointer']
        name = battle.get('trainer')
        if name and not name.startswith('sprite'):
            self.votes[name] = self.votes.get(name, 0) + 1
        if self.votes:
            battle['trainer'] = max(self.votes, key=self.votes.get)  # a tie keeps the first one read
        return data


class PlatinumParser:
    ANCHOR_POINTER = 0x02101D40
    # Absolute base RAM physical offset translation (index 0 of a RAM dump = 0x02000000)
    # Base NDS Ram starts at 0x02000000. So we subtract 0x02000000 to get array indices.
    RAM_OFFSET = 0x02000000

    # Offsets relative to the Live Save Block (Destination of the Anchor Pointer)
    OFFSET_TRAINER_NAME = 0x7C
    OFFSET_PLAYTIME = 0x9E  # u16 hours, u8 minutes, u8 seconds (0xAC is the party capacity)
    OFFSET_PARTY_BLOCK = 0xB0

    # Pokemon details
    SIZE_POKEMON = 236
    POKEMON_OFFSET_LEVEL = 0x8C
    POKEMON_OFFSET_CURR_HP = 0x8E
    POKEMON_OFFSET_MAX_HP = 0x90

    # More live save block offsets. Checked against ram_dump.bin and the
    # pret/pokeplatinum decomp; several come from the RetroAchievements notes.
    OFFSET_TRAINER_ID = 0x8C      # u16, secret ID (u16) right after
    OFFSET_MONEY = 0x90           # u32
    OFFSET_GENDER = 0x94          # u8: 0 = Lucas, 1 = Dawn
    OFFSET_BADGES = 0x96          # u8 bitmask, bit 0 = Coal ... bit 7 = Beacon
    OFFSET_COINS = 0x9C           # u16
    OFFSET_LOCATION = 0x1294      # s32 x5: map ID, warp ID, x, z, facing
    OFFSET_WEATHER = 0x12FA       # u16
    OFFSET_DEX_CAUGHT = 0x1340    # 493 bits, bit n-1 = national dex #n
    OFFSET_DEX_SEEN = 0x1380      # same layout
    OFFSET_DEX_OBTAINED = 0x1656  # u8, 1 once you have the Pokedex
    OFFSET_RIVAL_NAME = 0x27FC    # 8 x u16, the name chosen for the rival in the intro
    TRAINER_CLASS_RIVAL = 0x3F    # trainer class at battle +0x3C6 when fighting the rival

    # Static addresses outside the save block.
    FIELD_POINTER = 0x02101D2C        # RA: "Current Map + Poketch Pointer"
    FIELD_RA_DIRECTION = 0x2A0884     # RA: "Player Direction and Action", used as (u16 of pointer) + this
    BATTLE_POINTER = 0x021BFB0C       # not cleared after a battle, so check the data too
    BATTLE_OFFSET_TRAINER_SPRITE = 0x3C6  # the opponent's trainer class (RA calls it a sprite ID)
    BATTLE_OFFSET_MONS = 0x4F40       # 4 BattleMons: you, foe, your 2nd, foe's 2nd
    # u16 x4, the move each battler used last (BattleContext.movePrevByBattler).
    # Worked out from the decomp's struct layout relative to the BattleMons
    # above (see docs/research.md). Checked on hardware for your side; the
    # foe's entry hasn't been seen change yet.
    BATTLE_OFFSET_LAST_MOVES = 0x527C
    SIZE_BATTLE_MON = 0xC0
    BATTLE_SIDES = ('yours', 'foe', 'yours (2nd)', 'foe (2nd)')  # BattleMon slots 0-3
    # The parts of a BattleMon that decode_battle_mon() looks at, as
    # (offset, length). The hub's quick in-battle reads fetch only these.
    BATTLE_MON_FIELDS = ((0x00, 0x1C), (0x26, 0x2E), (0x6C, 0x0C), (0x7E, 1))
    MUSIC_ID = 0x021BEB04             # u16
    TEXTBOX_ACTIVE = 0x021C04E3       # u8, 2 while an NPC text box is open
    POS_MIRROR = 0x021C5CCC           # fx32 x, y (height), z; the tile is the upper u16
    POS_STABLE = 0x021C5CE4           # fx32 x, ?, z ("stable copy" in the RA notes)
    RTC = 0x021BF5D8                  # u32 year, month, day, weekday, hour, minute

    # Gen IV data block order, indexed by ((PID & 0x3E000) >> 13) % 24.
    BLOCK_ORDERS = ['ABCD', 'ABDC', 'ACBD', 'ACDB', 'ADBC', 'ADCB',
                    'BACD', 'BADC', 'BCAD', 'BCDA', 'BDAC', 'BDCA',
                    'CABD', 'CADB', 'CBAD', 'CBDA', 'CDAB', 'CDBA',
                    'DABC', 'DACB', 'DBAC', 'DBCA', 'DCAB', 'DCBA']

    def __init__(self, ram_dump, charmap):
        self.ram = ram_dump
        self.charmap = charmap
        self.live_save_addr = None
        self.parsed_data = {}

    def read_u32(self, address):
        """Reads a 32-bit unsigned integer from the absolute memory address."""
        index = address - self.RAM_OFFSET
        if index < 0 or index + 4 > len(self.ram):
            return 0
        return struct.unpack('<I', self.ram[index:index+4])[0]

    def read_s32(self, address):
        index = address - self.RAM_OFFSET
        if index < 0 or index + 4 > len(self.ram):
            return 0
        return struct.unpack('<i', self.ram[index:index+4])[0]

    def read_u16(self, address):
        index = address - self.RAM_OFFSET
        if index < 0 or index + 2 > len(self.ram):
            return 0
        return struct.unpack('<H', self.ram[index:index+2])[0]

    def read_u8(self, address):
        index = address - self.RAM_OFFSET
        if index < 0 or index + 1 > len(self.ram):
            return 0
        return self.ram[index]

    def read_bytes(self, address, length):
        index = address - self.RAM_OFFSET
        if index < 0 or index + length > len(self.ram):
            return b''
        return self.ram[index:index+length]

    def is_ram_pointer(self, value):
        return self.RAM_OFFSET <= value < self.RAM_OFFSET + 0x400000

    def prefetch(self, ranges):
        """Tells a sparse RAM source (core.dsi_memory.DsiRam) what is about to
        be read, so it can fetch it in as few requests as possible. A full
        RAM dump has nothing to prefetch."""
        if hasattr(self.ram, 'prefetch'):
            self.ram.prefetch([(address - self.RAM_OFFSET, length) for address, length in ranges
                               if self.is_ram_pointer(address)])

    @staticmethod
    def name(table, index):
        return table[index] if 0 <= index < len(table) else f'#{index}'

    @staticmethod
    def status_text(status):
        for mask, text in pdata.STATUS_BITS:
            if status & mask:
                return text
        return None

    @staticmethod
    def crypt(data, seed):
        """Gen IV stream cipher over 16-bit words (the same call encrypts and decrypts)."""
        words = struct.unpack(f'<{len(data) // 2}H', data)
        out = []
        x = seed
        for w in words:
            x = (0x41C64E6D * x + 0x6073) & 0xFFFFFFFF
            out.append(w ^ (x >> 16))
        return struct.pack(f'<{len(out)}H', *out)

    def decode_pokemon(self, raw):
        """236-byte party Pokemon -> dict. In RAM these are encrypted like in the
        save file, except while the game has one unlocked (flags at +0x04)."""
        from .charmap import decode_string

        pid, flags, checksum = struct.unpack_from('<IHH', raw, 0)
        box = raw[0x08:0x88]
        party = raw[0x88:0xEC]
        if not flags & 0x2:
            box = self.crypt(box, checksum)
        if not flags & 0x1:
            party = self.crypt(party, pid)

        order = self.BLOCK_ORDERS[((pid & 0x3E000) >> 13) % 24]
        blocks = {letter: box[32 * i:32 * i + 32] for i, letter in enumerate(order)}
        a, b, c = blocks['A'], blocks['B'], blocks['C']

        species, item, ot_id, ot_sid = struct.unpack_from('<HHHH', a, 0)
        moves = struct.unpack_from('<4H', b, 0)
        ivs = struct.unpack_from('<I', b, 0x10)[0]
        gender_bits = b[0x18]
        status, level, _, hp, max_hp = struct.unpack_from('<IBBHH', party, 0)

        return {
            'species_id': species,
            'species': self.name(pdata.SPECIES, species),
            'nickname': decode_string(c[0:22], self.charmap),
            'level': level,
            'curr_hp': hp,
            'max_hp': max_hp,
            'status': self.status_text(status),
            'item': self.name(pdata.ITEMS, item),
            'moves': [self.name(pdata.MOVES, m) for m in moves if m],
            'nature': pdata.NATURES[pid % 25],
            'gender': 'genderless' if gender_bits & 0x4 else ('F' if gender_bits & 0x2 else 'M'),
            'shiny': (ot_id ^ ot_sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8,
            'egg': bool(ivs >> 30 & 1),
            'checksum_ok': (sum(struct.unpack('<64H', box)) & 0xFFFF) == checksum,
        }

    def decode_battle_mon(self, raw):
        """One BattleMon (0xC0 bytes, not encrypted). Returns None if it doesn't
        look like a real Pokemon, which is how leftover data shows up."""
        from .charmap import decode_string

        species = struct.unpack_from('<H', raw, 0x00)[0]
        level = raw[0x34]
        hp, max_hp = struct.unpack_from('<iI', raw, 0x4C)
        if not (1 <= species <= 493 and 1 <= level <= 100 and 0 < max_hp < 1000 and 0 <= hp <= max_hp):
            return None
        moves = struct.unpack_from('<4H', raw, 0x0C)
        pp, pp_ups = raw[0x2C:0x30], raw[0x30:0x34]  # ppCur[4], ppUps[4]
        status = struct.unpack_from('<I', raw, 0x6C)[0]
        # Speed stat at +0x06 and its stage (statBoosts[3], 0-12, 6 = no
        # change) at +0x1B, for guessing who moved first. The OT ID at +0x74
        # tells wild Pokemon apart: they're made with the player's ID.
        speed, speed_stage = struct.unpack_from('<H', raw, 0x06)[0], raw[0x1B]
        ot_id = struct.unpack_from('<I', raw, 0x74)[0]
        return {
            'species_id': species,
            'species': self.name(pdata.SPECIES, species),
            'nickname': decode_string(raw[0x36:0x4C], self.charmap),
            'level': level,
            'curr_hp': hp,
            'max_hp': max_hp,
            'status': self.status_text(status),
            'moves': [self.name(pdata.MOVES, m) for m in moves if m],
            'pp': [pp[k] for k, m in enumerate(moves) if m],
            'pp_ups': [pp_ups[k] for k, m in enumerate(moves) if m],
            'shiny': bool(raw[0x26] >> 5 & 1),
            'gender': {0: 'M', 1: 'F'}.get(raw[0x7E] & 0x0F, 'genderless'),
            'speed': speed,
            'speed_stage': speed_stage,
            'ot_id': ot_id,
        }

    def battle_mon(self, raw, slot, last_moves):
        """BattleMon `slot` (0-3) decoded, with its side and the last move it
        used (`last_moves`: the 8 bytes at BATTLE_OFFSET_LAST_MOVES). None if
        it isn't a real Pokemon."""
        mon = self.decode_battle_mon(raw) if len(raw) == self.SIZE_BATTLE_MON else None
        if mon:
            mon['side'] = self.BATTLE_SIDES[slot]
            last = struct.unpack_from('<H', last_moves, 2 * slot)[0] if len(last_moves) >= 2 * slot + 2 else 0
            mon['last_move'] = pdata.MOVES[last] if 0 < last < len(pdata.MOVES) else None
        return mon

    def parse(self):
        """Parses the RAM dump for configured values."""
        self.parsed_data.clear()
        from .charmap import decode_string

        # 0. Pointers and other fixed addresses, in one batch.
        self.prefetch([(self.ANCHOR_POINTER, 4), (self.FIELD_POINTER, 4), (self.BATTLE_POINTER, 4),
                       (self.MUSIC_ID, 2), (self.TEXTBOX_ACTIVE, 1), (self.RTC, 24),
                       (self.POS_MIRROR, 12), (self.POS_STABLE, 12)])

        # 1. Read Pointer Chain
        self.live_save_addr = self.read_u32(self.ANCHOR_POINTER)
        # Ensure it's a valid ram address
        if not (0x02000000 <= self.live_save_addr < 0x02400000):
            logging.error(f"Invalid live save block pointer: {hex(self.live_save_addr)}")
            return None
        save = self.live_save_addr
        field_ptr = self.read_u32(self.FIELD_POINTER)
        battle_ptr = self.read_u32(self.BATTLE_POINTER)
        direction_addr = None
        if self.is_ram_pointer(field_ptr):
            direction_addr = self.RAM_OFFSET + (field_ptr & 0xFFFF) + self.FIELD_RA_DIRECTION

        # Everything hanging off those pointers, in a second batch.
        wanted = [
            (save + self.OFFSET_TRAINER_NAME, self.OFFSET_PARTY_BLOCK + 4 + 6 * self.SIZE_POKEMON - self.OFFSET_TRAINER_NAME),
            (save + self.OFFSET_LOCATION, self.OFFSET_WEATHER + 2 - self.OFFSET_LOCATION),
            (save + self.OFFSET_DEX_CAUGHT, 0x80),
            (save + self.OFFSET_DEX_OBTAINED, 1),
            (save + self.OFFSET_RIVAL_NAME, 16),
        ]
        if direction_addr:
            wanted.append((direction_addr, 2))
        if self.is_ram_pointer(battle_ptr):
            wanted.append((battle_ptr + self.BATTLE_OFFSET_TRAINER_SPRITE, 2))
            wanted.append((battle_ptr + self.BATTLE_OFFSET_MONS, 4 * self.SIZE_BATTLE_MON))
            wanted.append((battle_ptr + self.BATTLE_OFFSET_LAST_MOVES, 8))
        self.prefetch(wanted)

        # 2. Extract Trainer Name
        raw_name = self.read_bytes(self.live_save_addr + self.OFFSET_TRAINER_NAME, 16)
        trainer_name = decode_string(raw_name, self.charmap)
        self.parsed_data['trainer_name'] = trainer_name
        self.parsed_data['live_save_addr'] = hex(self.live_save_addr)

        self.parsed_data['trainer_id'] = self.read_u16(save + self.OFFSET_TRAINER_ID)
        self.parsed_data['secret_id'] = self.read_u16(save + self.OFFSET_TRAINER_ID + 2)
        self.parsed_data['money'] = self.read_u32(save + self.OFFSET_MONEY)
        self.parsed_data['coins'] = self.read_u16(save + self.OFFSET_COINS)
        self.parsed_data['rival_name'] = decode_string(self.read_bytes(save + self.OFFSET_RIVAL_NAME, 16), self.charmap)
        self.parsed_data['character'] = 'Dawn' if self.read_u8(save + self.OFFSET_GENDER) else 'Lucas'
        badge_bits = self.read_u8(save + self.OFFSET_BADGES)
        self.parsed_data['badges'] = [n for i, n in enumerate(pdata.BADGES) if badge_bits >> i & 1]
        self.parsed_data['playtime'] = {
            'hours': self.read_u16(save + self.OFFSET_PLAYTIME),
            'minutes': self.read_u8(save + self.OFFSET_PLAYTIME + 2),
            'seconds': self.read_u8(save + self.OFFSET_PLAYTIME + 3),
        }

        # 3. Party Data
        party_start = self.live_save_addr + self.OFFSET_PARTY_BLOCK
        party_count = self.read_u32(party_start)

        self.parsed_data['party_count'] = party_count
        self.parsed_data['party'] = []

        # 4. Every Pokemon in the party (level/HP need decrypting, see decode_pokemon)
        if 0 < party_count <= 6:
            for slot in range(party_count):
                mon_addr = party_start + 4 + slot * self.SIZE_POKEMON
                mon = self.decode_pokemon(self.read_bytes(mon_addr, self.SIZE_POKEMON))
                mon['slot'] = slot + 1
                mon['address'] = hex(mon_addr)
                self.parsed_data['party'].append(mon)

        # 5. Where the player is
        map_id, warp_id, x, z, facing = [self.read_s32(save + self.OFFSET_LOCATION + 4 * i) for i in range(5)]
        place, area = pdata.MAPS[map_id] if 0 <= map_id < len(pdata.MAPS) else ('?', f'map {map_id}')
        self.parsed_data['location'] = {
            'map_id': map_id,
            'name': place,
            'area': area,
            'x': x,
            'z': z,
            'facing': pdata.DIRECTIONS[facing] if 0 <= facing < 4 else facing,
            'weather': self.read_u16(save + self.OFFSET_WEATHER),
        }
        self.parsed_data['position_live'] = {
            'x': self.read_u16(self.POS_MIRROR + 2),
            'height': self.read_u16(self.POS_MIRROR + 6),
            'z': self.read_u16(self.POS_MIRROR + 10),
            'stable_x': self.read_u16(self.POS_STABLE + 2),
            'stable_z': self.read_u16(self.POS_STABLE + 10),
        }
        self.parsed_data['direction_raw'] = self.read_u16(direction_addr) if direction_addr else None

        # 6. Pokedex
        def count_bits(address):
            bits = self.read_bytes(address, 62)
            return sum(bin(x).count('1') for x in bits[:61]) + bin(bits[61] & 0x1F).count('1') if len(bits) == 62 else 0
        self.parsed_data['pokedex'] = {
            'obtained': bool(self.read_u8(save + self.OFFSET_DEX_OBTAINED)),
            'seen': count_bits(save + self.OFFSET_DEX_SEEN),
            'caught': count_bits(save + self.OFFSET_DEX_CAUGHT),
        }

        # 7. Battle
        music = self.read_u16(self.MUSIC_ID)
        battle = {'pointer': hex(battle_ptr), 'music_says_battle': music in pdata.BATTLE_MUSIC,
                  'active': False, 'wild': False, 'trainer': None, 'mons': []}
        if self.is_ram_pointer(battle_ptr):
            last_moves = self.read_bytes(battle_ptr + self.BATTLE_OFFSET_LAST_MOVES, 8)
            for i in range(len(self.BATTLE_SIDES)):
                raw = self.read_bytes(battle_ptr + self.BATTLE_OFFSET_MONS + i * self.SIZE_BATTLE_MON, self.SIZE_BATTLE_MON)
                mon = self.battle_mon(raw, i, last_moves)
                if mon:
                    battle['mons'].append(mon)
            sides_found = {m['side'] for m in battle['mons']}
            battle['active'] = 'yours' in sides_found and 'foe' in sides_found
            # Wild Pokemon are made with the player's own trainer ID (TID and
            # SID as one u32); a trainer's Pokemon get a random one.
            player_id = self.parsed_data['trainer_id'] | self.parsed_data['secret_id'] << 16
            battle['wild'] = any(m['ot_id'] == player_id for m in battle['mons'] if m['side'].startswith('foe'))
            if battle['active']:
                sprite = self.read_u16(battle_ptr + self.BATTLE_OFFSET_TRAINER_SPRITE)
                battle['trainer_class'] = sprite
                if sprite not in pdata.TRAINER_SPRITES and (sprite & 0xFF) in pdata.TRAINER_SPRITES:
                    sprite &= 0xFF  # it may only be a u8; ignore the byte after it
                if sprite == self.TRAINER_CLASS_RIVAL and self.parsed_data.get('rival_name'):
                    battle['trainer'] = self.parsed_data['rival_name']  # whatever the rival was named
                else:
                    battle['trainer'] = pdata.TRAINER_SPRITES.get(sprite, f'sprite {sprite:#x}')
                if battle['wild']:
                    battle['trainer'] = None  # whatever the class field says, there's no trainer
        self.parsed_data['battle'] = battle

        # 8. Odds and ends
        rtc = [self.read_u32(self.RTC + 4 * i) for i in range(6)]
        self.parsed_data['misc'] = {
            'music_id': music,
            'music': pdata.MUSIC.get(music),
            'textbox_open': self.read_u8(self.TEXTBOX_ACTIVE) == 2,
            'clock': f'20{rtc[0]:02d}-{rtc[1]:02d}-{rtc[2]:02d} {rtc[4]:02d}:{rtc[5]:02d}',
        }

        return self.parsed_data
