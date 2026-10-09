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
# Held items by the games' own numbers (None: unused): Gen IV's numbering,
# with Gen V's own items from 468 on and a few of Gen IV's slots reused (the
# Drives at 116-119, Sweet Heart at 134, the new Mail at 137-148). From
# IronMon Tracker's Gen 5 table (constants/ItemData.lua), accents dropped
# for the pixel font.
ITEMS = [
    None, 'Master Ball', 'Ultra Ball', 'Great Ball', 'Poke Ball', 'Safari Ball', 'Net Ball', 'Dive Ball',
    'Nest Ball', 'Repeat Ball', 'Timer Ball', 'Luxury Ball', 'Premier Ball', 'Dusk Ball', 'Heal Ball',
    'Quick Ball', 'Cherish Ball', 'Potion', 'Antidote', 'Burn Heal', 'Ice Heal', 'Awakening', 'Paralyze Heal',
    'Full Restore', 'Max Potion', 'Hyper Potion', 'Super Potion', 'Full Heal', 'Revive', 'Max Revive',
    'Fresh Water', 'Soda Pop', 'Lemonade', 'Moomoo Milk', 'Energy Powder', 'Energy Root', 'Heal Powder',
    'Revival Herb', 'Ether', 'Max Ether', 'Elixir', 'Max Elixir', 'Lava Cookie', 'Berry Juice', 'Sacred Ash',
    'Hp Up', 'Protein', 'Iron', 'Carbos', 'Calcium', 'Rare Candy', 'PP Up', 'Zinc', 'PP Max', 'Old Gateau',
    'Guard Spec', 'Dire Hit', 'X Attack', 'X Defense', 'X Speed', 'X Accuracy', 'X Sp-atk', 'X Sp-def',
    'Poke Doll', 'Fluffy Tail', 'Blue Flute', 'Yellow Flute', 'Red Flute', 'Black Flute', 'White Flute',
    'Shoal Salt', 'Shoal Shell', 'Red Shard', 'Blue Shard', 'Yellow Shard', 'Green Shard', 'Super Repel',
    'Max Repel', 'Escape Rope', 'Repel', 'Sun Stone', 'Moon Stone', 'Fire Stone', 'Thunder Stone', 'Water Stone',
    'Leaf Stone', 'Tiny Mushroom', 'Big Mushroom', 'Pearl', 'Big Pearl', 'Stardust', 'Star Piece', 'Nugget',
    'Heart Scale', 'Honey', 'Growth Mulch', 'Damp Mulch', 'Stable Mulch', 'Gooey Mulch', 'Root Fossil',
    'Claw Fossil', 'Helix Fossil', 'Dome Fossil', 'Old Amber', 'Armor Fossil', 'Skull Fossil', 'Rare Bone',
    'Shiny Stone', 'Dusk Stone', 'Dawn Stone', 'Oval Stone', 'Odd Keystone', 'Griseous Orb', None, None, None,
    'Douse Drive', 'Shock Drive', 'Burn Drive', 'Chill Drive', None, None, None, None, None, None, None, None,
    None, None, None, None, None, None, 'Sweet Heart', 'Adamant Orb', 'Lustrous Orb', 'Greet Mail', 'Favored Mail',
    'Rsvp Mail', 'Thanks Mail', 'Inquiry Mail', 'Like Mail', 'Reply Mail', 'Bridge Mail-s', 'Bridge Mail-d',
    'Bridge Mail-t', 'Bridge Mail-v', 'Bridge Mail-m', 'Cheri Berry', 'Chesto Berry', 'Pecha Berry', 'Rawst Berry',
    'Aspear Berry', 'Leppa Berry', 'Oran Berry', 'Persim Berry', 'Lum Berry', 'Sitrus Berry', 'Figy Berry',
    'Wiki Berry', 'Mago Berry', 'Aguav Berry', 'Iapapa Berry', 'Razz Berry', 'Bluk Berry', 'Nanab Berry',
    'Wepear Berry', 'Pinap Berry', 'Pomeg Berry', 'Kelpsy Berry', 'Qualot Berry', 'Hondew Berry', 'Grepa Berry',
    'Tamato Berry', 'Cornn Berry', 'Magost Berry', 'Rabuta Berry', 'Nomel Berry', 'Spelon Berry', 'Pamtre Berry',
    'Watmel Berry', 'Durin Berry', 'Belue Berry', 'Occa Berry', 'Passho Berry', 'Wacan Berry', 'Rindo Berry',
    'Yache Berry', 'Chople Berry', 'Kebia Berry', 'Shuca Berry', 'Coba Berry', 'Payapa Berry', 'Tanga Berry',
    'Charti Berry', 'Kasib Berry', 'Haban Berry', 'Colbur Berry', 'Babiri Berry', 'Chilan Berry', 'Liechi Berry',
    'Ganlon Berry', 'Salac Berry', 'Petaya Berry', 'Apicot Berry', 'Lansat Berry', 'Starf Berry', 'Enigma Berry',
    'Micle Berry', 'Custap Berry', 'Jaboca Berry', 'Rowap Berry', 'BrightPowder', 'White Herb', 'Macho Brace',
    'Exp Share', 'Quick Claw', 'Soothe Bell', 'Mental Herb', 'Choice Band', "King's Rock", 'Silver Powder',
    'Amulet Coin', 'Cleanse Tag', 'Soul Dew', 'Deep Sea-tooth', 'Deep Sea-scale', 'Smoke Ball', 'Everstone',
    'Focus Band', 'Lucky Egg', 'Scope Lens', 'Metal Coat', 'Leftovers', 'Dragon Scale', 'Light Ball', 'Soft Sand',
    'Hard Stone', 'Miracle Seed', 'BlackGlasses', 'Black Belt', 'Magnet', 'Mystic Water', 'Sharp Beak',
    'Poison Barb', 'Never Melt-ice', 'Spell Tag', 'Twisted Spoon', 'Charcoal', 'Dragon Fang', 'Silk Scarf',
    'Up Grade', 'Shell Bell', 'Sea Incense', 'Lax Incense', 'Lucky Punch', 'Metal Powder', 'Thick Club', 'Stick',
    'Red Scarf', 'Blue Scarf', 'Pink Scarf', 'Green Scarf', 'Yellow Scarf', 'Wide Lens', 'Muscle Band',
    'Wise Glasses', 'Expert Belt', 'Light Clay', 'Life Orb', 'Power Herb', 'Toxic Orb', 'Flame Orb',
    'Quick Powder', 'Focus Sash', 'Zoom Lens', 'Metronome', 'Iron Ball', 'Lagging Tail', 'Destiny Knot',
    'Black Sludge', 'Icy Rock', 'Smooth Rock', 'Heat Rock', 'Damp Rock', 'Grip Claw', 'Choice Scarf',
    'Sticky Barb', 'Power Bracer', 'Power Belt', 'Power Lens', 'Power Band', 'Power Anklet', 'Power Weight',
    'Shed Shell', 'Big Root', 'Choice Specs', 'Flame Plate', 'Splash Plate', 'Zap Plate', 'Meadow Plate',
    'Icicle Plate', 'Fist Plate', 'Toxic Plate', 'Earth Plate', 'Sky Plate', 'Mind Plate', 'Insect Plate',
    'Stone Plate', 'Spooky Plate', 'Draco Plate', 'Dread Plate', 'Iron Plate', 'Odd Incense', 'Rock Incense',
    'Full Incense', 'Wave Incense', 'Rose Incense', 'Luck Incense', 'Pure Incense', 'Protector', 'Electirizer',
    'Magmarizer', 'Dubious Disc', 'Reaper Cloth', 'Razor Claw', 'Razor Fang', 'TM01', 'TM02', 'TM03', 'TM04',
    'TM05', 'TM06', 'TM07', 'TM08', 'TM09', 'TM10', 'TM11', 'TM12', 'TM13', 'TM14', 'TM15', 'TM16', 'TM17', 'TM18',
    'TM19', 'TM20', 'TM21', 'TM22', 'TM23', 'TM24', 'TM25', 'TM26', 'TM27', 'TM28', 'TM29', 'TM30', 'TM31', 'TM32',
    'TM33', 'TM34', 'TM35', 'TM36', 'TM37', 'TM38', 'TM39', 'TM40', 'TM41', 'TM42', 'TM43', 'TM44', 'TM45', 'TM46',
    'TM47', 'TM48', 'TM49', 'TM50', 'TM51', 'TM52', 'TM53', 'TM54', 'TM55', 'TM56', 'TM57', 'TM58', 'TM59', 'TM60',
    'TM61', 'TM62', 'TM63', 'TM64', 'TM65', 'TM66', 'TM67', 'TM68', 'TM69', 'TM70', 'TM71', 'TM72', 'TM73', 'TM74',
    'TM75', 'TM76', 'TM77', 'TM78', 'TM79', 'TM80', 'TM81', 'TM82', 'TM83', 'TM84', 'TM85', 'TM86', 'TM87', 'TM88',
    'TM89', 'TM90', 'TM91', 'TM92', 'HM01', 'HM02', 'HM03', 'HM04', 'HM05', 'HM06', None, None, 'Explorer Kit',
    'Loot Sack', 'Rule Book', 'Poke Radar', 'Point Card', 'Journal', 'Seal Case', 'Fashion Case', 'Seal Bag',
    'Pal Pad', 'Works Key', 'Old Charm', 'Galactic Key', 'Red Chain', 'Town Map', 'Vs Seeker', 'Coin Case',
    'Old Rod', 'Good Rod', 'Super Rod', 'Sprayduck', 'Poffin Case', 'Bicycle', 'Suite Key', 'Oaks Letter',
    'Lunar Wing', 'Member Card', 'Azure Flute', 'Ss Ticket', 'Contest Pass', 'Magma Stone', 'Parcel', 'Coupon 1',
    'Coupon 2', 'Coupon 3', 'Storage Key', 'Secret Potion', 'Vs Recorder', 'Gracidea', 'Secret Key',
    'Apricorn Box', 'Unown Report', 'Berry Pots', 'Dowsing Machine', 'Blue Card', 'Slowpoke Tail', 'Clear Bell',
    'Card Key', 'Basement Key', 'Squirt Bottle', 'Red Scale', 'Lost Item', 'Pass', 'Machine Part', 'Silver Wing',
    'Rainbow Wing', 'Mystery Egg', 'Red Apricorn', 'Blue Apricorn', 'Yellow Apricorn', 'Green Apricorn',
    'Pink Apricorn', 'White Apricorn', 'Black Apricorn', 'Fast Ball', 'Level Ball', 'Lure Ball', 'Heavy Ball',
    'Love Ball', 'Friend Ball', 'Moon Ball', 'Sport Ball', 'Park Ball', 'Photo Album', 'Gb Sounds', 'Tidal Bell',
    'RageCandyBar', 'Data Card-01', 'Data Card-02', 'Data Card-03', 'Data Card-04', 'Data Card-05', 'Data Card-06',
    'Data Card-07', 'Data Card-08', 'Data Card-09', 'Data Card-10', 'Data Card-11', 'Data Card-12', 'Data Card-13',
    'Data Card-14', 'Data Card-15', 'Data Card-16', 'Data Card-17', 'Data Card-18', 'Data Card-19', 'Data Card-20',
    'Data Card-21', 'Data Card-22', 'Data Card-23', 'Data Card-24', 'Data Card-25', 'Data Card-26', 'Data Card-27',
    'Jade Orb', 'Lock Capsule', 'Red Orb', 'Blue Orb', 'Enigma Stone', 'Prism Scale', 'Eviolite', 'Float Stone',
    'Rocky Helmet', 'Air Balloon', 'Red Card', 'Ring Target', 'Binding Band', 'Absorb Bulb', 'Cell Battery',
    'Eject Button', 'Fire Gem', 'Water Gem', 'Electric Gem', 'Grass Gem', 'Ice Gem', 'Fighting Gem', 'Poison Gem',
    'Ground Gem', 'Flying Gem', 'Psychic Gem', 'Bug Gem', 'Rock Gem', 'Ghost Gem', 'Dragon Gem', 'Dark Gem',
    'Steel Gem', 'Normal Gem', 'Health Wing', 'Muscle Wing', 'Resist Wing', 'Genius Wing', 'Clever Wing',
    'Swift Wing', 'Pretty Wing', 'Cover Fossil', 'Plume Fossil', 'Liberty Pass', 'Pass Orb', 'Dream Ball',
    'Poke Toy', 'Prop Case', 'Dragon Skull', 'Balm Mushroom', 'Big Nugget', 'Pearl String', 'Comet Shard',
    'Relic Copper', 'Relic Silver', 'Relic Gold', 'Relic Vase', 'Relic Band', 'Relic Statue', 'Relic Crown',
    'Casteliacone', 'Dire Hit-2', 'X Speed-2', 'X Sp-atk-2', 'X Sp-def-2', 'X Defense-2', 'X Attack-2',
    'X Accuracy-2', 'X Speed-3', 'X Sp-atk-3', 'X Sp-def-3', 'X Defense-3', 'X Attack-3', 'X Accuracy-3',
    'X Speed-6', 'X Sp-atk-6', 'X Sp-def-6', 'X Defense-6', 'X Attack-6', 'X Accuracy-6', 'Ability Urge',
    'Item Drop', 'Item Urge', 'Reset Urge', 'Dire Hit-3', 'Light Stone', 'Dark Stone', 'TM93', 'TM94', 'TM95',
    'Xtransceiver', 'God Stone', 'Gram 1', 'Gram 2', 'Gram 3',
]


