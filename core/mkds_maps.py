"""
mkds_maps.py - where Mario Kart DS's course art (Assets/MarioKartDS) has
the game's world: written by tools/mkds_maps.py from the courses'
checkpoints in the game's own files (see there). Don't edit it by hand:
change the tool's OVERRIDES and run it again.

MAPS: course file (core/mkds_reader.py's COURSES) -> (the map's name in
its file name, the part of the sheet that's the map (left, top, right,
bottom), world units a pixel k, the world's origin in that part (ox, oy),
and the middle of checkpoint 0 (the finish line) in the course file).
A point (x, z) in the world is at (ox + x / k, oy + z / k) in the map. The
overlay checks the checkpoint the console has against the last, so a
course the console has otherwise (mirrored, say) isn't drawn on the
wrong map.
"""

ART = "DS _ DSi - Mario Kart DS - Courses - {} Map.png"

MAPS = {
    'old_yoshi_gc': ('GCN Yoshi Circuit', (0, 0, 512, 512), 12.000, 254.6, 194.0, (385, 3342)),
    'old_baby_gc': ('GCN Baby Park', (0, 0, 512, 512), 13.654, 240.0, 252.6, (-275, -20)),
    'old_mario_sfc': ('SNES Mario Circuit 1', (0, 0, 512, 512), 12.500, 333.0, 263.0, (562, 128)),
    'old_momo_64': ('N64 Moo Moo Farm', (0, 0, 512, 509), 11.863, 258.8, 251.0, (-660, -1375)),
    'old_koopa_agb': ('GBA Bowser Castle 2', (0, 0, 512, 511), 11.433, 257.6, 252.0, (-2112, -710)),
    'old_peach_agb': ('GBA Peach Circuit', (0, 0, 512, 512), 12.200, 252.8, 259.9, (95, -934)),
    'old_luigi_gc': ('GCN Luigi Circuit', (0, 0, 512, 1023), 11.667, 256.8, 513.9, (1096, 1674)),
    'old_noko_sfc': ('SNES Koopa Beach 2', (0, 0, 512, 512), 10.762, 260.2, 264.5, (962, -585)),
    'old_frappe_64': ('N64 Frappe Snowland', (0, 0, 512, 511), 11.812, 254.8, 253.1, (250, 350)),
    'clock_course': ('Tick-Tock Clock', (0, 0, 512, 512), 12.246, 314.7, 256.6, (-1180, 2738)),
    'mansion_course': ("Luigi's Mansion", (0, 0, 512, 1024), 12.458, 188.0, 585.7, (2400, 1180)),
    'airship_course': ('Airship Fortress', (0, 518, 520, 1036), 13.680, 259.9, 542.7, (725, -2575)),
    'cross_course': ('Figure-8 Circuit', (0, 0, 1024, 511), 12.133, 504.5, 240.2, (-75, 0)),
    'bank_course': ('Yoshi Falls', (0, 0, 512, 512), 12.346, 288.3, 255.6, (-695, 955)),
    'old_hyudoro_64': ('N64 Banshee Boardwalk', (0, 0, 512, 512), 11.675, 255.5, 260.2, (2445, 320)),
    'ridge_course': ('Shroom Ridge', (0, 0, 512, 510), 11.567, 299.1, 185.0, (134, 679)),
    'mario_course': ('Mario Circuit', (521, 22, 1034, 535), 13.363, 229.5, 255.0, (1485, -1575)),
    'garden_course': ('Peach Gardens', (0, 0, 512, 512), 11.850, 262.0, 251.0, (-5, -1615)),
    'desert_course': ('Desert Hills', (0, 0, 512, 512), 11.500, 256.3, 194.2, (1300, 835)),
    'town_course': ('Delfino Square', (0, 0, 1024, 512), 12.475, 522.1, 300.8, (-2100, 865)),
    'rainbow_course': ('Rainbow Road', (0, 0, 512, 512), 11.662, 255.5, 253.0, (-1712, 798)),
    'snow_course': ('DK Pass', (0, 0, 512, 1024), 11.817, 187.8, 503.9, (-1025, 1835)),
    'beach_course': ('Cheep-Cheep Beach', (0, 0, 512, 510), 12.612, 263.6, 245.2, (-1725, -470)),
    'koopa_course': ('Bowser Castle', (0, 0, 512, 512), 11.875, 252.8, 254.1, (-750, 1460)),
    'pinball_course': ('Waluigi Pinball', (0, 0, 512, 1023), 11.875, 256.0, 513.8, (1330, 3780)),
    'stadium_course': ('Wario Stadium', (0, 0, 512, 512), 11.930, 372.4, 168.9, (-1265, 190)),
    'old_donut_sfc': ('SNES Donut Plains 1', (0, 0, 512, 512), 12.525, 260.8, 261.8, (-1250, 0)),
    'old_choco_64': ('N64 Choco Mountain', (0, 0, 512, 512), 11.938, 254.6, 252.5, (-950, -988)),
    'old_luigi_agb': ('GBA Luigi Circuit', (0, 0, 512, 512), 11.913, 251.0, 256.2, (-1881, 75)),
    'old_kinoko_gc': ('GCN Mushroom Bridge', (0, 0, 1024, 512), 12.104, 512.5, 257.8, (2281, 1275)),
    'old_choco_sfc': ('SNES Choco Island 2', (0, 0, 512, 512), 12.717, 248.0, 251.2, (-1180, 436)),
    'old_sky_agb': ('GBA Sky Garden', (0, 0, 511, 512), 10.342, 256.6, 255.2, (1595, -840)),
}
