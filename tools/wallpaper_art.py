"""Draw the README's banner from the launcher's pixel art."""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from helpers import REPO, launcher_ui as lui  # noqa: E402

SOURCE = os.path.join(REPO, "launcher", "source")
OUT = os.path.join(REPO, "docs", "images")

DRIFT_S = 16 * 7 / 59.83                # the diamonds: a pixel every 7 frames, 16 to a cell


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


def colors(src, name):
    """A table of { r, g, b } by designated entry, {entry's first name: rgb}"""
    return {key: (int(r), int(g), int(b)) for key, r, g, b in
            re.findall(r"\[\s*(\w+)[^\]]*\]\s*=\s*\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", block(src, name))}


class Art:
    """Everything the README's art takes from the launcher"""

    def __init__(self):
        top = read("topscreen.c")
        self.top = colors(top, "rgb")
        self.top.update({"C_" + k[2:]: v for k, v in colors(top, "modern_rgb").items()})
        hexes = re.findall(r"0x([0-9A-Fa-f]{2})", block(open(os.path.join(REPO, "tests", "c", "ui", "font.h")).read(),
                                                         "default_font"))
        self.font = bytes(int(h, 16) for h in hexes)
        letters = strings(top, "TITLE")
        self.title = [letters[i:i + 7] for i in range(0, len(letters), 7)]
        self.battery = strings(top, "BATTERY")
        rgb = {k: v for k, v in re.findall(r"#define\s+(\w+)\s+RGB\((\d+, \d+, \d+)\)", top)}
        self.top_rgb = {k: tuple(int(c) for c in v.split(", ")) for k, v in rgb.items()}

    def rgb(self, name):
        """A color by the launcher's name for it (UI_ for the bottom screen's, C_ the top's)"""
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
    """The 16:9 banner's header and background."""
    font = Font(art.font)
    bar_h, w, h = 20, 316, 176
    pic = Picture(w, h)

    # The header bar, its name (topscreen.c's draw_bar)
    pic.fill(0, 0, w, bar_h, art.rgb("C_BAR"))
    pic.fill(0, 0, w, 1, art.rgb("C_BAR_HI"))
    pic.fill(0, bar_h - 1, w, 1, art.rgb("C_BAR_LO"))
    title(pic, 12, 5, art.title, art.rgb("C_TEXT_SHADOW"), 2)
    title(pic, 10, 3, art.title, art.rgb("C_TEXT"), 2)

    return pic, font


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


def banner_svg(art):
    pic, font = banner(art)
    w, h = pic.w, pic.h
    connected = status(art, font, w, "Connected", "GREEN")
    css = [".drift { animation: drift %.3fs steps(16) infinite; }" % DRIFT_S,
           "@keyframes drift { to { transform: translate(16px, 16px); } }"]

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
    label = "DSiRPC"
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
    svg += connected.paths()
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
    return "\n".join(svg) + "\n", still


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"{os.path.relpath(path, REPO)}: {len(text) // 1024} KB")


def main():
    ap = argparse.ArgumentParser(description="Draw the README's banner from the launcher's pixel art")
    ap.add_argument("--out", default=OUT, help="where they go (default docs/images)")
    ap.add_argument("--png", action="store_true", help="also save a still in renders/readme-art")
    args = ap.parse_args()
    art = Art()
    svg, still = banner_svg(art)
    write(os.path.join(args.out, "16-9-wallpaper.svg"), svg)
    if args.png:
        out = os.path.join(REPO, "renders", "readme-art")
        os.makedirs(out, exist_ok=True)
        back = art.rgb("C_BACKDROP")
        im = still.image(back)
        im.save(os.path.join(out, "banner.png"))
        print(f"{os.path.relpath(out, REPO)}: the stills")


if __name__ == "__main__":
    main()