def item_name(item):
    """A held item's name, '#<id>' for an unknown number, None for none."""
    return None if not item else ITEMS[item] if item < len(ITEMS) and ITEMS[item] else f'#{item}'
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
    (0x1A9, 0x1A9, 'Black City Pokémon Center'), (0x1AA, 0x1AA, 'Black City'),
]
ZONES = {zone: name for first, last, name in _ZONE_RANGES for zone in range(first, last + 1)}


def zone_name(zone, version='Black'):
    """The place for a zone ID; White's Black City zones are White Forest."""
    name = ZONES.get(zone)
    if name and version == 'White' and name.startswith('Black'):
        name = 'White Forest' if name.startswith('Black City') else 'White Forest Gate'
    return name


# Who you're up against, by where the battle is (zone IDs). A Gym's leader
# room only counts while the Gym Leader music plays (some Gyms keep their
# trainers in the same zone); the Elite Four's and the Champion's rooms have
# nobody else in them. From the RetroAchievements notes for Black.
GYM_ROOMS = {0x07: 'Striaton', 0x13: 'Lenora', 0x1D: 'Burgh', 0x3F: 'Elesa', 0x61: 'Clay',
             0x6C: 'Skyla', 0x72: 'Brycen', 0x79: 'Opelucid'}
ELITE_ROOMS = {0x8C: 'Shauntal', 0x8D: 'Grimsley', 0x8E: 'Marshal', 0x8F: 'Caitlin'}
CHAMPION_ROOM, CHAMPION = 0x90, 'Alder'
LEADER_MUSIC = {0x46C, 0x47B}        # Gym Leader battle, and its last-Pokemon version
# Striaton's leader is the brother whose type beats your first partner.
STRIATON = [((495, 496, 497), 'Chili'), ((498, 499, 500), 'Cress'), ((501, 502, 503), 'Cilan')]


