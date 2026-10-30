"""
readme_art.py - the README's banner and its sections' icons, drawn from the
launcher's own pixel art so the page looks like the console's screens:
topscreen.c's DSi, Wi-Fi sign, title letters, diamonds and colors, ui.c's
colors and check box, the main screen's tile icons, the game list's star
and libnds' font (tests/c/ui/font.h, which the modern look writes with).

    python tools/readme_art.py          docs/images/banner.svg and docs/images/icons/*.svg
    python tools/readme_art.py --png    a still of each too, in renders/readme-art (Pillow)

(--out DIR for another folder: tests/test_readme_art.py checks they're up
to date that way.)

The banner is the launcher's top screen made wide: its header bar, the pixel
DSi on the drifting diamonds, and beside it the tagline (on a grid twice as
fine as the art's, so its pixels can be a little smaller than the DSi's)
and the features as the launcher's chips. It moves as the console's does
while it connects (the Wi-Fi sign's arcs lighting up, the chip saying
Connecting, then Connected), with CSS, so a browser set to reduce motion
shows it still and connected. The icons are the main screen's tiles, small:
the launcher's icon on a panel (the check box is one already), plus four
of the README's own in their style. Run it again after changing that art.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from helpers import REPO, launcher_ui as lui  # noqa: E402

SOURCE = os.path.join(REPO, "launcher", "source")
OUT = os.path.join(REPO, "docs", "images")

TAGLINE = ["Same native DS games,", "same original hardware,", "modern features."]
# The features, as the launcher's chips (dark like its header bar) in two
# columns under the tagline: what DSiRPC does down the first, in the colors
# the launcher gives them, where it runs down the second; each chip's text
# color
FEATURES = [("Discord + RA Dynamic Rich Presence", "C_GREEN"),
            ("Real RetroAchievements for DS games, even offline", "C_AMBER"),
            ("Backup saves, sync between devices", "C_CYAN"),
            ("Runs on a real 3DS or DSi", "C_TEXT"),
            ("Windows + macOS desktop clients", "C_TEXT"),
            ("Auto-Updates, console included", "C_TEXT")]
TEXT_RES = 2                            # the tagline's own grid: twice as fine as the art's
CONNECTING_S, CONNECTED_S = 4.8, 3.2     # the banner's loop: 3 rounds of the arcs, then connected
ARC_S = 0.4                             # an arc every 400 ms, as the launcher
DRIFT_S = 16 * 7 / 59.83                # the diamonds: a pixel every 7 frames, 16 to a cell

# The README's own icons, for sections the launcher has none for, in the
# style of the tiles' (8x8, drawn 2x; 1-3 their colors)
PROMPT = ["........", ".1......", "..1.....", "...1....", "..1.....", ".1..222.", "........", "........"]
FLAG = ["12222...", "122222..", "1222222.", "122222..", "12222...", "1.......", "1.......", "1......."]
HEART = [".11..11.", "1111111.", "1121111.", "1111111.", ".11111..", "..111...", "...1....", "........"]
PAGE = [".11111..", ".1222111", ".1333321", ".1222221", ".1333321", ".1222221", ".1333321", ".1111111"]
BALL = ["..1111..", ".111111.", "11333311", "33322333", "22333322", "22222222", ".222222.", "..2222.."]


def read(name):
    with open(os.path.join(SOURCE, name), encoding="utf-8") as f:
        return f.read()


def block(src, name):
    """What's between the braces of a C array's initializer"""
    m = re.search(r"\b%s\s*(\[[^\]]*\]\s*)+=\s*\{" % re.escape(name), src)
    if m is None:
        raise SystemExit(f"Can't find {name} in the launcher's code: has it moved?")
    depth, i = 1, m.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return src[m.end():i - 1]


def strings(src, name):
    return re.findall(r'"([^"]*)"', block(src, name))


def numbers(src, name):
    return [int(n, 0) for n in re.findall(r"\b(0x[0-9A-Fa-f]+|\d+)\b", block(src, name))]


def colors(src, name):
    """A table of { r, g, b } by designated entry, {entry's first name: rgb}"""
    return {key: (int(r), int(g), int(b)) for key, r, g, b in
            re.findall(r"\[\s*(\w+)[^\]]*\]\s*=\s*\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", block(src, name))}


def define(src, name):
    return int(re.search(r"#define\s+%s\s+(\d+)" % name, src).group(1))


class Art:
    """Everything the README's art takes from the launcher"""

    def __init__(self):
        top, ui, main, picker = read("topscreen.c"), read("ui.c"), read("main.c"), read("picker.c")
        self.ui = colors(ui, "RGBS")
        self.top = colors(top, "rgb")
        self.top.update({"C_" + k[2:]: v for k, v in colors(top, "modern_rgb").items()})
        hexes = re.findall(r"0x([0-9A-Fa-f]{2})", block(open(os.path.join(REPO, "tests", "c", "ui", "font.h")).read(),
                                                         "default_font"))
        self.font = bytes(int(h, 16) for h in hexes)
        self.dsi = strings(top, "DSI_ART")
        keys = re.search(r'DSI_KEYS\[\]\s*=\s*"(\w+)"', top).group(1)
        rgb = numbers(top, "DSI_RGB")
        self.dsi_colors = {k: tuple(rgb[i * 3:i * 3 + 3]) for i, k in enumerate(keys)}
        n = numbers(top, "WIFI")
        self.wifi = [tuple(n[i:i + 3]) for i in range(0, len(n), 3)]
        n = numbers(top, "LINES")
        self.lines = [tuple(n[i:i + 2]) for i in range(0, len(n), 2)]
        self.lines_x = define(top, "LINES_X0"), define(top, "LINES_X1")
        letters = strings(top, "TITLE")
        self.title = [letters[i:i + 7] for i in range(0, len(letters), 7)]
        self.battery = strings(top, "BATTERY")
        self.bolt = strings(top, "BOLT")
        self.star = strings(picker, "STAR")
        self.check = strings(ui, "ICON_CHECK")
        self.tiles = {name: strings(main, "ICON_" + name) for name in ("GAMES", "SAVES", "SETTINGS", "EXIT")}
        tile_colors = re.findall(r"\{\s*(UI_\w+),\s*(UI_\w+),\s*(UI_\w+|0)\s*\}", block(main, "COLORS"))
        self.tile_colors = dict(zip(("GAMES", "SAVES", "SETTINGS", "EXIT"), tile_colors))
        rgb = {k: v for k, v in re.findall(r"#define\s+(\w+)\s+RGB\((\d+, \d+, \d+)\)", top)}
        self.top_rgb = {k: tuple(int(c) for c in v.split(", ")) for k, v in rgb.items()}

    def rgb(self, name):
        """A color by the launcher's name for it (UI_ for the bottom screen's, C_ the top's)"""
        if name.startswith("UI_"):
            return self.ui[name]
        return self.top.get(name) or self.top_rgb[name]


class Picture:
    """Pixels to draw on, None where it's clear"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rows = [[None] * w for _ in range(h)]

    def fill(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.h, y + h)):
            row = self.rows[yy]
            for xx in range(max(0, x), min(self.w, x + w)):
                row[xx] = c

    def art(self, x, y, rows, palette, scale=1):
        """Pixel art: rows of characters, palette {character: rgb}"""
        for j, row in enumerate(rows):
            for i, k in enumerate(row):
                if palette.get(k) is not None:
                    self.fill(x + i * scale, y + j * scale, scale, scale, palette[k])

    def paths(self, dx=0, dy=0, skip=None):
        """As SVG paths, one a color"""
        rects = lui.rectangles([[skip if c is None else c for c in row] for row in self.rows],
                               0, 0, self.w, self.h, skip=skip)
        out = []
        for color, rs in sorted(rects.items(), key=lambda kv: -len(kv[1])):
            d = "".join(f"M{x + dx} {y + dy}h{w}v{h}h-{w}z" for x, y, w, h in rs)
            out.append(f'<path fill="{hexrgb(color)}" d="{d}"/>')
        return out

    def image(self, back):
        from PIL import Image
        im = Image.new("RGB", (self.w, self.h))
        im.putdata([back if c is None else c for row in self.rows for c in row])
        return im

    def mask(self):
        """Where it's drawn on, for pasting it"""
        from PIL import Image
        im = Image.new("L", (self.w, self.h))
        im.putdata([0 if c is None else 255 for row in self.rows for c in row])
        return im


def hexrgb(c):
    return "#%02x%02x%02x" % c


class Font:
    """libnds' font as the modern look writes with it: each letter as wide as
    it is, a pixel apart (ui.c's ui_text)"""

    def __init__(self, data):
        self.data = data
        self.left, self.width = [], []
        for ch in range(96):
            cols = 0
            for b in data[ch * 8:ch * 8 + 8]:
                cols |= b
            lit = [i for i in range(8) if cols & (1 << i)]
            self.left.append(lit[0] if lit else 0)
            self.width.append(lit[-1] - lit[0] + 1 if lit else 3)

    def measure(self, s, scale=1):
        return (sum(self.width[ord(ch) - 32] + 1 for ch in s) - 1) * scale

    def write(self, pic, x, y, s, color, scale=1):
        for ch in s:
            i = ord(ch) - 32
            for row in range(8):
                bits = self.data[i * 8 + row] >> self.left[i]
                for col in range(self.width[i]):
                    if bits & (1 << col):
                        pic.fill(x + col * scale, y + row * scale, scale, scale, color)
            x += (self.width[i] + 1) * scale
        return x


def title(pic, x, y, letters, color, scale):
    """topscreen.c's title(): "DSiRPC" in its 5x7 letters, each as wide as it is"""
    for g in letters:
        cols = [c for c in range(5) if any(row[c] == "#" for row in g)]
        for j, row in enumerate(g):
            for c in range(cols[0], cols[-1] + 1):
                if row[c] == "#":
                    pic.fill(x + (c - cols[0]) * scale, y + j * scale, scale, scale, color)
        x += (cols[-1] - cols[0] + 2) * scale


def chip(pic, font, x, y, text, fill, ink, scale=1, width=None):
    """ui.c's ui_chip(): 12 high, the text 4 in (or made `width` wide, the
    text in the middle)"""
    w = (font.measure(text) + 8) * scale
    if width is None:
        width = w
    pic.fill(x, y, width, 12 * scale, fill)
    font.write(pic, x + (width - w) // (2 * scale) * scale + 4 * scale, y + 2 * scale, text, ink, scale)
    return width


def corner_inset(y, h, corner):
    """How far in row y of a shape with stepped corners starts"""
    n = len(corner)
    return corner[y] if y < n else corner[h - 1 - y] if y >= h - n else 0


def stepped(w, h, corner):
    """An SVG path: a w x h rectangle with stepped corners (corner: each
    row's inset, from the top)"""
    n = len(corner)
    d = [f"M{corner[0]} 0H{w - corner[0]}"]
    for y in range(n):
        d.append(f"V{y + 1}H{w - corner[y + 1] if y + 1 < n else w}")
    d.append(f"V{h - n}")
    for y in reversed(range(n)):
        d.append(f"H{w - corner[y]}V{h - y}")
    d.append(f"H{corner[0]}")
    for y in range(n):
        d.append(f"V{h - 1 - y}H{corner[y + 1] if y + 1 < n else 0}")
    d.append(f"V{n}")
    for y in reversed(range(n)):
        d.append(f"H{corner[y]}V{y}")
    return "".join(d) + "Z"


def outline(w, h, corner, edge, color):
    """The pixels within edge of a shape with stepped corners, around it"""
    pic = Picture(w + 2 * edge, h + 2 * edge)

    def inside(x, y):
        return 0 <= y < h and corner_inset(y, h, corner) <= x < w - corner_inset(y, h, corner)

    for yy in range(pic.h):
        for xx in range(pic.w):
            x, y = xx - edge, yy - edge
            if not inside(x, y) and any(inside(x + i, y + j) for i in range(-edge, edge + 1)
                                        for j in range(-edge, edge + 1)):
                pic.rows[yy][xx] = color
    return pic


# ---------------------------------------------------------------------------
# The banner

def banner(art):
    """The banner's art and, apart, the tagline: a picture TEXT_RES times as
    fine, to put at (x, y)"""
    font = Font(art.font)
    bar_h, scale, margin, h = 20, 4, 28, 192
    dsi_w, dsi_h = len(art.dsi[0]) * scale, len(art.dsi) * scale
    # The tagline in the launcher's font, each of its pixels 7 of the
    # layer's (3.5 of the art's: 28 high, a little under the 32 it was at
    # 4x), its shadow one of them down and right
    px, line_h, line_gap, shadow = 7, 8 * 7, 4 * TEXT_RES, 7
    text_w = (max(font.measure(line, px) for line in TAGLINE) + shadow + TEXT_RES - 1) // TEXT_RES
    text_h = (len(TAGLINE) * line_h + (len(TAGLINE) - 1) * line_gap + shadow + TEXT_RES - 1) // TEXT_RES
    # The chips: the launcher's, the text 4 in, each column as wide as its
    # widest; laid out 12 high, but drawn 13 high with the text a pixel
    # lower (a pixel more room above it), so nothing else moves
    rows, gap, chips_gap = (len(FEATURES) + 1) // 2, 4, 12
    columns = [FEATURES[:rows], FEATURES[rows:]]
    col_w = [max(font.measure(name) + 8 for name, _ in col) for col in columns]
    chips_w, chips_h = sum(col_w) + 6, rows * 12 + (rows - 1) * gap
    tx = margin + dsi_w + scale + margin
    w = tx + max(text_w, chips_w) + margin
    pic = Picture(w, h)

    # The header bar, its name (topscreen.c's draw_bar)
    pic.fill(0, 0, w, bar_h, art.rgb("C_BAR"))
    pic.fill(0, 0, w, 1, art.rgb("C_BAR_HI"))
    pic.fill(0, bar_h - 1, w, 1, art.rgb("C_BAR_LO"))
    title(pic, 12, 5, art.title, art.rgb("C_TEXT_SHADOW"), 2)
    title(pic, 10, 3, art.title, art.rgb("C_TEXT"), 2)

    # The DSi, its shadow and the lines on its bottom screen (draw_dsi), as
    # the classic look draws it: 4x, in the middle of the screen's height
    x, y = margin, bar_h + (h - bar_h - dsi_h - scale) // 2
    shadow_colors = {k: art.rgb("C_SHADOW") for k in art.dsi_colors}
    pic.art(x + scale, y + scale, art.dsi, shadow_colors, scale)
    pic.art(x, y, art.dsi, art.dsi_colors, scale)
    x0, x1 = art.lines_x
    for top, bottom in art.lines:
        pic.fill(x + x0, y + top, x1 - x0, max(1, bottom - top), art.rgb("C_LINES"))
    dsi = (x, y)

    # The tagline and the chips beside it, in the middle of the height
    ty = bar_h + (h - bar_h - text_h - chips_gap - chips_h) // 2
    text = Picture(text_w * TEXT_RES, text_h * TEXT_RES)
    for i, line in enumerate(TAGLINE):
        ly = i * (line_h + line_gap)
        font.write(text, shadow, ly + shadow, line, art.rgb("C_TEXT_SHADOW"), px)
        font.write(text, 0, ly, line, art.rgb("C_TEXT"), px)
    cx, cy = tx, ty + text_h + chips_gap
    for col, cw in zip(columns, col_w):
        for r, (name, ink) in enumerate(col):
            y = cy + r * (12 + gap)
            pic.fill(cx, y, cw, 13, art.rgb("C_BAR"))
            pic.fill(cx, y, cw, 1, art.rgb("C_BAR_HI"))
            pic.fill(cx, y + 12, cw, 1, art.rgb("C_BAR_LO"))
            font.write(pic, cx + 4, y + 3, name, art.rgb(ink))
        cx += cw + 6

    return pic, dsi, font, (tx, ty, text)


def status(art, font, w, text, tone):
    """The bar's right end (draw_status): the chip and the battery left of it"""
    pic = Picture(w, 20)
    fill, ink = (art.rgb("C_" + tone), art.rgb("C_" + tone + "_DARK"))
    x = w - 6 - (font.measure(text) + 8)
    chip(pic, font, x, 4, text, fill, ink)
    x -= 6 + 14
    pic.art(x, 6, art.battery, {"1": art.rgb("C_LINES")})
    pic.fill(x + 2, 8, 8, 4, art.rgb("C_GREEN"))
    return pic


def keyframes(name, prop, values, total):
    """CSS keyframes for values [(seconds, value)], each held until the next"""
    frames = [f"{t / total * 100:g}% {{ {prop}: {v} }}" for t, v in values]
    frames.append(f"100% {{ {prop}: {values[-1][1]} }}")
    return f"@keyframes {name} {{ {' '.join(frames)} }}"


def banner_svg(art):
    pic, (dx, dy), font, (tx, ty, text) = banner(art)
    w, h, scale = pic.w, pic.h, 4
    total = CONNECTING_S + CONNECTED_S
    amber, green, grey = (hexrgb(art.rgb(n)) for n in ("C_AMBER", "C_GREEN", "WIFI_ON"))

    # The Wi-Fi sign's parts (the dot, then the arcs from the smallest out),
    # lit in turn while it connects, as topscreen.c's top_animate()
    css = [".drift { animation: drift %.3fs steps(16) infinite; }" % DRIFT_S,
           "@keyframes drift { to { transform: translate(16px, 16px); } }"]
    parts = []
    for p in range(4):
        values, slots = [], round(CONNECTING_S / ARC_S)
        for s in range(slots):
            c = amber if p < 1 + s % 4 else grey
            if not values or values[-1][1] != c:
                values.append((s * ARC_S, c))
        values.append((CONNECTING_S, green))
        css.append(keyframes(f"wifi{p}", "fill", values, total))
        css.append(f".wifi{p} {{ animation: wifi{p} {total:g}s step-end infinite; }}")
        d = "".join(f"M{dx + x * scale} {dy + y * scale}h{scale}v{scale}h-{scale}z"
                    for x, y, part in art.wifi if part == p)
        parts.append(f'<path class="wifi{p}" fill="{green}" d="{d}"/>')

    # The status: Connecting, then Connected
    connecting = status(art, font, w, "Connecting", "AMBER")
    connected = status(art, font, w, "Connected", "GREEN")
    css.append(keyframes("connecting", "opacity", [(0, 1), (CONNECTING_S, 0)], total))
    css.append(keyframes("connected", "opacity", [(0, 0), (CONNECTING_S, 1)], total))
    css.append(f".connecting {{ animation: connecting {total:g}s step-end infinite; }}")
    css.append(f".connected {{ animation: connected {total:g}s step-end infinite; }}")
    css.append("@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }")

    # The diamonds: topscreen.c's make_pattern(), a 16x16 cell
    back, tile, dot = (hexrgb(art.rgb(n)) for n in ("C_BACKDROP", "C_TILE", "C_DOT"))
    cell = [f'<rect width="16" height="16" fill="{back}"/>']
    for i in range(4):
        cell.append(f'<rect x="{8 - i}" y="{4 + i}" width="{2 * i + 1}" height="1" fill="{tile}"/>')
        cell.append(f'<rect x="{8 - i}" y="{11 - i}" width="{2 * i + 1}" height="1" fill="{tile}"/>')
    cell.append(f'<rect x="8" y="7" width="1" height="1" fill="{dot}"/>')

    # A dark edge around it all, its corners stepped like the DSi's
    edge, corner = 2, [4, 2, 1, 1]
    border = outline(w, h, corner, edge, art.rgb("C_BAR_LO"))
    label = "DSiRPC: " + " ".join(TAGLINE) + " " + "; ".join(name for name, _ in FEATURES) + "."
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {border.w} {border.h}" '
           f'width="{border.w * 2}" height="{border.h * 2}" shape-rendering="crispEdges" '
           f'role="img" aria-label="{label}">',
           f"<title>{label}</title>",
           "<style>\n" + "\n".join(css) + "\n</style>",
           '<defs><pattern id="diamonds" width="16" height="16" patternUnits="userSpaceOnUse">'
           + "".join(cell) + "</pattern>"
           f'<clipPath id="screen"><path d="{stepped(w, h, corner)}"/></clipPath></defs>']
    svg += border.paths()
    svg += [f'<g transform="translate({edge} {edge})" clip-path="url(#screen)">',
            f'<rect class="drift" x="-16" y="-16" width="{w + 32}" height="{h + 32}" fill="url(#diamonds)"/>']
    svg += pic.paths()
    svg += [f'<g transform="translate({tx} {ty}) scale({1 / TEXT_RES:g})">'] + text.paths() + ["</g>"]
    svg += parts
    svg += ['<g class="connecting" opacity="0">'] + connecting.paths() + ["</g>"]
    svg += ['<g class="connected">'] + connected.paths() + ["</g>"]
    svg += ["</g>", "</svg>"]

    # A still, connected, to look at
    still = border
    for y in range(h):
        inset = corner_inset(y, h, corner)
        for x in range(inset, w - inset):
            c = connected.rows[y][x] if y < connected.h else None
            if c is None:
                c = pic.rows[y][x]
            if c is None:
                cx, cy = x % 16, y % 16
                d = abs(cx - 8)
                c = art.rgb("C_DOT") if (cx, cy) == (8, 7) else art.rgb("C_TILE") if (
                    4 <= cy <= 7 and d <= cy - 4) or (8 <= cy <= 11 and d <= 11 - cy) else art.rgb("C_BACKDROP")
            still.rows[y + edge][x + edge] = c
    for x, y, part in art.wifi:
        still.fill(edge + dx + x * scale, edge + dy + y * scale, scale, scale, art.rgb("C_GREEN"))
    return "\n".join(svg) + "\n", still, (tx + edge, ty + edge, text)


# ---------------------------------------------------------------------------
# The icons

def tile(art, rows, palette, scale=2):
    """A main screen tile, small: the icon on a panel, 26x26"""
    size = 26
    pic = Picture(size, size)
    pic.fill(0, 0, size, size, art.rgb("UI_EDGE"))
    pic.fill(1, 1, size - 2, size - 2, art.rgb("UI_PANEL"))
    pic.fill(1, 1, size - 2, 1, art.rgb("UI_PANEL_HI"))
    pic.fill(1, size - 2, size - 2, 1, art.rgb("UI_PANEL_LO"))
    for x, y in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
        pic.rows[y][x] = None
    w, h = max(len(r) for r in rows) * scale, len(rows) * scale
    pic.art((size - w) // 2, (size - h) // 2, rows, palette, scale)
    return pic


def icons(art):
    """The README's sections' icons, by name"""
    c = art.rgb

    def launcher_tile(name):
        keys = art.tile_colors[name]
        return tile(art, art.tiles[name], {str(i + 1): (c(k) if k != "0" else None) for i, k in enumerate(keys)})

    # The DSi's Wi-Fi sign, connected
    xs, ys = [x for x, _, _ in art.wifi], [y for _, y, _ in art.wifi]
    sign = [["."] * (max(xs) - min(xs) + 1) for _ in range(max(ys) - min(ys) + 1)]
    for x, y, _ in art.wifi:
        sign[y - min(ys)][x - min(xs)] = "1"
    # The connecting screen's check box needs no panel: it's one
    check = Picture(26, 26)
    check.art(1, 1, art.check, {"1": c("UI_GREEN"), "2": c("UI_GREEN_DARK")}, 2)
    return {
        "games": launcher_tile("GAMES"),
        "settings": launcher_tile("SETTINGS"),
        "star": tile(art, art.star, {"1": c("UI_AMBER")}),
        "bolt": tile(art, art.bolt, {"1": c("UI_AMBER")}),
        "wifi": tile(art, ["".join(r) for r in sign], {"1": c("UI_GREEN")}),
        "check": check,
        "prompt": tile(art, PROMPT, {"1": c("UI_GREEN"), "2": c("UI_TEXT")}),
        "flag": tile(art, FLAG, {"1": c("UI_ICON"), "2": c("UI_AMBER")}),
        "heart": tile(art, HEART, {"1": c("UI_RED"), "2": c("UI_TEXT")}),
        "page": tile(art, PAGE, {"1": c("UI_ICON"), "2": c("UI_PANEL"), "3": c("UI_DIM")}),
        "ball": tile(art, BALL, {"1": c("UI_RED"), "2": c("UI_TEXT"), "3": c("UI_EDGE")}),
    }


def icon_svg(pic):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {pic.w} {pic.h}" width="{pic.w}" '
            f'height="{pic.h}" shape-rendering="crispEdges" aria-hidden="true">')
    return "\n".join([head, *pic.paths(), "</svg>"]) + "\n"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"{os.path.relpath(path, REPO)}: {len(text) // 1024} KB")


