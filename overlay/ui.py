"""
ui.py - the overlay's palette and pixel-art drawing helpers: rounded panels,
HP bars, status tags, badge pips, the tiled background, sparkles.

Everything draws on the 256x192 canvas at 1x; the window scales the finished
canvas up with nearest-neighbour, so every pixel here is a real pixel on
screen. Colours live in THEME so the look can be changed in one place.
"""

import math

import pygame

THEME = {
    # Background pattern (party screen)
    'bg': (40, 104, 112), 'bg_tile': (52, 122, 130), 'bg_dot': (70, 142, 148),
    # Header / footer bars
    'bar': (32, 48, 58), 'bar_hi': (66, 90, 102), 'bar_lo': (16, 24, 32),
    # Panels
    'panel_border': (40, 56, 66), 'panel_fill': (234, 242, 242),
    'panel_hi': (255, 255, 255), 'panel_lo': (186, 204, 208),
    'lead_fill': (250, 242, 206), 'lead_lo': (220, 200, 140), 'lead_border': (120, 88, 32),
    'faint_fill': (238, 208, 208), 'faint_lo': (206, 164, 164),
    # Text
    'text': (64, 64, 72), 'text_shadow': (208, 208, 216),
    'text_light': (248, 248, 248), 'text_light_shadow': (24, 32, 40),
    'text_muted': (96, 104, 112),
    'male': (48, 128, 240), 'female': (232, 80, 104),
    # Achievements (the game card's progress bar, trophy and labels)
    'ach': (232, 176, 40), 'ach_hi': (252, 224, 120), 'ach_lo': (152, 104, 24),
    # HP bar
    'hp_frame': (40, 52, 60), 'hp_empty': (82, 98, 106), 'hp_label': (248, 208, 72),
    'hp_green': (88, 208, 128), 'hp_green_hi': (160, 248, 184),
    'hp_yellow': (240, 192, 48), 'hp_yellow_hi': (248, 232, 128),
    'hp_red': (232, 72, 56), 'hp_red_hi': (248, 144, 120),
    # Battle scene
    'sky': [(112, 176, 232), (128, 188, 240), (144, 200, 244), (164, 212, 248), (184, 224, 250)],
    'ground': [(146, 200, 112), (128, 186, 98), (112, 172, 86)],
    'box_frame': (56, 80, 112), 'box_frame_hi': (104, 136, 176), 'box_fill': (248, 248, 248),
    # Chroma key (--chroma), filled wherever the background would be
    'chroma': None,
}

STATUS_TAGS = {
    'Asleep': ('SLP', (136, 144, 160)), 'Poisoned': ('PSN', (168, 88, 192)),
    'Badly poisoned': ('TOX', (128, 56, 160)), 'Burned': ('BRN', (232, 104, 56)),
    'Frozen': ('FRZ', (88, 176, 232)), 'Paralyzed': ('PAR', (200, 168, 32)),
    'Fainted': ('FNT', (208, 64, 64)),
}

# Move button colours by type (the usual colours for each type).
TYPE_COLORS = {
    'Normal': (168, 168, 120), 'Fighting': (192, 48, 40), 'Flying': (168, 144, 240),
    'Poison': (160, 64, 160), 'Ground': (224, 192, 104), 'Rock': (184, 160, 56),
    'Bug': (168, 184, 32), 'Ghost': (112, 88, 152), 'Steel': (184, 184, 208),
    'Fire': (240, 128, 48), 'Water': (104, 144, 240), 'Grass': (120, 200, 80),
    'Electric': (248, 208, 48), 'Psychic': (248, 88, 136), 'Ice': (152, 216, 216),
    'Dragon': (112, 56, 248), 'Dark': (112, 88, 72), '???': (104, 160, 144),
}

# One colour per badge, in badge order (Coal ... Beacon). Simple gems, not the
# real badge art.
BADGE_COLORS = [(152, 120, 104), (96, 184, 96), (200, 168, 112), (88, 144, 232),
                (232, 200, 72), (184, 192, 200), (136, 216, 240), (240, 136, 56)]


def lighten(c, amt=40):
    return tuple(min(255, v + amt) for v in c)


def darken(c, amt=40):
    return tuple(max(0, v - amt) for v in c)