def opponent(zone, music, party_species, version='Black'):
    """(kind, name) of a trainer battle: kind 'gym', 'elite', 'champion' or
    'trainer'; name None when it isn't known."""
    if zone in ELITE_ROOMS:
        return 'elite', ELITE_ROOMS[zone]
    if zone == CHAMPION_ROOM:
        return 'champion', CHAMPION
    if music in LEADER_MUSIC:
        leader = GYM_ROOMS.get(zone)
        if leader == 'Opelucid':
            leader = 'Iris' if version == 'White' else 'Drayden'
        elif leader == 'Striaton':
            leader = next((name for line, name in STRIATON if any(s in line for s in party_species)), None)
        return 'gym', leader
    return 'trainer', None


# Trainers and items per place, as (RetroAchievements address, bit) flags
# set once a trainer is beaten or an item picked up (hidden ones included):
# {place: ([trainer flags], [item flags])}. Generated from the trainer and
# item notes for Black (docs/memory-map/), so places count only the ones
# the notes name; White's flags are 0x20 higher like everything else.
ROUTE_FLAGS = {
    'Abundant Shrine': ([(0x23C021, 2), (0x23C021, 3), (0x23C021, 4), (0x23C022, 1)],
                         [(0x23BFA6, 5), (0x23BFA6, 6), (0x23BFAC, 4), (0x23BFD4, 6), (0x23BFD5, 0), (0x23BFD5, 2), (0x23BFD5, 3), (0x23BFD5, 5)]),
    'Baseball Stadium': ([(0x23BFF1, 3)],
                          []),
    'Basketball Court': ([(0x23BFE3, 6), (0x23C003, 2), (0x23C003, 5), (0x23C003, 6), (0x23C004, 4), (0x23C005, 5)],
                          []),
    'Battle Company': ([(0x23BFE5, 1), (0x23BFE5, 2), (0x23BFE7, 5), (0x23BFE7, 6), (0x23BFE8, 0), (0x23BFEE, 1), (0x23BFEE, 2), (0x23BFEE, 3)],
                        [(0x23BFBF, 3), (0x23BFD4, 7)]),
    'Castelia City': ([],
                       [(0x23BF91, 3)]),
    'Castelia Gym': ([(0x23BF38, 2), (0x23BF38, 3), (0x23BFF2, 0), (0x23BFF2, 2)],
                      []),
    'Celestial Tower': ([(0x23BFE8, 2), (0x23BFE8, 3), (0x23BFE8, 4), (0x23BFE8, 5), (0x23BFEA, 6), (0x23BFEA, 7), (0x23BFEC, 4), (0x23BFF1, 2), (0x23BFFA, 3), (0x23BFFA, 4), (0x23BFFB, 1)],
                         [(0x23BFC1, 3), (0x23BFC1, 4), (0x23BFC1, 5), (0x23BFC6, 0), (0x23BFC6, 1)]),
    "Challenger's Cave": ([(0x23BFF9, 7), (0x23BFFA, 0), (0x23BFFA, 1), (0x23BFFA, 2), (0x23C021, 6)],
                           [(0x23BFA3, 1), (0x23BFA3, 2), (0x23BFA3, 3), (0x23BFA3, 4), (0x23BFA8, 6), (0x23BFA8, 7), (0x23BFA9, 0), (0x23BFC7, 0), (0x23BFC7, 2), (0x23BFC7, 4), (0x23BFC7, 6)]),
    'Chargestone Cave': ([(0x23BFE6, 0), (0x23BFE6, 1), (0x23BFE6, 4), (0x23BFE6, 5), (0x23BFE7, 7), (0x23BFE8, 1), (0x23BFEC, 2), (0x23BFF1, 6), (0x23BFF7, 4), (0x23BFFE, 6), (0x23BFFE, 7), (0x23BFFF, 0), (0x23BFFF, 1), (0x23C000, 2), (0x23C000, 3), (0x23C025, 0)],
                          [(0x23BFA0, 0), (0x23BFA0, 1), (0x23BFA0, 2), (0x23BFA0, 3), (0x23BFAB, 0), (0x23BFAB, 1), (0x23BFAB, 2), (0x23BFB6, 1), (0x23BFB6, 2), (0x23BFB6, 3), (0x23BFB6, 4), (0x23BFB6, 5), (0x23BFB6, 6), (0x23BFBA, 4), (0x23BFD7, 1), (0x23BFD7, 2), (0x23BFD7, 3), (0x23BFD7, 4)]),
    'Cold Storage': ([(0x23BFE2, 4), (0x23BFE2, 5), (0x23BFE2, 6), (0x23BFE2, 7), (0x23BFE3, 0), (0x23BFE3, 1), (0x23BFEB, 0), (0x23BFEB, 1)],
                      [(0x23BF9F, 1), (0x23BFAD, 4), (0x23BFAD, 5), (0x23BFB5, 7), (0x23BFB6, 0), (0x23BFB9, 7), (0x23BFBA, 0), (0x23BFBD, 1), (0x23BFBD, 2), (0x23BFC4, 5), (0x23BFD7, 0)]),
    'Desert Resort': ([(0x23BFF6, 5), (0x23BFF6, 6), (0x23BFF6, 7), (0x23BFF7, 0), (0x23BFF7, 1), (0x23BFF7, 2), (0x23BFF7, 3), (0x23C01E, 1), (0x23C01E, 2), (0x23C026, 1)],
                       [(0x23BF9E, 4), (0x23BF9E, 5), (0x23BF9E, 6), (0x23BFA8, 5), (0x23BFB5, 5), (0x23BFB5, 6), (0x23BFB9, 1), (0x23BFB9, 2), (0x23BFB9, 3), (0x23BFC4, 3), (0x23BFC4, 4)]),
    'Dragonspiral Tower': ([(0x23BFFF, 2), (0x23BFFF, 3), (0x23BFFF, 4), (0x23C000, 4), (0x23C026, 0)],
                            [(0x23BFBC, 0), (0x23BFC0, 1), (0x23BFC2, 5), (0x23BFC6, 6), (0x23BFC7, 3), (0x23BFC7, 5), (0x23BFC7, 7), (0x23BFC8, 0), (0x23BFD8, 2), (0x23BFD8, 3)]),
    'Dreamyard': ([(0x23BFDA, 3), (0x23BFDA, 4), (0x23C00D, 5), (0x23C00D, 6), (0x23C00D, 7), (0x23C00E, 0), (0x23C00E, 2), (0x23C00E, 3), (0x23C00E, 4)],
                   [(0x23BF98, 6), (0x23BF99, 2), (0x23BF99, 3), (0x23BFA8, 3), (0x23BFB2, 7), (0x23BFB3, 0), (0x23BFB3, 1), (0x23BFB7, 2), (0x23BFB7, 3), (0x23BFB7, 4), (0x23BFD6, 5), (0x23BFD7, 7)]),
    'Driftveil City': ([],
                        [(0x23BFAC, 1), (0x23BFC1, 7), (0x23BFC2, 0), (0x23BFC2, 1)]),
    'Driftveil Gym': ([(0x23BFE5, 3), (0x23BFEE, 4), (0x23BFF2, 5), (0x23BFF2, 6), (0x23BFF2, 7)],
                       []),
    'Football Stadium': ([(0x23C002, 5), (0x23C003, 0), (0x23C003, 1), (0x23C004, 0), (0x23C005, 3)],
                          []),
    'Giant Chasm': ([],
                     [(0x23BFAA, 4), (0x23BFAA, 5), (0x23BFC8, 2), (0x23BFC8, 3), (0x23BFC8, 4), (0x23BFD3, 5), (0x23BFD3, 6), (0x23BFD3, 7), (0x23BFD4, 0), (0x23BFD4, 1), (0x23BFD4, 2), (0x23BFD4, 3), (0x23BFD4, 4)]),
    'Icirrus City': ([],
                      [(0x23BFA2, 1), (0x23BFAD, 7), (0x23BFAE, 0), (0x23BFCD, 6)]),
    'Icirrus Gym': ([(0x23BFF4, 0), (0x23BFF4, 1), (0x23BFF4, 2), (0x23BFF4, 3), (0x23BFF4, 4), (0x23BFF4, 5)],
                     []),
    'Lacunosa Town': ([],
                       [(0x23BFA5, 1), (0x23BFA5, 2)]),
    'Lostlorn Forest': ([],
                         [(0x23BFAD, 6), (0x23BFC3, 2), (0x23BFD5, 7)]),
    'Mistralton Cave': ([(0x23BFF9, 3), (0x23BFF9, 4)],
                         [(0x23BFAB, 5), (0x23BFAB, 6), (0x23BFAB, 7), (0x23BFAD, 2), (0x23BFC4, 6), (0x23BFC4, 7), (0x23BFC5, 2), (0x23BFC5, 3), (0x23BFC5, 4), (0x23BFC5, 5), (0x23BFC5, 6)]),
    'Mistralton City': ([],
                         [(0x23BFA0, 4), (0x23BFA0, 5), (0x23BFA0, 6), (0x23BFC5, 7)]),
    'Mistralton Gym': ([(0x23BFE2, 2), (0x23BFE2, 3), (0x23BFE9, 1), (0x23BFE9, 3), (0x23BFE9, 4)],
                        []),
    'Moor of Icirrus': ([(0x23C022, 2), (0x23C022, 3), (0x23C022, 4)],
                         [(0x23BFA9, 5), (0x23BFA9, 6), (0x23BFA9, 7), (0x23BFCA, 7), (0x23BFCB, 3), (0x23BFCB, 7), (0x23BFCC, 2), (0x23BFCC, 3)]),
    "N's Castle": ([],
                    [(0x23BFD5, 6), (0x23BFD6, 3), (0x23BFD7, 5)]),
    "N's Room": ([],
                  [(0x23BFD8, 1)]),
    'Nacrene City': ([],
                      [(0x23BF99, 1), (0x23BF9D, 4), (0x23BF9D, 5)]),
    'Nacrene Gym': ([(0x23BF38, 0), (0x23BF38, 1), (0x23BFE4, 2)],
                     []),
    'Nimbasa Gym': ([(0x23BFE1, 6), (0x23BFE2, 0)],
                     []),
    'Opelucid City': ([],
                       [(0x23BFA3, 0)]),
    'Opelucid Gym': ([(0x23BFFA, 5), (0x23BFFA, 6), (0x23BFFA, 7), (0x23BFFB, 2), (0x23BFFB, 3), (0x23BFFB, 4), (0x23BFFB, 6), (0x23BFFB, 7)],
                      []),
    'P2 Laboratory': ([(0x23C00E, 1)],
                       [(0x23BFC0, 6), (0x23BFD6, 0)]),
    'Pinwheel Forest': ([(0x23BFDC, 6), (0x23BFDC, 7), (0x23BFDD, 0), (0x23BFDD, 1), (0x23BFDD, 2), (0x23BFDD, 3), (0x23BFDD, 4), (0x23BFDD, 5), (0x23BFDD, 6), (0x23BFE7, 3), (0x23BFEB, 4), (0x23BFEB, 5), (0x23BFED, 4), (0x23C018, 1), (0x23C018, 2), (0x23C01D, 5)],
                         [(0x23BF99, 4), (0x23BF9E, 0), (0x23BFB5, 0), (0x23BFB5, 1), (0x23BFB5, 2), (0x23BFB5, 3), (0x23BFB5, 4), (0x23BFB7, 7), (0x23BFB8, 0), (0x23BFB8, 1), (0x23BFB8, 2), (0x23BFBF, 6), (0x23BFC3, 5), (0x23BFC3, 7), (0x23BFCE, 0), (0x23BFD6, 7)]),
    'Relic Castle': ([(0x23BFDF, 7), (0x23BFE0, 0), (0x23BFF5, 1), (0x23BFF5, 2), (0x23BFF5, 3), (0x23BFF5, 4), (0x23BFF5, 5), (0x23BFF5, 6), (0x23BFF5, 7)],
                      [(0x23BFB4, 1), (0x23BFB8, 4), (0x23BFB9, 4), (0x23BFB9, 5), (0x23BFB9, 6), (0x23BFBA, 5), (0x23BFBD, 0)]),
    'Route 1': ([(0x23C01B, 7), (0x23C01C, 0), (0x23C01C, 1)],
                 [(0x23BFB6, 7), (0x23BFC1, 6)]),
    'Route 10': ([(0x23BFE5, 7), (0x23BFE6, 3), (0x23BFE7, 0), (0x23BFED, 2), (0x23BFEF, 6), (0x23BFEF, 7), (0x23BFF1, 5)],
                  [(0x23BF9F, 5), (0x23BFBC, 5), (0x23BFBC, 6), (0x23BFBC, 7), (0x23BFC8, 1), (0x23BFD5, 1)]),
    'Route 11': ([(0x23C010, 1), (0x23C010, 4), (0x23C012, 1), (0x23C012, 3)],
                  [(0x23BFA4, 4), (0x23BFA8, 4), (0x23BFAA, 6), (0x23BFBE, 1), (0x23BFBE, 2), (0x23BFBE, 3)]),
    'Route 12': ([(0x23C00E, 7), (0x23C00F, 0), (0x23C011, 4), (0x23C011, 7), (0x23C012, 0)],
                  [(0x23BFA4, 5), (0x23BFA4, 6), (0x23BFA5, 0), (0x23BFBE, 4), (0x23BFBE, 5), (0x23BFBE, 6)]),
    'Route 13': ([(0x23C00D, 2), (0x23C00D, 4), (0x23C00E, 5), (0x23C00E, 6), (0x23C00F, 2), (0x23C00F, 5), (0x23C010, 0), (0x23C011, 2), (0x23C011, 5), (0x23C012, 5)],
                  [(0x23BFA5, 3), (0x23BFA5, 4), (0x23BFA5, 5), (0x23BFA5, 6), (0x23BFA5, 7), (0x23BFA6, 0), (0x23BFAC, 0), (0x23BFBE, 0), (0x23BFBE, 7), (0x23BFBF, 0), (0x23BFBF, 1), (0x23BFBF, 2), (0x23BFD4, 5)]),
    'Route 14': ([(0x23C00C, 6), (0x23C00C, 7), (0x23C00D, 3), (0x23C00F, 3), (0x23C012, 6), (0x23C021, 5)],
                  [(0x23BFBF, 4), (0x23BFBF, 5)]),
    'Route 15': ([(0x23C00F, 1), (0x23C011, 0), (0x23C012, 2), (0x23C012, 4), (0x23C012, 7)],
                  [(0x23BFA6, 7), (0x23BFA9, 1), (0x23BFBF, 7), (0x23BFC0, 0)]),
    'Route 16': ([(0x23C00C, 4), (0x23C00C, 5), (0x23C00D, 0), (0x23C010, 2), (0x23C010, 6), (0x23C010, 7)],
                  [(0x23BFC0, 2), (0x23BFC0, 3), (0x23BFD6, 1)]),
    'Route 17': ([(0x23C00A, 1), (0x23C00A, 2), (0x23C00D, 1), (0x23C00F, 4), (0x23C011, 3)],
                  [(0x23BFA7, 0), (0x23BFA7, 1), (0x23BFA7, 3), (0x23BFA9, 3), (0x23BFC0, 4), (0x23BFC0, 5)]),
    'Route 18': ([(0x23C010, 3), (0x23C010, 5), (0x23C011, 1), (0x23C011, 6), (0x23C013, 0)],
                  [(0x23BFA7, 2), (0x23BFC0, 7), (0x23BFC1, 0), (0x23BFC1, 1), (0x23BFC1, 2), (0x23BFD2, 6)]),
    'Route 2': ([(0x23BFD9, 5), (0x23BFD9, 6), (0x23BFE4, 1)],
                 [(0x23BFB2, 2), (0x23BFB2, 3), (0x23BFB2, 4), (0x23BFB2, 5), (0x23BFB2, 6), (0x23BFB3, 2)]),
    'Route 3': ([(0x23BFD9, 7), (0x23BFDA, 0), (0x23BFDB, 2), (0x23BFDB, 3), (0x23BFDB, 4), (0x23BFDB, 5), (0x23BFDB, 7), (0x23BFDC, 0), (0x23BFE4, 0), (0x23BFFE, 0)],
                 [(0x23BF98, 7), (0x23BF99, 0), (0x23BFB3, 6), (0x23BFB3, 7), (0x23BFB4, 0), (0x23BFB7, 0), (0x23BFB7, 1), (0x23BFB7, 5), (0x23BFB7, 6), (0x23BFD6, 6)]),
    'Route 4': ([(0x23BFDD, 7), (0x23BFDE, 0), (0x23BFDE, 1), (0x23BFDE, 3), (0x23BFDE, 4), (0x23BFDE, 5), (0x23BFDE, 6), (0x23BFEC, 5), (0x23BFED, 0), (0x23BFFD, 6), (0x23BFFD, 7), (0x23C018, 5)],
                 [(0x23BF9E, 3), (0x23BFAC, 2), (0x23BFAC, 3), (0x23BFAE, 4), (0x23BFB4, 2), (0x23BFB8, 3), (0x23BFB8, 6), (0x23BFB8, 7), (0x23BFB9, 0), (0x23BFC4, 0), (0x23BFC4, 2)]),
    'Route 5': ([(0x23BFDF, 0), (0x23BFDF, 1), (0x23BFDF, 3), (0x23BFDF, 4), (0x23BFDF, 5), (0x23BFDF, 6)],
                 [(0x23BFB3, 3), (0x23BFB3, 4), (0x23BFB3, 5), (0x23BFC4, 1)]),
    'Route 6': ([(0x23BFE7, 4), (0x23BFED, 5), (0x23BFED, 6), (0x23BFF0, 2), (0x23BFF0, 6), (0x23BFF9, 5), (0x23BFF9, 6)],
                 [(0x23BF9F, 2), (0x23BF9F, 3), (0x23BF9F, 4), (0x23BFBA, 1), (0x23BFBA, 2), (0x23BFBA, 3), (0x23BFC2, 2), (0x23BFC2, 3)]),
    'Route 7': ([(0x23BFEB, 2), (0x23BFEB, 3), (0x23BFEC, 6), (0x23BFEC, 7), (0x23BFF0, 3), (0x23BFF0, 7), (0x23C018, 3), (0x23C018, 4)],
                 [(0x23BFBA, 6), (0x23BFBA, 7), (0x23BFBB, 0), (0x23BFBB, 1)]),
    'Route 8': ([(0x23BFEC, 0), (0x23BFED, 7), (0x23BFEE, 0), (0x23BFF0, 4), (0x23BFF1, 0)],
                 [(0x23BFA2, 4), (0x23BFAD, 3), (0x23BFBC, 1), (0x23BFBC, 2), (0x23BFC6, 4), (0x23BFD8, 0)]),
    'Route 9': ([(0x23BFEA, 2), (0x23BFEA, 3), (0x23BFED, 1), (0x23BFF0, 0), (0x23BFF0, 1)],
                 [(0x23BFA2, 5), (0x23BFA2, 6), (0x23BFBC, 3), (0x23BFBC, 4)]),
    'Shopping Mall Nine': ([(0x23BFE5, 4), (0x23BFE6, 7)],
                            []),
    'Striaton City': ([],
                       [(0x23BFC5, 0), (0x23BFD2, 5)]),
    'Striaton Gym': ([(0x23BFDA, 5), (0x23BFDA, 6)],
                      []),
    'Tennis Court': ([(0x23C000, 6), (0x23C001, 1), (0x23C001, 2), (0x23C004, 2), (0x23C005, 4), (0x23C007, 4), (0x23C00B, 3)],
                      []),
    'Twist Mountain': ([(0x23BFDE, 2), (0x23BFE7, 2), (0x23BFE8, 6), (0x23BFE8, 7), (0x23BFE9, 0), (0x23BFEC, 3), (0x23BFED, 3), (0x23BFF1, 7), (0x23BFF7, 5), (0x23BFF7, 6), (0x23BFF7, 7), (0x23C01A, 2)],
                        [(0x23BFA0, 7), (0x23BFA1, 2), (0x23BFA1, 3), (0x23BFA1, 4), (0x23BFA1, 5), (0x23BFA1, 7), (0x23BFA2, 0), (0x23BFBB, 2), (0x23BFBB, 3), (0x23BFBB, 4), (0x23BFBB, 5), (0x23BFBB, 7), (0x23BFBD, 3), (0x23BFC2, 4), (0x23BFC6, 3), (0x23BFC8, 5)]),
    'Undella Bay': ([(0x23C020, 4), (0x23C020, 5), (0x23C020, 6), (0x23C020, 7), (0x23C021, 0), (0x23C021, 1)],
                     [(0x23BFA6, 1), (0x23BFA6, 2), (0x23BFA6, 3)]),
    'Undella Town': ([],
                      [(0x23BFCC, 5)]),
    'Victory Road': ([(0x23BF54, 1), (0x23BFF8, 0), (0x23BFF8, 1), (0x23BFF8, 2), (0x23BFF8, 3), (0x23BFF8, 4), (0x23BFF8, 5), (0x23BFF8, 6), (0x23BFF8, 7)],
                      [(0x23BFA3, 5), (0x23BFA3, 6), (0x23BFA4, 1), (0x23BFA4, 2), (0x23BFA4, 3), (0x23BFB4, 3), (0x23BFB4, 4), (0x23BFB4, 5), (0x23BFB4, 6), (0x23BFB4, 7), (0x23BFBD, 4), (0x23BFBD, 5), (0x23BFBD, 6), (0x23BFBD, 7), (0x23BFD5, 4)]),
    'Village Bridge': ([(0x23C021, 7), (0x23C022, 0)],
                        [(0x23BFAE, 1), (0x23BFAE, 2), (0x23BFD6, 2), (0x23BFD6, 4)]),
    'Wellspring Cave': ([(0x23BFF9, 0), (0x23BFF9, 1), (0x23BFF9, 2)],
                         [(0x23BFA7, 6), (0x23BFA9, 4), (0x23BFAC, 5), (0x23BFAC, 6), (0x23BFAC, 7), (0x23BFAD, 0), (0x23BFC2, 6), (0x23BFC2, 7), (0x23BFC3, 0), (0x23BFC3, 3), (0x23BFC3, 4)]),
}
ROUTE_FLAGS_START, ROUTE_FLAGS_END = 0x23BF38, 0x23C027   # the bytes they live in


