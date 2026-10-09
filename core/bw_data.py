"""
bw_data.py - names and tables for Pokemon Black and White (Generation V).

Gen V keeps Gen IV's numbering and adds to it, so these extend
core/platinum_data.py: Pokemon 494-649 (Victini to Genesect), moves 468-559
(Hone Claws to Fusion Bolt). Type numbers lose Gen IV's unused '???' slot.
Natures, status bits and the type chart are the same as Gen IV's.
"""

from . import platinum_data as pdata

BADGES = ['Trio', 'Basic', 'Insect', 'Bolt', 'Quake', 'Jet', 'Freeze', 'Legend']
GYM_LEADERS = ['Cilan', 'Lenora', 'Burgh', 'Elesa', 'Clay', 'Skyla', 'Brycen', 'Drayden']
NATURES = pdata.NATURES
STATUS_BITS = pdata.STATUS_BITS
TYPE_CHART = pdata.TYPE_CHART
DIRECTIONS = ['up', 'down', 'left', 'right']
SEASONS = ['spring', 'summer', 'autumn', 'winter']

# Gen V's internal type order (Gen IV's without '???').
TYPES = ['Normal', 'Fighting', 'Flying', 'Poison', 'Ground', 'Rock', 'Bug', 'Ghost', 'Steel',
         'Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Ice', 'Dragon', 'Dark']

_GEN5_SPECIES = [
    'Victini', 'Snivy', 'Servine', 'Serperior', 'Tepig', 'Pignite', 'Emboar', 'Oshawott', 'Dewott',
    'Samurott', 'Patrat', 'Watchog', 'Lillipup', 'Herdier', 'Stoutland', 'Purrloin', 'Liepard',
    'Pansage', 'Simisage', 'Pansear', 'Simisear', 'Panpour', 'Simipour', 'Munna', 'Musharna',
    'Pidove', 'Tranquill', 'Unfezant', 'Blitzle', 'Zebstrika', 'Roggenrola', 'Boldore', 'Gigalith',
    'Woobat', 'Swoobat', 'Drilbur', 'Excadrill', 'Audino', 'Timburr', 'Gurdurr', 'Conkeldurr',
    'Tympole', 'Palpitoad', 'Seismitoad', 'Throh', 'Sawk', 'Sewaddle', 'Swadloon', 'Leavanny',
    'Venipede', 'Whirlipede', 'Scolipede', 'Cottonee', 'Whimsicott', 'Petilil', 'Lilligant',
    'Basculin', 'Sandile', 'Krokorok', 'Krookodile', 'Darumaka', 'Darmanitan', 'Maractus',
    'Dwebble', 'Crustle', 'Scraggy', 'Scrafty', 'Sigilyph', 'Yamask', 'Cofagrigus', 'Tirtouga',
    'Carracosta', 'Archen', 'Archeops', 'Trubbish', 'Garbodor', 'Zorua', 'Zoroark', 'Minccino',
    'Cinccino', 'Gothita', 'Gothorita', 'Gothitelle', 'Solosis', 'Duosion', 'Reuniclus', 'Ducklett',
    'Swanna', 'Vanillite', 'Vanillish', 'Vanilluxe', 'Deerling', 'Sawsbuck', 'Emolga', 'Karrablast',
    'Escavalier', 'Foongus', 'Amoonguss', 'Frillish', 'Jellicent', 'Alomomola', 'Joltik',
    'Galvantula', 'Ferroseed', 'Ferrothorn', 'Klink', 'Klang', 'Klinklang', 'Tynamo', 'Eelektrik',
    'Eelektross', 'Elgyem', 'Beheeyem', 'Litwick', 'Lampent', 'Chandelure', 'Axew', 'Fraxure',
    'Haxorus', 'Cubchoo', 'Beartic', 'Cryogonal', 'Shelmet', 'Accelgor', 'Stunfisk', 'Mienfoo',
    'Mienshao', 'Druddigon', 'Golett', 'Golurk', 'Pawniard', 'Bisharp', 'Bouffalant', 'Rufflet',
    'Braviary', 'Vullaby', 'Mandibuzz', 'Heatmor', 'Durant', 'Deino', 'Zweilous', 'Hydreigon',
    'Larvesta', 'Volcarona', 'Cobalion', 'Terrakion', 'Virizion', 'Tornadus', 'Thundurus',
    'Reshiram', 'Zekrom', 'Landorus', 'Kyurem', 'Keldeo', 'Meloetta', 'Genesect',
]
SPECIES = pdata.SPECIES[:494] + _GEN5_SPECIES      # index = national dex number, 0 = none
MAX_SPECIES = len(SPECIES) - 1                     # 649