def panel(surf, rect, fill=None, border=None, hi=None, lo=None, radius=2):
    """A pixel-art rounded box: 1px border with cut corners, a highlight line
    along the inside top and a shade line along the inside bottom."""
    t = THEME
    fill = fill or t['panel_fill']
    border = border or t['panel_border']
    hi = hi or t['panel_hi']
    lo = lo or t['panel_lo']
    x, y, w, h = rect
    r = radius
    # Fill, stepped at the corners.
    pygame.draw.rect(surf, fill, (x + 1, y + 1 + r, w - 2, h - 2 - 2 * r))
    for i in range(r + 1):
        inset = r - i
        pygame.draw.line(surf, fill, (x + 1 + inset, y + 1 + i), (x + w - 2 - inset, y + 1 + i))
        pygame.draw.line(surf, fill, (x + 1 + inset, y + h - 2 - i), (x + w - 2 - inset, y + h - 2 - i))
    # Border.
    pygame.draw.line(surf, border, (x + r, y), (x + w - 1 - r, y))
    pygame.draw.line(surf, border, (x + r, y + h - 1), (x + w - 1 - r, y + h - 1))
    pygame.draw.line(surf, border, (x, y + r), (x, y + h - 1 - r))
    pygame.draw.line(surf, border, (x + w - 1, y + r), (x + w - 1, y + h - 1 - r))
    for i in range(1, r + 1):
        # stair-step corners
        surf.set_at((x + r - i, y + i), border)
        surf.set_at((x + w - 1 - r + i, y + i), border)
        surf.set_at((x + r - i, y + h - 1 - i), border)
        surf.set_at((x + w - 1 - r + i, y + h - 1 - i), border)
    # Inner highlight / shade.
    pygame.draw.line(surf, hi, (x + r + 1, y + 1), (x + w - 2 - r, y + 1))
    pygame.draw.line(surf, lo, (x + r + 1, y + h - 2), (x + w - 2 - r, y + h - 2))


def textbox(surf, rect):
    """The battle message box: a thick framed box, like the games' text windows."""
    t = THEME
    x, y, w, h = rect
    panel(surf, rect, fill=t['box_frame'], border=darken(t['box_frame'], 30),
          hi=t['box_frame_hi'], lo=darken(t['box_frame'], 16), radius=3)
    panel(surf, (x + 4, y + 4, w - 8, h - 8), fill=t['box_fill'], border=darken(t['box_frame'], 20),
          hi=(255, 255, 255), lo=(216, 216, 224), radius=2)


EFFECT_LABELS = {4: ("X4", (72, 184, 88)), 2: ("X2", (72, 184, 88)), 0.5: ("X1/2", (200, 128, 48)),
                 0.25: ("X1/4", (200, 128, 48)), 0: ("X0", (88, 88, 96))}


def move_button(surf, font, mini, rect, name, mtype=None, pp=None, pp_max=None, selected=False, effect=None):
    """One move, coloured by its type, with PP on the right. name=None draws
    an empty slot. selected: the move used last (lighter, white border).
    effect: its type multiplier against the foe (a label in the top right
    corner unless it's 1)."""
    x, y, w, h = rect
    if name is None:
        panel(surf, rect, fill=(120, 132, 140), border=(72, 80, 88), hi=(150, 160, 168), lo=(104, 112, 120))
        font.draw(surf, "-", (x + 6, y + 5), (200, 204, 208), (72, 80, 88))
        return
    c = TYPE_COLORS.get(mtype, (150, 150, 150))
    if selected:
        panel(surf, rect, fill=lighten(c, 24), border=(248, 248, 248), hi=lighten(c, 80), lo=darken(c, 10))
    else:
        panel(surf, rect, fill=c, border=darken(c, 80), hi=lighten(c, 60), lo=darken(c, 30))
    font.draw(surf, name, (x + 6, y + 5), (248, 248, 248), darken(c, 90))
    if pp is not None and pp_max:
        frac = pp / pp_max
        col = (248, 248, 248) if frac > 0.5 else (248, 224, 96) if frac > 0.25 else (248, 160, 72) if pp else (248, 96, 88)
        text = f"{pp}/{pp_max}"
        mini.draw(surf, text, (x + w - 5 - mini.width(text), y + 7), col)
        mini.draw(surf, "PP", (x + w - 16 - mini.width(text), y + 7), lighten(c, 70))
    label = EFFECT_LABELS.get(effect)
    if label:
        text, lc = label
        lw = mini.width(text) + 4
        lx = x + w - 3 - lw
        # A tab on the top edge, clear of the PP line below it.
        pygame.draw.rect(surf, darken(lc, 60), (lx - 1, y, lw + 2, 7))
        pygame.draw.rect(surf, lc, (lx, y + 1, lw, 5))
        mini.draw(surf, text, (lx + 2, y + 1), (248, 248, 248))


