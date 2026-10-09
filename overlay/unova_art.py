"""
unova_art.py - Pokemon Black and White's own art for the overlay, cut at
runtime from the sprite sheets in Assets/PokemonBlackUI, so the sheets stay
the only image files:

    grid          the party screen's dark grid background (256x192)
    panels        the party screen's chevron panels: blue, the lead's
                  brighter blue, red when fainted, green for an egg; any
                  width from 82 to 160 (the flat middle is cut or repeated)
    labels        type labels, the PSN/BRN/PAR/FRZ/FNT tags, the red shiny
                  star, the mail and ball capsule icons
    badges        the eight Unova badges, dull or polished
    trainers      Hilbert and Hilda from the trainer card, and the battle
                  sprites of the trainer classes
    battle        sky backdrops and platform pairs, per terrain and time of
                  day (BattleBackgroundsTransparent.png)
    game icon     the animated title icon, Black's or White's

The sheets load the first time something is asked for (pygame needs its
display first) and every piece is cached. Anything missing comes back as
None, and the views draw without it.
"""

import logging
import os

import pygame

FOLDER = 'PokemonBlackUI'
_SHEET = 'DS _ DSi - Pokemon Black _ White - {} - {}.png'
PARTY_SHEET = _SHEET.format('Miscellaneous', 'Party Screen')
MISC_SHEET = _SHEET.format('Miscellaneous', 'Miscellaneous Icons')
CARD_SHEET = _SHEET.format('Miscellaneous', 'Trainer Card')
ICON_SHEET = _SHEET.format('Miscellaneous', 'Game Icons')
TRAINER_SHEET = _SHEET.format('Trainers', 'Trainers')
BATTLE_SHEET = 'BattleBackgroundsTransparent.png'

# Party screen: lime is see-through. Panels are 126x46 in a 4x3 grid: blue,
# red, green rows; the plain chevron, the selected (brighter) chevron, then
# two diagonal styles.
PARTY_KEY = (160, 234, 0)
GRID = (2, 2, 256, 192)
PANEL_W, PANEL_H = 126, 46
PANELS = {'normal': (0, 0), 'lead': (1, 0), 'fainted': (0, 1), 'fainted_lead': (1, 1),
          'egg': (0, 2), 'egg_lead': (1, 2)}
EMPTY_PANEL = (5, 345, 126, 46)

# Miscellaneous icons: blue is see-through.
MISC_KEY = (66, 66, 255)
TYPES = ['Normal', 'Grass', 'Water', 'Fire', 'Electric', 'Bug', 'Flying', 'Ground', 'Rock',
         'Poison', 'Fighting', 'Psychic', 'Dark', 'Ghost', 'Ice', 'Steel', 'Dragon']
TYPE_LABEL = lambda i: (73, 5 + 15 * i, 32, 12)  # noqa: E731
CATEGORIES = {'Physical': (75, 260, 28, 14), 'Special': (75, 277, 28, 14), 'Status': (75, 294, 28, 14)}
STATUS = {'Poisoned': 0, 'Badly poisoned': 0, 'Burned': 1, 'Paralyzed': 2, 'Frozen': 3, 'Fainted': 4}
STATUS_TAG = lambda i: (79, 311 + 9 * i, 19, 6)  # noqa: E731
CAPSULE, MAIL, SHINY_STAR = (76, 356, 6, 8), (85, 357, 8, 7), (96, 357, 7, 7)

# Trainer card sheet: grey-blue is see-through. Badges in game order (Trio,
# Basic, Insect, Bolt, Quake, Jet, Freeze, Legend), three rows: dull,
# clean, polished.
CARD_KEY = (112, 146, 190)
BADGE_COLUMNS = [(848, 15), (881, 12), (907, 24), (939, 24), (974, 17), (1004, 20), (1035, 25), (1063, 30)]
BADGE_ROWS = [667, 730, 794]
BADGE_H = 59
CARD_TRAINERS = {'Hilbert': (911, 967, 35, 71), 'Hilda': (981, 964, 40, 74)}