# New moves: (name, type, category, PP).
_GEN5_MOVES = [
    ('Hone Claws', 'Dark', 'Status', 15), ('Wide Guard', 'Rock', 'Status', 10),
    ('Guard Split', 'Psychic', 'Status', 10), ('Power Split', 'Psychic', 'Status', 10),
    ('Wonder Room', 'Psychic', 'Status', 10), ('Psyshock', 'Psychic', 'Special', 10),
    ('Venoshock', 'Poison', 'Special', 10), ('Autotomize', 'Steel', 'Status', 15),
    ('Rage Powder', 'Bug', 'Status', 20), ('Telekinesis', 'Psychic', 'Status', 15),
    ('Magic Room', 'Psychic', 'Status', 10), ('Smack Down', 'Rock', 'Physical', 15),
    ('Storm Throw', 'Fighting', 'Physical', 10), ('Flame Burst', 'Fire', 'Special', 15),
    ('Sludge Wave', 'Poison', 'Special', 10), ('Quiver Dance', 'Bug', 'Status', 20),
    ('Heavy Slam', 'Steel', 'Physical', 10), ('Synchronoise', 'Psychic', 'Special', 15),
    ('Electro Ball', 'Electric', 'Special', 10), ('Soak', 'Water', 'Status', 20),
    ('Flame Charge', 'Fire', 'Physical', 20), ('Coil', 'Poison', 'Status', 20),
    ('Low Sweep', 'Fighting', 'Physical', 20), ('Acid Spray', 'Poison', 'Special', 20),
    ('Foul Play', 'Dark', 'Physical', 15), ('Simple Beam', 'Normal', 'Status', 15),
    ('Entrainment', 'Normal', 'Status', 15), ('After You', 'Normal', 'Status', 15),
    ('Round', 'Normal', 'Special', 15), ('Echoed Voice', 'Normal', 'Special', 15),
    ('Chip Away', 'Normal', 'Physical', 20), ('Clear Smog', 'Poison', 'Special', 15),
    ('Stored Power', 'Psychic', 'Special', 10), ('Quick Guard', 'Fighting', 'Status', 15),
    ('Ally Switch', 'Psychic', 'Status', 15), ('Scald', 'Water', 'Special', 15),
    ('Shell Smash', 'Normal', 'Status', 15), ('Heal Pulse', 'Psychic', 'Status', 10),
    ('Hex', 'Ghost', 'Special', 10), ('Sky Drop', 'Flying', 'Physical', 10),
    ('Shift Gear', 'Steel', 'Status', 10), ('Circle Throw', 'Fighting', 'Physical', 10),
    ('Incinerate', 'Fire', 'Special', 15), ('Quash', 'Dark', 'Status', 15),
    ('Acrobatics', 'Flying', 'Physical', 15), ('Reflect Type', 'Normal', 'Status', 15),
    ('Retaliate', 'Normal', 'Physical', 5), ('Final Gambit', 'Fighting', 'Special', 5),
    ('Bestow', 'Normal', 'Status', 15), ('Inferno', 'Fire', 'Special', 5),
    ('Water Pledge', 'Water', 'Special', 10), ('Fire Pledge', 'Fire', 'Special', 10),
    ('Grass Pledge', 'Grass', 'Special', 10), ('Volt Switch', 'Electric', 'Special', 20),
    ('Struggle Bug', 'Bug', 'Special', 20), ('Bulldoze', 'Ground', 'Physical', 20),
    ('Frost Breath', 'Ice', 'Special', 10), ('Dragon Tail', 'Dragon', 'Physical', 10),
    ('Work Up', 'Normal', 'Status', 30), ('Electroweb', 'Electric', 'Special', 15),
    ('Wild Charge', 'Electric', 'Physical', 15), ('Drill Run', 'Ground', 'Physical', 10),
    ('Dual Chop', 'Dragon', 'Physical', 15), ('Heart Stamp', 'Psychic', 'Physical', 25),
    ('Horn Leech', 'Grass', 'Physical', 10), ('Sacred Sword', 'Fighting', 'Physical', 15),
    ('Razor Shell', 'Water', 'Physical', 10), ('Heat Crash', 'Fire', 'Physical', 10),
    ('Leaf Tornado', 'Grass', 'Special', 10), ('Steamroller', 'Bug', 'Physical', 20),
    ('Cotton Guard', 'Grass', 'Status', 10), ('Night Daze', 'Dark', 'Special', 10),
    ('Psystrike', 'Psychic', 'Special', 10), ('Tail Slap', 'Normal', 'Physical', 10),
    ('Hurricane', 'Flying', 'Special', 10), ('Head Charge', 'Normal', 'Physical', 15),
    ('Gear Grind', 'Steel', 'Physical', 15), ('Searing Shot', 'Fire', 'Special', 5),
    ('Techno Blast', 'Normal', 'Special', 5), ('Relic Song', 'Normal', 'Special', 10),
    ('Secret Sword', 'Fighting', 'Special', 10), ('Glaciate', 'Ice', 'Special', 10),
    ('Bolt Strike', 'Electric', 'Physical', 5), ('Blue Flare', 'Fire', 'Special', 5),
    ('Fiery Dance', 'Fire', 'Special', 10), ('Freeze Shock', 'Ice', 'Physical', 5),
    ('Ice Burn', 'Ice', 'Special', 5), ('Snarl', 'Dark', 'Special', 15),
    ('Icicle Crash', 'Ice', 'Physical', 10), ('V-create', 'Fire', 'Physical', 5),
    ('Fusion Flare', 'Fire', 'Special', 5), ('Fusion Bolt', 'Electric', 'Physical', 5),
]
MOVES = pdata.MOVES + [m[0] for m in _GEN5_MOVES]          # index = move ID
MOVE_INFO = dict(pdata.MOVE_INFO, **{m[0]: m[1:] for m in _GEN5_MOVES})  # name -> (type, category, PP)