def hp_color(frac):
    t = THEME
    if frac > 0.5:
        return t['hp_green'], t['hp_green_hi']
    if frac > 0.2:
        return t['hp_yellow'], t['hp_yellow_hi']
    return t['hp_red'], t['hp_red_hi']


def hp_bar(surf, mini, x, y, width, frac):
    """'HP' label plus a 3px-tall bar, 7px tall in total. frac is 0..1."""
    t = THEME
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, t['hp_frame'], (x, y, width, 7))
    mini.draw(surf, "HP", (x + 2, y + 1), t['hp_label'])
    bx, bw = x + 11, width - 13
    pygame.draw.rect(surf, t['hp_empty'], (bx, y + 2, bw, 3))
    fill = int(round(bw * frac))
    if frac > 0 and fill == 0:
        fill = 1
    if fill:
        c, hi = hp_color(frac)
        pygame.draw.rect(surf, c, (bx, y + 2, fill, 3))
        pygame.draw.line(surf, hi, (bx, y + 2), (bx + fill - 1, y + 2))


def chip(surf, mini, x, y, text, color):
    """A small coloured label (9 px tall) with mini-font text. Returns its width."""
    w = mini.width(text) + 5
    pygame.draw.rect(surf, darken(color, 50), (x, y, w, 9))
    pygame.draw.rect(surf, color, (x + 1, y + 1, w - 2, 7))
    pygame.draw.line(surf, lighten(color, 50), (x + 1, y + 1), (x + w - 2, y + 1))
    mini.draw(surf, text, (x + 3, y + 2), (248, 248, 248))
    return w


def status_tag(surf, mini, x, y, status):
    tag = STATUS_TAGS.get(status)
    if not tag:
        return 0
    text, color = tag
    return chip(surf, mini, x, y, text, color)


# Stat stage chips: raised in red, lowered in blue (the colours the games'
# stat-change animations use). Conditions from the parser's `conditions`
# get their own short labels.
STAGE_UP, STAGE_DOWN = (216, 88, 64), (64, 112, 216)
CONDITION_TAGS = {
    'Confused': ('CNF', (200, 152, 48)), 'Infatuated': ('LOVE', (232, 104, 168)),
    'Leech Seed': ('SEED', (96, 168, 72)), 'Cursed': ('CURSE', (104, 72, 136)),
    'Substitute': ('SUB', (144, 128, 104)), 'Nightmare': ('NGHT', (80, 72, 120)),
}


def stage_chips(mon):
    """[(text, colour), ...] for a battler's stat stages and conditions."""
    out = [(f"{name}{'↑' if v > 0 else '↓'}{abs(v)}", STAGE_UP if v > 0 else STAGE_DOWN)
           for name, v in (mon.get('stages') or {}).items()]
    out += [CONDITION_TAGS[c] for c in mon.get('conditions') or [] if c in CONDITION_TAGS]
    return out


def chip_rows(mini, chips, width):
    """Splits chips into rows that fit `width`."""
    rows, row, used = [], [], 0
    for text, color in chips:
        w = mini.width(text) + 5 + 2
        if row and used + w > width:
            rows.append(row)
            row, used = [], 0
        row.append((text, color))
        used += w
    if row:
        rows.append(row)
    return rows


def gender_symbol(font, gender):
    if gender == 'M':
        return '♂', THEME['male']
    if gender == 'F':
        return '♀', THEME['female']
    return None, None


def badge_pip(surf, x, y, index, earned):
    """A 7x7 gem. Earned badges are coloured, missing ones are an outline."""
    c = BADGE_COLORS[index % len(BADGE_COLORS)]
    shape = [".###.", "#####", "#####", "#####", ".###."]
    if earned:
        for yy, row in enumerate(shape):
            for xx, ch in enumerate(row):
                if ch == '#':
                    surf.set_at((x + xx + 1, y + yy + 1), c)
        # rim + shine
        pygame.draw.lines(surf, darken(c, 70), True,
                          [(x + 2, y), (x + 4, y), (x + 6, y + 2), (x + 6, y + 4), (x + 4, y + 6),
                           (x + 2, y + 6), (x, y + 4), (x, y + 2)])
        surf.set_at((x + 2, y + 2), lighten(c, 90))
        surf.set_at((x + 3, y + 2), lighten(c, 60))
    else:
        pygame.draw.lines(surf, (88, 104, 112), True,
                          [(x + 2, y), (x + 4, y), (x + 6, y + 2), (x + 6, y + 4), (x + 4, y + 6),
                           (x + 2, y + 6), (x, y + 4), (x, y + 2)])