def route_stats(place, flag_bytes):
    """{'trainers': (beaten, known), 'items': (found, known)} for a place,
    from the flag bytes read from ROUTE_FLAGS_START; {} for a place with
    none known."""
    entry = ROUTE_FLAGS.get(place)
    if not entry or len(flag_bytes) < ROUTE_FLAGS_END - ROUTE_FLAGS_START:
        return {}
    out = {}
    for key, flags in zip(('trainers', 'items'), entry):
        if flags:
            done = sum(1 for addr, bit in flags if flag_bytes[addr - ROUTE_FLAGS_START] >> bit & 1)
            out[key] = (done, len(flags))
    return out


# The Battle Subway (White's notes, Black's 0x20 lower): the current and
# record streaks per train (u16), the Battle Points, and which train you're
# on (a u8 by the battle code: 0 single, 1 double, 2 multi, 5-7 super).
SUBWAY_PLACES = ('Gear Station', 'Battle Subway')
SUBWAY_TRAINS = ['Single', 'Double', 'Multi', 'Multi (friend)', None, 'Super Single', 'Super Double', 'Super Multi']
SUBWAY_MODES = {0: 0, 1: 1, 2: 2, 5: 5, 6: 6, 7: 7}       # mode byte -> train index above
INSTITUTE_PLACES = ('Battle Institute',)
INSTITUTE_RANKS = [(6000, 'Master'), (5000, 'Elite'), (4000, 'Hyper'), (3000, 'Super'), (2000, 'Normal'),
                   (1000, 'Novice'), (0, 'Beginner')]