# Zone IDs (the u16 the parser reads) -> place names, as (first, last,
# name) ranges. From the RetroAchievements rich presence for Pokemon Black
# (game 3887, by mulbruk), with "In the ..." and the like taken off.
_ZONE_RANGES = [
    (0x000, 0x000, 'Black City'), (0x006, 0x006, 'Striaton City'), (0x007, 0x007, 'Striaton Gym'),
    (0x008, 0x008, 'Striaton Pokémon Center'), (0x009, 0x00E, 'Striaton City'), (0x00F, 0x00F, "Trainer's School"),
    (0x010, 0x010, 'Nacrene City'), (0x011, 0x011, 'Nacrene Museum'), (0x012, 0x013, 'Nacrene Gym'),
    (0x014, 0x014, 'Nacrene Pokémon Center'), (0x015, 0x019, 'Nacrene City'), (0x01A, 0x01A, 'Café Warehouse'),
    (0x01B, 0x01B, 'Nacrene Gate'), (0x01C, 0x01C, 'Castelia City'), (0x01D, 0x01D, 'Castelia Gym'),
    (0x01E, 0x028, 'Castelia City'), (0x029, 0x029, 'Castelia Pokémon Center'),
    (0x02A, 0x02A, 'Passerby Analytics HQ'), (0x02B, 0x02B, 'Studio Castelia'),
    (0x02C, 0x02C, 'Battle Company (1F)'), (0x02D, 0x02D, 'Battle Company (47F)'),
    (0x02E, 0x02E, 'Battle Company (55F)'), (0x02F, 0x02F, 'GAME FREAK (1F)'), (0x030, 0x030, 'GAME FREAK (22F)'),
    (0x031, 0x032, 'Castelia City'), (0x033, 0x033, 'Castelia Gate'), (0x034, 0x034, 'Royal Unova'),
    (0x035, 0x035, 'Café Sonata'), (0x036, 0x03D, 'Castelia City'), (0x03E, 0x03E, 'Nimbasa City'),
    (0x03F, 0x03F, 'Nimbasa Gym'), (0x040, 0x040, 'Nimbasa City'), (0x041, 0x041, 'Nimbasa Pokémon Center'),
    (0x042, 0x04A, 'Gear Station'), (0x04B, 0x04B, 'Battle Subway'), (0x04C, 0x04C, 'Battle Subway'),
    (0x04D, 0x04D, 'Musical Theater'), (0x04E, 0x04E, 'Musical Stage'), (0x04F, 0x050, 'Big Stadium'),
    (0x051, 0x051, 'Soccer Stadium'), (0x052, 0x052, 'Baseball Stadium'), (0x053, 0x053, 'Football Stadium'),
    (0x054, 0x055, 'Small Court'), (0x056, 0x056, 'Tennis Court'), (0x057, 0x057, 'Basketball Court'),
    (0x058, 0x059, 'Nimbasa City'), (0x05A, 0x05C, 'Nimbasa Gate'), (0x05D, 0x05D, 'Battle Institute'),
    (0x05E, 0x05F, 'Nimbasa City'), (0x060, 0x060, 'Driftveil City'), (0x061, 0x062, 'Driftveil Gym'),
    (0x063, 0x063, 'Driftveil Pokémon Center'), (0x064, 0x068, 'Driftveil City'),
    (0x069, 0x069, 'Driftveil Market'), (0x06A, 0x06A, 'Driftveil City'), (0x06B, 0x06B, 'Mistralton City'),
    (0x06C, 0x06C, 'Mistralton Gym'), (0x06D, 0x06D, 'Mistralton Pokémon Center'),
    (0x06E, 0x06E, 'Mistralton City'), (0x06F, 0x06F, 'Mistralton Cargo Service'),
    (0x070, 0x070, 'Mistralton City'), (0x071, 0x071, 'Icirrus City'), (0x072, 0x072, 'Icirrus Gym'),
    (0x073, 0x073, 'Icirrus Pokémon Center'), (0x074, 0x076, 'Icirrus City'), (0x077, 0x077, 'Pokémon Fan Club'),
    (0x078, 0x078, 'Opelucid City'), (0x079, 0x079, 'Opelucid Gym'), (0x07A, 0x07A, 'Opelucid Pokémon Center'),
    (0x07B, 0x07C, "Drayden's House"), (0x07D, 0x07E, 'Battle House'), (0x07F, 0x082, 'Opelucid City'),
    (0x083, 0x085, 'Opelucid Gate'), (0x086, 0x087, 'Opelucid City'), (0x088, 0x08A, 'Pokémon League'),
    (0x08B, 0x08B, "N's Castle"), (0x08C, 0x08C, "Shauntal's Room"), (0x08D, 0x08D, "Grimsley's Room"),
    (0x08E, 0x08E, "Marshal's Room"), (0x08F, 0x08F, "Caitlin's Room"), (0x090, 0x090, "Champion's Room"),
    (0x091, 0x091, 'Hall of Fame'), (0x092, 0x092, 'League Pokémon Center'), (0x098, 0x099, 'Dreamyard'),
    (0x09A, 0x09B, 'Pinwheel Forest'), (0x09C, 0x09C, 'Rumination Field'), (0x09D, 0x09E, 'Desert Resort'),
    (0x09F, 0x09F, 'Desert Gate'), (0x0A0, 0x0BE, 'Relic Castle'), (0x0BF, 0x0C1, 'Cold Storage'),
    (0x0C2, 0x0C5, 'Chargestone Cave'), (0x0C6, 0x0CC, 'Twist Mountain'), (0x0CD, 0x0D5, 'Dragonspiral Tower'),
    (0x0D6, 0x0E4, 'Victory Road'), (0x0E5, 0x0E5, 'Trial Chamber'), (0x0E6, 0x0EA, 'Giant Chasm'),
    (0x0EB, 0x0ED, 'Liberty Garden'), (0x0EE, 0x0EF, 'P2 Laboratory'), (0x0F0, 0x0F0, 'Undella Bay'),
    (0x0F1, 0x0F8, 'Abyssal Ruins'), (0x0F9, 0x0F9, 'Skyarrow Bridge'), (0x0FA, 0x0FC, 'Skyarrow Gate'),
    (0x0FD, 0x0FD, 'Driftveil Drawbridge'), (0x0FE, 0x0FE, 'Tubeline Bridge'), (0x0FF, 0x105, 'Village Bridge'),
    (0x107, 0x107, 'Marvelous Bridge'), (0x108, 0x111, "N's Castle"), (0x112, 0x112, "N's Room"),
    (0x113, 0x116, "N's Castle"), (0x117, 0x117, 'Entralink'), (0x118, 0x11B, 'Entree Forest'),
    (0x11D, 0x11D, 'Entree Forest'), (0x11F, 0x120, 'Entree Forest'), (0x13D, 0x13D, 'Route 1'),
    (0x13E, 0x13E, 'Route Gate'), (0x13F, 0x13F, 'Route 2'), (0x140, 0x140, 'Accumula Gate'),
    (0x141, 0x142, 'Route 3'), (0x143, 0x143, 'Pokémon Daycare'), (0x144, 0x145, 'Wellspring Cave'),
    (0x146, 0x148, 'Route 4'), (0x149, 0x14A, 'Route 5'), (0x14B, 0x14B, 'Route 6'),
    (0x14C, 0x14C, 'Season Research Lab'), (0x14D, 0x14E, 'Mistralton Cave'), (0x14F, 0x14F, 'Guidance Chamber'),
    (0x150, 0x150, 'Route 6'), (0x151, 0x151, 'Route 7'), (0x152, 0x156, 'Celestial Tower'),
    (0x157, 0x158, 'Route 7'), (0x159, 0x159, 'Route 8'), (0x15A, 0x15A, 'Moor of Icirrus'),
    (0x15B, 0x15B, 'Tubeline Gate'), (0x15C, 0x15C, 'Route 9'), (0x15D, 0x15D, 'Tubeline Gate'),
    (0x15E, 0x15F, 'Shopping Mall Nine'), (0x160, 0x162, "Challenger's Cave"), (0x163, 0x163, 'Route 10'),
    (0x164, 0x16C, 'Badge Check Gates'), (0x16D, 0x16D, 'Route 11'), (0x16E, 0x16E, 'Bridge Gate'),
    (0x16F, 0x16F, 'Route 11'), (0x170, 0x170, 'Route 12'), (0x171, 0x171, 'Bridge Gate'),
    (0x172, 0x173, 'Route 13'), (0x174, 0x174, 'Undella Gate'), (0x175, 0x175, 'Route 13'),
    (0x176, 0x176, 'Route 14'), (0x177, 0x177, 'Black Gate'), (0x178, 0x178, 'Abundant Shrine'),
    (0x17A, 0x17A, 'Route 15'), (0x17B, 0x17B, 'Black Gate'), (0x17C, 0x17C, 'Marvelous Gate'),
    (0x17D, 0x17D, 'Poké Transfer Lab'), (0x17E, 0x17E, 'Route 15'), (0x17F, 0x17F, 'Route 16'),
    (0x180, 0x180, 'Marvelous Gate'), (0x181, 0x182, 'Lostlorn Forest'), (0x183, 0x184, 'Route 18'),
    (0x185, 0x185, 'Nuvema Town'), (0x186, 0x187, 'Your House'), (0x188, 0x189, "Bianca's House"),
    (0x18A, 0x18B, "Cheren's House"), (0x18C, 0x18C, "Juniper's Lab"), (0x18D, 0x18D, 'Accumula Town'),
    (0x18E, 0x18E, 'Accumula Pokémon Center'), (0x18F, 0x195, 'Accumula Town'), (0x196, 0x196, 'Lacunosa Town'),
    (0x197, 0x197, 'Lacunosa Pokémon Center'), (0x198, 0x19B, 'Lacunosa Town'), (0x19C, 0x19C, 'Undella Town'),
    (0x19D, 0x19D, 'Undella Pokémon Center'), (0x19E, 0x1A1, 'Undella Town'), (0x1A2, 0x1A5, 'Anville Town'),
    (0x1A6, 0x1A6, 'Union Room'), (0x1A7, 0x1A7, 'Route 17'), (0x1A8, 0x1A8, 'Black City'),
    (0x1A9, 0x1A9, "Black City's Pokémon Center"), (0x1AA, 0x1AA, 'Black City'),
]
ZONES = {zone: name for first, last, name in _ZONE_RANGES for zone in range(first, last + 1)}