def tiled_background(surf, t_ms, rect=None):
    """The party-screen background: a slowly drifting diamond pattern."""
    t = THEME
    x0, y0, w, h = rect or (0, 0, surf.get_width(), surf.get_height())
    if t['chroma']:
        pygame.draw.rect(surf, t['chroma'], (x0, y0, w, h))
        return
    pygame.draw.rect(surf, t['bg'], (x0, y0, w, h))
    shift = int(t_ms / 120) % 16
    for ty in range(-16, h + 16, 16):
        for tx in range(-16, w + 16, 16):
            cx, cy = x0 + tx + shift, y0 + ty + shift
            # small diamond in the middle of each 16x16 tile
            for i in range(4):
                pygame.draw.line(surf, t['bg_tile'], (cx + 8 - i, cy + 4 + i), (cx + 8 + i, cy + 4 + i))
                pygame.draw.line(surf, t['bg_tile'], (cx + 8 - i, cy + 11 - i), (cx + 8 + i, cy + 11 - i))
            surf.set_at((cx + 8, cy + 7), t['bg_dot'])  # off-surface pixels are ignored


def sparkle(surf, x, y, t_ms, color=(248, 224, 96)):
    """A small twinkling 4-point star for shiny Pokemon."""
    phase = (t_ms // 150) % 6
    size = [0, 1, 2, 3, 2, 1][phase]
    if size == 0:
        return
    core = lighten(color, 60)
    for i in range(1, size + 1):
        c = color if i < size else darken(color, 30)
        surf.set_at((x + i, y), c)
        surf.set_at((x - i, y), c)
        surf.set_at((x, y + i), c)
        surf.set_at((x, y - i), c)
    surf.set_at((x, y), core)


def bands(surf, rect, colors, dither=True):
    """Horizontal colour bands with a checkerboard dither between them."""
    x, y, w, h = rect
    n = len(colors)
    for i, c in enumerate(colors):
        y1 = y + h * i // n
        y2 = y + h * (i + 1) // n
        pygame.draw.rect(surf, c, (x, y1, w, y2 - y1))
        if dither and i > 0:
            prev = colors[i - 1]
            for xx in range(x, x + w, 2):
                surf.set_at((xx, y1), prev)
                surf.set_at((xx + 1, y1 + 1), prev)


def wipe(surf, progress):
    """Battle transition: horizontal black bars closing (progress 0..1) and
    opening again (1..2)."""
    w, h = surf.get_size()
    bars = 8
    bh = h // bars
    amount = progress if progress <= 1 else 2 - progress
    for i in range(bars):
        cover = int(w * amount)
        if i % 2 == 0:
            pygame.draw.rect(surf, (8, 8, 16), (0, i * bh, cover, bh))
        else:
            pygame.draw.rect(surf, (8, 8, 16), (w - cover, i * bh, cover, bh))


def ease_out(t):
    return 1 - (1 - t) * (1 - t)


def bob(t_ms, period=1200, amp=1):
    return int(round(math.sin(t_ms / period * 2 * math.pi) * amp))


# -- shared by every view ------------------------------------------------------

def bar(surf, y, h):
    """A header or footer bar across the whole canvas."""
    t = THEME
    w = surf.get_width()
    pygame.draw.rect(surf, t['bar'], (0, y, w, h))
    pygame.draw.line(surf, t['bar_hi'], (0, y), (w - 1, y))
    pygame.draw.line(surf, t['bar_lo'], (0, y + h - 1), (w - 1, y + h - 1))


def pixels(surf, x, y, rows, palette):
    """Pixel art from strings: each character is a pixel, looked up in
    `palette` (character -> colour); '.' and characters not in it are left
    clear."""
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            c = palette.get(ch)
            if c:
                surf.set_at((x + xx, y + yy), c)


def meter(surf, mini, x, y, width, frac, label="ACH"):
    """Like hp_bar, in gold: a label plus a 3px-tall bar, 7px tall in total."""
    t = THEME
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, t['hp_frame'], (x, y, width, 7))
    mini.draw(surf, label, (x + 2, y + 1), t['hp_label'])
    bx = x + mini.width(label) + 4
    bw = x + width - 2 - bx
    pygame.draw.rect(surf, t['hp_empty'], (bx, y + 2, bw, 3))
    fill = int(round(bw * frac))
    if frac > 0 and fill == 0:
        fill = 1
    if fill:
        pygame.draw.rect(surf, t['ach'], (bx, y + 2, fill, 3))
        pygame.draw.line(surf, t['ach_hi'], (bx, y + 2), (bx + fill - 1, y + 2))