def institute_rank(points):
    return next(name for floor, name in INSTITUTE_RANKS if points >= floor)


# The League: the Elite Four you've beaten this challenge (bits 1-4 of a
# byte, White's notes; assumed in room order), shown only in their rooms.
LEAGUE_ROOMS = set(ELITE_ROOMS) | {CHAMPION_ROOM}
ELITE_ORDER = [ELITE_ROOMS[z] for z in sorted(ELITE_ROOMS)]   # Shauntal, Grimsley, Marshal, Caitlin

# A badge's shine (u32 each, 0x23F polished; White's notes): which row of
# the trainer card's badge art to show.
SHINE_MAX = 0x23F


def shine_row(value):
    """0 dull, 1 clean, 2 polished (unova_art's badge rows)."""
    return 2 if value >= 0x200 else 1 if value >= 0x100 else 0


CATCH_MUSIC = 0x518       # plays when a wild Pokemon is caught
LOW_HP_MUSIC = 0x47A      # your Pokemon's HP is low


# The field's weather (a u8 next to the season) -> the battle view's weather
# particles (overlay/backdrop.py).
WEATHER = {0: None, 1: 'snow', 2: 'rain', 3: 'sand', 4: 'heavy_snow', 5: 'hail', 6: 'storm', 7: 'heavy_rain',
           8: 'snow', 9: 'fog'}