def zone_name(zone):
    return ZONES.get(zone)


# Where battles happen, by words in the place's name: (sky, platform) for
# overlay/unova_art.py. Outdoors in winter is snowy where the game puts snow.
_TERRAIN_WORDS = [
    (('cave', 'chargestone', 'twist mountain', 'victory road', 'challenger', 'giant chasm', 'relic castle',
      'wellspring', 'mistralton cave'), ('cave', 'cave')),
    (('gym', 'center', 'mart', 'house', 'lab', 'tower', 'castle', 'league', 'subway', 'station', 'theater',
      'building', 'cold storage', 'mall', 'chamber', 'museum', 'hotel', 'room', 'gate'), ('indoor', 'indoor')),
    (('desert', 'route 4'), ('mountain', 'sand')),
    (('forest', 'dreamyard', 'shrine'), ('forest', 'grass')),
    (('bay', 'beach', 'sea', 'undella', 'humilau'), ('ocean', 'sand')),
    (('route 7', 'icirrus', 'dragonspiral'), ('field', 'grass')),
]
_SNOWY_IN_WINTER = ('route 6', 'route 7', 'route 8', 'icirrus', 'twist mountain', 'dragonspiral', 'opelucid',
                    'route 9', 'route 10', 'route 12', 'route 13', 'route 14', 'lacunosa', 'undella', 'route 15')


def terrain(location, season=None, surfing=False):
    """(sky, platform) for a battle at `location` (the parser's dict)."""
    text = f"{location.get('name') or ''} {location.get('area') or ''}".lower()
    if surfing:
        return 'ocean', 'water'
    for words, kind in _TERRAIN_WORDS:
        if any(w in text for w in words):
            if season == 'winter' and kind[0] in ('field', 'forest') and any(w in text for w in _SNOWY_IN_WINTER):
                return 'snow', 'snow'
            return kind
    if season == 'winter' and any(w in text for w in _SNOWY_IN_WINTER):
        return 'snow', 'snow'
    return 'field', 'grass'