# A DS game card, 16x20, standing in for a game that has no sprite of its own.
# l/L/w: its label (light, dark, the white stripe), in the game's colour.
_CARD = [
    ".oooooooooooo...",
    "ohhhhhhhhhhhho..",
    "ohbbbbbbbbbbbbo.",
    "ohbLLLLLLLLLLbbo",
    "ohbLllllllllLbbo",
    "ohbLlwwwwwwlLbbo",
    "ohbLllllllllLbbo",
    "ohbLllllllllLbbo",
    "ohbLllllllllLbbo",
    "ohbLllllllllLbbo",
    "ohbLllllllllLbbo",
    "ohbLLLLLLLLLLbbo",
    "ohbbbbbbbbbbbbbo",
    "ohbbbbbbbbbbbbbo",
    "ohbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbo",
    "obcbcbcbcbcbcbbo",
    "obcbcbcbcbcbcbbo",
    "obbbbbbbbbbbbbbo",
    ".oooooooooooooo.",
]

# Label colours for game cards, picked by the game code so a game always
# gets the same one.
CARD_COLORS = [(216, 72, 64), (64, 128, 216), (72, 168, 88), (232, 160, 40),
               (152, 88, 192), (40, 160, 168), (224, 96, 152), (120, 128, 144)]


def card_color(code):
    return CARD_COLORS[sum((code or '????').encode()) % len(CARD_COLORS)]


def game_card(surf, x, y, color):
    """A DS game card (16x20) with a `color` label, top left corner at x, y."""
    pixels(surf, x, y, _CARD, {
        'o': (40, 44, 52), 'h': (176, 180, 188), 'b': (136, 140, 150), 'c': (208, 176, 72),
        'l': color, 'L': darken(color, 50), 'w': lighten(color, 110),
    })


_TROPHY = [
    "ooooooooo",
    "ohggggggo",
    "ohggggggo",
    ".ohggggo.",
    "..oggdo..",
    "...ogo...",
    "...ogo...",
    "..oddoo..",
    ".ooooooo.",
]


def trophy(surf, x, y, earned=True):
    """A 9x9 trophy; grey when nothing's earned yet."""
    t = THEME
    if earned:
        pal = {'o': t['ach_lo'], 'h': t['ach_hi'], 'g': t['ach'], 'd': darken(t['ach'], 40)}
    else:
        pal = {'o': (88, 104, 112), 'h': (196, 204, 208), 'g': (160, 172, 178), 'd': (128, 140, 146)}
    pixels(surf, x, y, _TROPHY, pal)


# A DSi, open, 34x44: the lid with its screen (rows 0-20), the hinge, then
# the base with the touch screen and the buttons.
_DSI = [
    "..oooooooooooooooooooooooooooooo..",
    ".obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo.",
    "obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo",
    "obbbbbkkkkkkkkkkkkkkkkkkkkkkbbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkssssssssssssssssssssskbbbbo",
    "obbbbbkkkkkkkkkkkkkkkkkkkkkkbbbbbo",
    "obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo",
    ".obbbbbbbbbbbbbbbbbbbbbbbbbbbbbbo.",
    "..oooooooooooooooooooooooooooooo..",
    "...oHHHHHHHHHHHHHHHHHHHHHHHHHHo...",
    "..oooooooooooooooooooooooooooooo..",
    ".oddddddddddddddddddddddddddddddo.",
    "oddddddddddddddddddddddddddddddddo",
    "oddddddKKKKKKKKKKKKKKKKKKKKKddpddo",
    "oddpdddKtttttttttttttttttttKdpdpdo",
    "odpppddKtttttttttttttttttttKddpddo",
    "oddpdddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdpdddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKtttttttttttttttttttKdddddo",
    "oddddddKKKKKKKKKKKKKKKKKKKKKdddddo",
    "oddddddddddddddddddddddddddddddddo",
    ".oddddddddddddddddddddddddddddddo.",
    "..oooooooooooooooooooooooooooooo..",
]
DSI_W, DSI_H = 34, 40
DSI_TOP_SCREEN = (7, 4, 21, 12)     # x, y, w, h inside the icon


def dsi(surf, x, y, color=(72, 76, 88)):
    """A small open DSi, top left corner at x, y. The top screen is left dark
    for whatever the caller draws on it (DSI_TOP_SCREEN)."""
    pixels(surf, x, y, _DSI, {
        'o': (24, 28, 36), 'b': color, 'd': darken(color, 12), 'H': darken(color, 30),
        'k': (20, 22, 28), 's': (36, 44, 56), 'K': (20, 22, 28), 't': (196, 212, 216),
        'p': (150, 156, 168),
    })
