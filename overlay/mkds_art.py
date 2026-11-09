"""
mkds_art.py - Mario Kart DS's art for the overlay's race view (overlay/mkds.py),
cut at runtime from the sheets in Assets/MarioKartDS (the Spriters Resource's
rips), so the sheets stay the only image files:

    heads     the racers' heads from the bottom screen's map (HUD Elements,
              Character Map Markers: 16x14 each, a 4x5 grid)
    items     the items: the game's own 32x32 textures (Items.gif: shown 1:1 at
              the window's resolution, half size in canvas pixels) where it
              has the whole item, else the bottom screen's (HUD Elements,
              Items (Bottom Screen), 1:1 on the canvas), with its x2 and x3
              versions, or its xN badge on an item it hasn't with that count
    maps      a course's map from above (Courses - <name> Map), the part of
              it the view shows, scaled to the view's size; where it sits in
              the game's world comes from core/mkds_maps.py; past the map's
              edge its edge colour carries on

Sheets load the first time something's asked for (pygame needs its display
first) and every piece is cached, scaled maps by the size they were scaled
to. A sheet missing from Assets/ (a release download doesn't include them) is
fetched from GitHub Pages in the background, as overlay/unova_art.py does;
until it's there, or if it can't be had, pieces come back as None and the
view draws without them (coloured dots, and the course as a line).
"""

import logging
import os
import threading

import pygame

from core.mkds_maps import ART as MAP_ART
from core.mkds_maps import MAPS
from .sprites import _download

FOLDER = 'MarioKartDS'
MARKERS = 'DS _ DSi - Mario Kart DS - HUD Elements (In-Game) - Character Map Markers.png'
HEAD_W, HEAD_H = 16, 14
# The markers sheet's grid, by core/mkds_reader.py's character names (the
# rows after these are the Shy Guys: red, green, blue, yellow, black, light
# blue, pink, white)
HEADS = ["Mario", "Luigi", "Peach", "Toad", "Yoshi", "Donkey Kong", "Wario", "Bowser",
         "Daisy", "Dry Bones", "Waluigi", "R.O.B.", "Shy Guy"]
HEAD_COLUMNS = 4
ITEM_SHEET = 'DS _ DSi - Mario Kart DS - HUD Elements (In-Game) - Items (Bottom Screen).png'
ITEM_KEY = (8, 100, 105)          # the sheet's background
# Each item's place on the sheet (x, y, w, h), and (name, how many) for the
# ones it also has with a count on them; triples are their single item's
ITEM_ICONS = {
    "Banana": (16, 7, 14, 13), "Mushroom": (32, 8, 12, 12), ("Mushroom", 2): (45, 7, 15, 13),
    ("Mushroom", 3): (61, 7, 15, 13), "Golden Mushroom": (77, 7, 12, 14), ("Banana", 3): (16, 21, 15, 14),
    "Green Shell": (32, 23, 14, 12), ("Green Shell", 3): (47, 22, 15, 13), "Red Shell": (63, 23, 14, 12),
    ("Red Shell", 3): (78, 22, 15, 13), "Spiny Shell": (94, 20, 16, 15), "Blooper": (17, 37, 13, 14),
    "Bob-omb": (33, 36, 12, 15), "Star": (47, 39, 13, 12), "Boo": (63, 38, 15, 13), "Bullet Bill": (79, 39, 15, 11),
    "Lightning": (96, 37, 13, 13),
}
TRIPLES = {"Triple Mushrooms": "Mushroom", "Triple Green Shells": "Green Shell", "Triple Bananas": "Banana",
           "Triple Red Shells": "Red Shell"}
# Items.gif: the game's textures of the items, 32x32 each on a background colour of its own (its
# corner's), in a row: tile number -> item (the ones that are a whole item; its Mushroom and
# Blooper are half a model's texture each and its Boo's 64x64, so those come from the bottom
# screen's sheet)
GIF_SHEET = 'Items.gif'
GIF_ITEMS = {"Banana": 2, "Bob-omb": 3, "Golden Mushroom": 7, "Green Shell": 8, "Red Shell": 9, "Star": 10,
             "Lightning": 12, "Spiny Shell": 14, "Fake Item Box": 15, "Bullet Bill": 16}