# Times of day by season: the hour morning, day, evening and night start.
# Black and White's days are longer in summer and shorter in winter.
_DAY_STARTS = {'spring': (5, 10, 17, 20), 'summer': (4, 9, 19, 21), 'autumn': (6, 10, 17, 20),
               'winter': (7, 11, 17, 19)}


def time_of_day(clock, season=None):
    """'morning', 'day', 'evening' or 'night' for a clock ('YYYY-MM-DD HH:MM')
    in a season."""
    try:
        hour = int(clock.split(' ')[1].split(':')[0])
    except (AttributeError, IndexError, ValueError):
        return 'day'
    morning, day, evening, night = _DAY_STARTS.get(season, _DAY_STARTS['spring'])
    if morning <= hour < day:
        return 'morning'
    if day <= hour < evening:
        return 'day'
    if evening <= hour < night:
        return 'evening'
    return 'night'


# Where battles happen, by words in the place's name: (sky, platform) for
# overlay/unova_art.py. Outdoors in winter is snowy where the game puts snow.
_TERRAIN_WORDS = [
    (('cave', 'chargestone', 'twist mountain', 'victory road', 'challenger', 'giant chasm', 'relic castle',
      'wellspring', 'mistralton cave'), ('cave', 'cave')),
    (('gym', 'center', 'mart', 'house', 'lab', 'tower', 'castle', 'league', 'subway', 'station', 'theater',
      'building', 'cold storage', 'mall', 'chamber', 'museum', 'hotel', 'room', 'gate', 'institute'), ('indoor', 'indoor')),
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
