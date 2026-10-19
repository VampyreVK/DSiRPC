"""A made-up Pokemon Black/White RAM image laid out the way core/bw_parser.py
expects, with properly encrypted Gen V Pokemon: make() builds the field (or
a battle, the Continue menu...) for the parser and the fake DSi."""
import struct

from core.bw_parser import BWParser as P, WHITE_SHIFT
from core.parser import PlatinumParser

BASE = 0x02000000


def text(s, n):
    out = b"".join(struct.pack("<H", {'♂': 0x246D, '♀': 0x246E}.get(c, ord(c))) for c in s) + b"\xff\xff"
    return (out + b"\0" * n)[:n]


def pkm(pid, species, level, hp, max_hp, nick, tid=12345, sid=54321, moves=(33, 39), item=0, female=False,
        egg=False, status=0, nature=3, speed=40):
    a = bytearray(32); b = bytearray(32); c = bytearray(32); d = bytearray(32)
    struct.pack_into("<HHHHI", a, 0, species, item, tid, sid, 1000)
    a[0x0D] = 65
    for k, m in enumerate(moves):
        struct.pack_into("<H", b, 2 * k, m); b[8 + k] = 20
    struct.pack_into("<I", b, 0x10, (1 << 30) if egg else 0)
    b[0x18] = 0x2 if female else 0
    b[0x19] = nature
    c[0:22] = text(nick, 22)
    d[0:16] = text("VIV", 16)
    blocks = {'A': a, 'B': b, 'C': c, 'D': d}
    order = PlatinumParser.BLOCK_ORDERS[((pid >> 13) & 31) % 24]
    box = b"".join(bytes(blocks[l]) for l in order)
    checksum = sum(struct.unpack("<64H", box)) & 0xFFFF
    party = bytearray(0x54)
    struct.pack_into("<IBBHH", party, 0, status, level, 0, hp, max_hp)
    struct.pack_into("<H", party, 0x0E, speed)
    return struct.pack("<IHH", pid, 0, checksum) + PlatinumParser.crypt(box, checksum) + PlatinumParser.crypt(bytes(party), pid)


def battler(species, level, hp, max_hp, moves, source):
    raw = bytearray(0x224)
    struct.pack_into("<I", raw, 0, source)
    struct.pack_into("<HHH", raw, 0x0C, species, max_hp, hp)
    raw[0x18] = level
    struct.pack_into("<H", raw, 0xF6, 55)
    for k, (m, pp, mx) in enumerate(moves):
        struct.pack_into("<HBB", raw, 0x10A + 14 * k, m, pp, mx)
    return bytes(raw)


def make(version="Black", battle=False, wild=True, zone=0x1C, music=0x400, weather=2, rtc=(21, 5, 9, 26, 10, 9), rtc_at=0,
         field=True, player_slot=2, facing=3):
    ram = bytearray(0x400000)
    s = WHITE_SHIFT if version == "White" else 0

    def put(addr, data):
        o = addr + s - BASE
        ram[o:o + len(data)] = data
    party = [pkm(0x12345678, 501, 18, 44, 52, "Oshawott"),
             pkm(0x0BADF00D, 519, 12, 30, 33, "Pidove", female=True, item=155),
             pkm(0x00000000 ^ (12345 ^ 54321) << 16, 570, 20, 0, 50, "Zorua"),  # shiny (PID hi = TID^SID, lo = 0)
             pkm(0xCAFEBABE, 637, 1, 10, 10, "Egg", egg=True)]
    put(P.PARTY_COUNT, bytes([len(party)]))
    for i, raw in enumerate(party):
        put(P.PARTY + i * 0xDC, raw)
    put(P.TRAINER_NAME, text("Hilda", 16))
    put(P.TRAINER_ID, struct.pack("<HH", 12345, 54321))
    put(P.GENDER, b"\x01")
    put(P.MONEY, struct.pack("<I", 23456))
    put(P.BADGES, b"\x07")
    put(P.PLAYTIME, struct.pack("<HBB", 15, 42, 7))
    dex = bytearray(4 + 5 * 0x54)
    dex[0] = 1
    for sp in (495, 498, 501, 504, 519):
        dex[4 + (sp - 1) // 8] |= 1 << ((sp - 1) % 8)
    for sp in (495, 498, 501, 504, 519, 506, 509, 570):
        dex[4 + 0x54 * (1 + sp % 4) + (sp - 1) // 8] |= 1 << ((sp - 1) % 8)
    put(P.DEX, bytes(dex))
    put(P.ZONE, struct.pack("<H", zone))  # 0x1C Castelia City
    put(P.SEASON + 1, bytes([weather]))
    put(P.MUSIC, struct.pack("<H", music))
    if rtc:
        put(P.RTC[rtc_at], struct.pack("<6I", *rtc))
    put(P.POSITION, struct.pack("<iii", 300 << 16, 0, 512 << 16))
    if field:  # the player's map object (none on the menu)
        for i in range(player_slot):
            put(P.MAP_OBJECTS + i * 0x100, struct.pack("<H", 1 + i))
        put(P.MAP_OBJECTS + player_slot * 0x100, struct.pack("<H", 0xFF))
        put(P.MAP_OBJECTS + player_slot * 0x100 + 0x10, bytes([facing]))
    put(P.SEASON, b"\x02")
    if battle:
        put(P.IN_BATTLE, b"\x41")
        put(P.BATTLE_TRAINER, struct.pack("<H", 0 if wild else 77))
        put(P.BATTLE_STYLE, b"\x00")
        foe_src = 0x0226ACF4
        put(foe_src, pkm(0x77777777, 506, 9, 28, 28, "Lillipup", tid=12345 if wild else 999, sid=54321 if wild else 1))
        mine_ptr, foe_ptr = 0x0226D6A4, 0x0226D6A4 + 0x224
        put(mine_ptr, battler(501, 18, 40, 52, [(55, 23, 25), (33, 30, 35)], P.PARTY + s))
        put(foe_ptr, battler(506, 9, 20, 28, [(33, 35, 35), (43, 30, 30)], foe_src + s))
        put(P.BATTLERS, struct.pack("<I", mine_ptr + s))
        put(P.BATTLERS + 4 * 7, struct.pack("<I", foe_ptr + s))
    return bytes(ram)
