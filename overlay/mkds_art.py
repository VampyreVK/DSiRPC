"""
mkds_art.py - Mario Kart DS's art for the overlay's race view (overlay/mkds.py),
cut at runtime from the sheets in Assets/MarioKartDS (the Spriters Resource's
rips), so the sheets stay the only image files:

    heads     the racers' heads from the bottom screen's map (HUD Elements,
              Character Map Markers: 16x14 each, a 4x5 grid)
    items     the items as the bottom screen shows the one you hold (HUD
              Elements, Items (Bottom Screen)), with its x2 and x3 versions
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

    def item(self, name, count=1):
        """(the item's icon, whether it shows the count already) for an
        item as core/mkds_reader.py names it, or (None, False) for one the
        sheet hasn't (the Fake Item Box) or before the sheet's loaded."""
        base = TRIPLES.get(name, name)
        key = (base, count) if (base, count) in ITEM_ICONS else base
        if key not in ITEM_ICONS:
            return None, False

        def make():
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
        return self._get(('item', key), make), isinstance(key, tuple)

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
            out = pygame.transform.smoothscale(src, out_size)
            if turn:
                out = pygame.transform.rotate(out, -90)
            if dim:
                shade = pygame.Surface(size)
                shade.fill((0, 0, 0))
                shade.set_alpha(int(255 * dim))
                out.blit(shade, (0, 0))
            return out
        return self._get(key, make)