# Trainers sheet: 86x128 cells, 8 a row, each on its own flat colour.
CELL_W, CELL_H = 86, 128
# Trainer class -> cell. The leaders, Elite Four, rivals and Team Plasma
# are certain; a few of the ordinary classes are best guesses from the art
# (marked ?) until the game's own class list says otherwise.
TRAINER_CELLS = {
    'Hilbert': 0, 'Hilda': 1, 'Youngster': 2, 'Lass': 3, 'School Kid': 4, 'School Kid F': 5,
    'Smasher': 6, 'Linebacker': 7, 'Waiter': 8, 'Waitress': 9, 'Chili': 10, 'Cilan': 11,
    'Cress': 12, 'Nursery Aide': 13, 'Preschooler': 14, 'Preschooler F': 15, 'Twins': 16,
    'Pokémon Breeder': 17, 'Pokémon Breeder F': 18,  # ?
    'Lenora': 19, 'Burgh': 20, 'Elesa': 21, 'Clay': 22, 'Skyla': 23,
    'Pokémon Ranger': 24, 'Pokémon Ranger F': 25,  # ?
    'Worker': 26, 'Backpacker': 27, 'Backpacker F': 28, 'Fisherman': 29, 'Musician': 30,
    'Dancer': 31, 'Harlequin': 32, 'Artist': 33, 'Baker': 34, 'Psychic': 35, 'Psychic F': 36,
    'Cheren': 37, 'Bianca': 40, 'Team Plasma Grunt': 43, 'N': 44,
    'Rich Boy': 47, 'Lady': 48,  # ?
    'Pilot': 49, 'Hoopster': 51, 'Scientist F': 52, 'Ace Trainer F': 54, 'Ace Trainer': 55,
    'Black Belt': 56, 'Scientist': 57, 'Striker': 58, 'Brycen': 59, 'Iris': 60, 'Drayden': 61,
    'Roughneck': 62, 'Janitor': 63, 'Pokéfan': 64, 'Pokéfan F': 65, 'Doctor': 66, 'Nurse': 67,
    'Battle Girl': 69, 'Parasol Lady': 70, 'Clerk': 71,  # ?
    'Gentleman': 72, 'Socialite': 76,  # ?
    'Backers': 73, 'Backers F': 74, 'Biker': 77, 'Infielder': 78, 'Hiker': 79,
    'Veteran F': 80, 'Veteran': 81,  # ?
    'Team Plasma Grunt F': 82, 'Shauntal': 83, 'Marshal': 84, 'Grimsley': 85, 'Caitlin': 86,
    'Ghetsis': 87, 'Depot Agent': 88, 'Swimmer': 89, 'Swimmer F': 90, 'Policeman': 91, 'Maid': 92,
    'Alder': 94, 'Cyclist': 95, 'Cyclist F': 96, 'Cynthia': 97,
}

# Battle backgrounds (Diamond and Pearl style): 256x143 skies, a far
# platform (an ellipse) and a near one (the top of one, the rest hidden by
# the message box) per terrain, each for day, afternoon and night.
SKY_H = 143
SKIES = {
    'ocean': [(3, 2), (272, 1), (540, 2)],
    'mountain': [(2, 285), (271, 286), (540, 286)],
    'field': [(1, 551), (270, 552), (541, 552)],
    'forest': [(5, 824), (273, 825), (542, 826)],
    'cave': [(119, 1094), (119, 1094), (397, 1096)],
    'snow': [(7, 1372), (280, 1370), (550, 1372)],
    'indoor': [(281, 1680)] * 3,
}
PLATFORMS = {  # far (x, y, w, h), near (x, y, w, h)
    'sand': [((1021, 76, 124, 30), (891, 129, 161, 17)), ((1297, 80, 124, 30), (1167, 133, 161, 17)),
             ((1577, 82, 124, 30), (1447, 135, 161, 17))],
    'snow': [((1021, 359, 124, 30), (891, 412, 161, 17)), ((1293, 360, 124, 30), (1163, 413, 161, 17)),
             ((1588, 360, 124, 30), (1458, 413, 161, 17))],
    'water': [((1022, 605, 124, 30), (892, 658, 161, 17)), ((1297, 609, 124, 30), (1167, 662, 161, 17)),
              ((1596, 613, 124, 30), (1466, 666, 161, 17))],
    'grass': [((1011, 871, 126, 32), (882, 921, 152, 22)), ((1300, 882, 126, 32), (1171, 932, 152, 22)),
              ((1604, 880, 126, 32), (1475, 930, 152, 22))],
    'field': [((1011, 1154, 124, 30), (881, 1207, 161, 17)), ((1305, 1162, 124, 30), (1175, 1215, 161, 17)),
              ((1590, 1170, 124, 30), (1460, 1223, 161, 17))],
    'indoor': [((1126, 1449, 124, 29), (996, 1501, 161, 17))] * 3,
    'cave': [((1511, 1450, 124, 33), (1381, 1502, 161, 21))] * 3,
}
# The overlay's times of day (backdrop.period) -> the sheet's three.
PERIODS = {'morning': 0, 'day': 0, 'evening': 1, 'night': 2}