def main():
    ap = argparse.ArgumentParser(description="Draw the README's banner and icons from the launcher's pixel art")
    ap.add_argument("--out", default=OUT, help="where they go (default docs/images)")
    ap.add_argument("--png", action="store_true", help="a still of each too, in renders/readme-art")
    args = ap.parse_args()
    art = Art()
    svg, still, (tx, ty, text) = banner_svg(art)
    write(os.path.join(args.out, "banner.svg"), svg)
    pictures = icons(art)
    for name, pic in sorted(pictures.items()):
        write(os.path.join(args.out, "icons", name + ".svg"), icon_svg(pic))
    if args.png:
        out = os.path.join(REPO, "renders", "readme-art")
        os.makedirs(out, exist_ok=True)
        back = art.rgb("C_BACKDROP")
        im = still.image(back)
        im = im.resize((im.width * TEXT_RES, im.height * TEXT_RES), 0)
        im.paste(text.image(back), (tx * TEXT_RES, ty * TEXT_RES), text.mask())
        im.save(os.path.join(out, "banner.png"))
        for name, pic in pictures.items():
            im = pic.image((255, 255, 255))
            im.resize((im.width * 4, im.height * 4), 0).save(os.path.join(out, name + ".png"))
        print(f"{os.path.relpath(out, REPO)}: the stills")


if __name__ == "__main__":
    main()