# The sheet's own count badges (the dark red box with x2 or x3 in the bottom right): cut from the
# mushroom with one (the pixels it doesn't share with the plain mushroom), for the items the sheet
# hasn't with that count (two shells, two bananas)
BADGES = {2: ("Mushroom", 2), 3: ("Mushroom", 3)}
# The Fake Item Box when neither sheet's here: a ? box in the sheets' reds and white (13x13)
FAKE_BOX = [
    "..ooooooooo..",
    ".ollllllllro.",
    "olmmmmmmmmmro",
    "olmmmwwwmmmro",
    "olmmwmmmwmmro",
    "olmmmmmmwmmro",
    "olmmmmmwmmmro",
    "olmmmmwmmmmro",
    "olmmmmmmmmmro",
    "olmmmmwmmmmro",
    "olmmmmmmmmmro",
    ".orrrrrrrrro.",
    "..ooooooooo..",
]
FAKE_COLOURS = {'o': (0x69, 0x10, 0x08), 'r': (0xb2, 0x08, 0x08), 'm': (0xdb, 0x30, 0x20),
                'l': (0xdb, 0x61, 0x41), 'w': (0xfb, 0xfb, 0xfb)}


class MkdsArt:
    def __init__(self, assets_dir):
        self.folder = os.path.join(assets_dir, FOLDER)
        self._sheets = {}
        self._cache = {}
        self._fetching = set()

    def _sheet(self, name):
        if name not in self._sheets:
            path = os.path.join(self.folder, name)
            if not os.path.exists(path):
                self._fetch(name, path)
                return None
            try:
                self._sheets[name] = pygame.image.load(path).convert_alpha()
            except (pygame.error, OSError) as e:
                logging.warning(f"Mario Kart DS art missing ({name}): {e}")
                self._sheets[name] = None
        return self._sheets[name]

    def _fetch(self, name, path):
        if name in self._fetching:
            return
        self._fetching.add(name)

        def run():
            if not _download(f"{FOLDER}/{name}", path):
                logging.warning(f"Mario Kart DS art missing ({name}): not in {self.folder}, and it couldn't be downloaded")
                self._sheets[name] = None
            self._fetching.discard(name)
        threading.Thread(target=run, name="mkds-art", daemon=True).start()

    def _get(self, key, make):
        if key not in self._cache:
            try:
                piece = make()
            except Exception:
                logging.exception(f"Couldn't cut {key} from the Mario Kart DS sheets")
                piece = None
            if piece is None and self._fetching:
                return None   # (a sheet may still be on its way: asked again then)
            self._cache[key] = piece
        return self._cache[key]

    def pending(self):
        return bool(self._fetching)

    def head(self, character):
        """A racer's head (16x14), or None (not a character we know)."""
        if character not in HEADS:
            return None

        def make():
            sheet = self._sheet(MARKERS)
            if sheet is None:
                return None
            i = HEADS.index(character)
            piece = pygame.Surface((HEAD_W, HEAD_H), pygame.SRCALPHA)
            piece.blit(sheet, (0, 0), (i % HEAD_COLUMNS * HEAD_W, i // HEAD_COLUMNS * HEAD_H, HEAD_W, HEAD_H))
            return piece
        return self._get(('head', character), make)

    def _cut_item(self, key):
        """An icon from the items sheet, its background see-through, its pixels as they are."""
        sheet = self._sheet(ITEM_SHEET)
        if sheet is None:
            return None
        rect = ITEM_ICONS[key]
        piece = pygame.Surface(rect[2:], pygame.SRCALPHA)
        piece.blit(sheet, (0, 0), rect)
        for y in range(piece.get_height()):
            for x in range(piece.get_width()):
                if piece.get_at((x, y))[:3] == ITEM_KEY:
                    piece.set_at((x, y), (0, 0, 0, 0))
        return piece

    def _badge(self, count):
        """[(dx, dy, colour)] of the sheet's xN badge, from the icon's bottom right."""
        def make():
            with_badge, plain = self._cut_item(BADGES[count]), self._cut_item("Mushroom")
            if with_badge is None or plain is None:
                return None
            w, h = with_badge.get_size()
            out = []
            for y in range(h):
                for x in range(w):
                    c = with_badge.get_at((x, y))
                    same = (x < plain.get_width() and y < plain.get_height() and plain.get_at((x, y)) == c)
                    if c.a and not same:
                        out.append((x - w, y - h, tuple(c)))
            return out
        return self._get(('badge', count), make)

    def _gif_tiles(self):
        """Items.gif's tiles, [(x, y, w, h)], left to right: the runs of
        columns with anything in them (the file's see-through between)."""
        def make():
            sheet = self._sheet(GIF_SHEET)
            if sheet is None:
                return None
            w, h = sheet.get_size()
            used = [any(sheet.get_at((x, y)).a for y in range(h)) for x in range(w)]
            tiles, x = [], 0
            while x < w:
                if not used[x]:
                    x += 1
                    continue
                x0 = x
                while x < w and used[x]:
                    x += 1
                rows = [y for y in range(h) if any(sheet.get_at((c, y)).a for c in range(x0, x))]
                tiles.append((x0, rows[0], x - x0, rows[-1] - rows[0] + 1))
            return tiles
        return self._get(('gif', 'tiles'), make)

    def _gif_item(self, name):
        """The item's texture from Items.gif, its background (the tile's
        corner colour, where it reaches from the edges) see-through, trimmed
        to what's left; None when the file isn't here."""
        def make():
            tiles = self._gif_tiles()
            sheet = self._sheet(GIF_SHEET)
            if not tiles or sheet is None or GIF_ITEMS[name] >= len(tiles):
                return None
            tile = pygame.Surface(tiles[GIF_ITEMS[name]][2:], pygame.SRCALPHA)
            tile.blit(sheet, (0, 0), tiles[GIF_ITEMS[name]])
            w, h = tile.get_size()
            bg = tile.get_at((0, 0))
            todo = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
            while todo:                                  # (from the edges in: a colour like it inside stays)
                x, y = todo.pop()
                if 0 <= x < w and 0 <= y < h and tile.get_at((x, y)) == bg:
                    tile.set_at((x, y), (0, 0, 0, 0))
                    todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            box = tile.get_bounding_rect()
            return tile.subsurface(box).copy() if box.w and box.h else None
        return self._get(('gif', name), make)

    def item(self, name, count=1):
        """(the item's icon, whether it shows the count already, whether it's
        at twice the canvas's pixels) for an item as core/mkds_reader.py
        names it: Items.gif's texture when it has the whole item (twice the
        canvas's pixels: drawn at half size, at the window's resolution), with
        the bottom screen's xN badge on it for a count; else the bottom
        screen's own icon (with its x2 or x3 when it has one, else its badge
        put on); FAKE_BOX when neither sheet's here; or (None, False, False)
        before they're loaded."""
        base = TRIPLES.get(name, name)
        if base in GIF_ITEMS:
            icon = self._gif_item(base)
            if icon is not None:
                if count in BADGES:
                    def make():
                        badge = self._badge(count)
                        if badge is None:
                            return None
                        w, h = icon.get_width() + 2, icon.get_height() + 2   # (the badge a pixel past it)
                        out = pygame.Surface((w, h), pygame.SRCALPHA)
                        out.blit(icon, (0, 0))
                        for dx, dy, colour in badge:   # (each of the badge's pixels a canvas pixel: 2x2 here)
                            out.fill(colour, (w + dx * 2, h + dy * 2, 2, 2))
                        return out
                    counted = self._get(('gif', base, count), make)
                    if counted is not None:
                        return counted, True, True
                return icon, False, True
        if name == "Fake Item Box":
            return self._get(('item', 'fake'), self._fake_box), False, False
        return self._sheet_item(name, base, count) + (False,)

    def _sheet_item(self, name, base, count):
        """(the bottom screen's icon, whether it shows the count already)."""
        if base not in ITEM_ICONS:
            return None, False
        if (base, count) in ITEM_ICONS:
            return self._get(('item', (base, count)), lambda: self._cut_item((base, count))), True
        if count in BADGES:
            def make():
                icon, badge = self._cut_item(base), self._badge(count)
                if icon is None or badge is None:
                    return None
                w, h = icon.get_width() + 1, icon.get_height() + 1     # (the badge sits a pixel past the icon)
                out = pygame.Surface((w, h), pygame.SRCALPHA)
                out.blit(icon, (0, 0))
                for dx, dy, colour in badge:
                    if 0 <= w + dx < w and 0 <= h + dy < h:
                        out.set_at((w + dx, h + dy), colour)
                return out
            icon = self._get(('item', (base, count)), make)
            return icon, icon is not None
        return self._get(('item', base), lambda: self._cut_item(base)), False

    @staticmethod
    def _fake_box():
        out = pygame.Surface((len(FAKE_BOX[0]), len(FAKE_BOX)), pygame.SRCALPHA)
        for y, row in enumerate(FAKE_BOX):
            for x, ch in enumerate(row):
                if ch in FAKE_COLOURS:
                    out.set_at((x, y), FAKE_COLOURS[ch])
        return out

    @staticmethod
    def calibrated(course_file):
        return course_file in MAPS

    def course_map(self, course_file, window, size, mirror=False, dim=0.0, turn=False):
        """The course's map showing `window` of the world (x0, z0, x1, z1),
        scaled to `size` (w, h) and darkened by `dim` (0-1), or None (no map
        for the course, or its sheet isn't here). The world's x runs the other
        way when `mirror` (the map's turned over to match). With `turn` the
        map's a quarter turn clockwise and `window` is (u0, v0, u1, v1) in
        the turned map, u = -z and v = x (overlay/mkds.py's turned())."""
        if course_file not in MAPS:
            return None
        key = ('map', course_file, tuple(round(v, 1) for v in window), tuple(size), mirror, dim, turn)

        def make():
            art, k, ox, oy = MAPS[course_file][:4]
            sheet = self._sheet(MAP_ART.format(art))
            if sheet is None:
                return None
            x0, z0, x1, z1 = window
            out_size = size
            if turn:                                      # (cut it as it is, then turn it)
                (u0, v0, u1, v1), out_size = window, (size[1], size[0])
                x0, z0, x1, z1 = v0, -u1, v1, -u0
            if mirror:                                    # (world x -> -x: the map read right to left)
                x0, x1 = -x1, -x0
            left, top = ox + x0 / k, oy + z0 / k
            w, h = (x1 - x0) / k, (z1 - z0) / k
            src = pygame.Surface((max(1, round(w)), max(1, round(h))))
            src.fill(sheet.get_at((2, 2))[:3])                              # (outside the map: its edge's colour)
            want = pygame.Rect(round(left), round(top), round(w), round(h))
            inside = want.clip(sheet.get_rect())
            if inside.w and inside.h:
                src.blit(sheet, (inside.x - want.x, inside.y - want.y), inside)
            if mirror:
                src = pygame.transform.flip(src, True, False)
            out = pygame.transform.scale(src, out_size)
            if turn:
                out = pygame.transform.rotate(out, -90)
            if dim:
                shade = pygame.Surface(size)
                shade.fill((0, 0, 0))
                shade.set_alpha(int(255 * dim))
                out.blit(shade, (0, 0))
            return out
        return self._get(key, make)