# Game icon: 41 frames of 32x32, 16 a row; White's three rows, then Black's.
ICON_FRAMES, ICON_MS = 41, 90


def _keyed(sheet, rect, key):
    """`rect` cut from `sheet` with `key` made see-through."""
    piece = pygame.Surface(rect[2:], pygame.SRCALPHA)
    piece.blit(sheet, (0, 0), rect)
    if key is not None:
        for y in range(piece.get_height()):
            for x in range(piece.get_width()):
                if piece.get_at((x, y))[:3] == key:
                    piece.set_at((x, y), (0, 0, 0, 0))
    return piece


def _trim(piece):
    box = piece.get_bounding_rect()
    return piece.subsurface(box).copy() if box.width and box.height else piece


def _flat_columns(surf):
    """(first, last) of the longest run of identical neighbouring columns:
    the part of a panel that can be cut or repeated without a seam."""
    w, h = surf.get_size()
    cols = [tuple(surf.get_at((x, y)) for y in range(h)) for x in range(w)]
    best, start = (0, -1), 0
    for x in range(1, w + 1):
        if x == w or cols[x] != cols[x - 1]:
            if x - 1 - start > best[1] - best[0]:
                best = (start, x - 1)
            start = x
    return best


def resize_panel(surf, width):
    """A panel `width` wide: its flat middle cut short or stretched."""
    w, h = surf.get_size()
    if width == w:
        return surf
    first, last = _flat_columns(surf)
    cut = (first + last) // 2
    out = pygame.Surface((width, h), pygame.SRCALPHA)
    out.blit(surf, (0, 0), (0, 0, cut, h))
    if width < w:
        drop = min(w - width, last - first)
        out.blit(surf, (cut, 0), (cut + drop, 0, w - cut - drop, h))
    else:
        for x in range(cut, cut + width - w):
            out.blit(surf, (x, 0), (cut, 0, 1, h))
        out.blit(surf, (cut + width - w, 0), (cut, 0, w - cut, h))
    return out


class UnovaArt:
    def __init__(self, assets_dir):
        self.folder = os.path.join(assets_dir, FOLDER)
        self._sheets = {}
        self._cache = {}

    def _sheet(self, name):
        if name not in self._sheets:
            try:
                self._sheets[name] = pygame.image.load(os.path.join(self.folder, name)).convert_alpha()
            except (pygame.error, FileNotFoundError, OSError) as e:
                logging.warning(f"Black/White art missing ({name}): {e}")
                self._sheets[name] = None
        return self._sheets[name]

    def _get(self, key, make):
        if key not in self._cache:
            try:
                self._cache[key] = make()
            except Exception:
                logging.exception(f"Couldn't cut {key} from the Black/White sheets")
                self._cache[key] = None
        return self._cache[key]

    def _cut(self, sheet_name, rect, key, trim=False):
        sheet = self._sheet(sheet_name)
        if sheet is None:
            return None
        piece = _keyed(sheet, rect, key)
        return _trim(piece) if trim else piece

    # -- party screen ----------------------------------------------------------

    def grid(self):
        return self._get('grid', lambda: self._cut(PARTY_SHEET, GRID, None))

    def panel(self, kind, width=PANEL_W):
        """kind: 'normal', 'lead', 'fainted', 'fainted_lead', 'egg', 'egg_lead' or 'empty'."""
        def make():
            if kind == 'empty':
                rect = EMPTY_PANEL
            else:
                col, row = PANELS[kind]
                rect = (5 + 128 * col, 201 + 48 * row, PANEL_W, PANEL_H)
            base = self._cut(PARTY_SHEET, rect, PARTY_KEY)
            return resize_panel(base, width) if base else None
        return self._get(('panel', kind, width), make)

    # -- icons -----------------------------------------------------------------

    def type_label(self, name):
        if name not in TYPES:
            return None
        return self._get(('type', name), lambda: self._cut(MISC_SHEET, TYPE_LABEL(TYPES.index(name)), MISC_KEY))

    def category(self, name):
        rect = CATEGORIES.get(name)
        return self._get(('cat', name), lambda: self._cut(MISC_SHEET, rect, MISC_KEY)) if rect else None

    def status_tag(self, status):
        i = STATUS.get(status)
        return self._get(('status', i), lambda: self._cut(MISC_SHEET, STATUS_TAG(i), MISC_KEY)) if i is not None else None

    def shiny_star(self):
        return self._get('star', lambda: self._cut(MISC_SHEET, SHINY_STAR, MISC_KEY))

    def mail(self):
        return self._get('mail', lambda: self._cut(MISC_SHEET, MAIL, MISC_KEY))

    def badge(self, index, polished=True):
        """Badge `index` (0 Trio ... 7 Legend): polished, or dull for one not
        earned yet."""
        def make():
            x, w = BADGE_COLUMNS[index]
            return self._cut(CARD_SHEET, (x, BADGE_ROWS[2 if polished else 0], w, BADGE_H), CARD_KEY, trim=True)
        return self._get(('badge', index, polished), make)

    def small_badge(self, index, polished=True):
        """The badge at 2/5 size, about 22 px tall (for a row of eight)."""
        def make():
            b = self.badge(index, polished)
            if not b:
                return None
            size = (max(1, round(b.get_width() * 0.4)), max(1, round(b.get_height() * 0.4)))
            return pygame.transform.scale(b, size)
        return self._get(('small_badge', index, polished), make)

    # -- trainers ----------------------------------------------------------------

    def card_trainer(self, name):
        """Hilbert or Hilda as on the trainer card (about 36x72)."""
        rect = CARD_TRAINERS.get(name, CARD_TRAINERS['Hilbert'])
        return self._get(('card', name), lambda: self._cut(CARD_SHEET, rect, CARD_KEY, trim=True))

    def battle_trainer(self, name):
        """A trainer class's (or named trainer's) battle sprite, or None."""
        cell = TRAINER_CELLS.get(name)
        if cell is None:
            return None

        def make():
            sheet = self._sheet(TRAINER_SHEET)
            if sheet is None:
                return None
            x, y = (cell % 8) * CELL_W, (cell // 8) * CELL_H
            key = tuple(sheet.get_at((x + CELL_W - 2, y + CELL_H - 2)))[:3]
            return _trim(_keyed(sheet, (x, y, CELL_W, CELL_H), key))
        return self._get(('trainer', cell), make)

    # -- battle ------------------------------------------------------------------

    def sky(self, kind, when='day'):
        pos = SKIES.get(kind, SKIES['field'])[PERIODS.get(when, 0)]
        return self._get(('sky', kind, when), lambda: self._cut(BATTLE_SHEET, (*pos, 256, SKY_H), None))

    def platforms(self, kind, when='day'):
        """(far, near) platform surfaces."""
        far, near = PLATFORMS.get(kind, PLATFORMS['grass'])[PERIODS.get(when, 0)]
        return (self._get(('far', kind, when), lambda: self._cut(BATTLE_SHEET, far, None, trim=True)),
                self._get(('near', kind, when), lambda: self._cut(BATTLE_SHEET, near, None, trim=True)))

    # -- game icon -----------------------------------------------------------------

    def game_icon(self, black, t_ms):
        i = (t_ms // ICON_MS) % ICON_FRAMES
        rect = (1 + 34 * (i % 16), 1 + 34 * (i // 16) + (102 if black else 0), 32, 32)
        return self._get(('icon', black, i), lambda: self._cut(ICON_SHEET, rect, None))
