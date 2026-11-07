"""
mkds_maps.py - lines Mario Kart DS's course art (Assets/MarioKartDS, the
Spriters Resource's top-down course maps) up with the game's world
coordinates, and writes the result to core/mkds_maps.py for the overlay's
race view (overlay/mkds.py):

    python tools/mkds_maps.py "Mario Kart DS (USA).nds"              core/mkds_maps.py
    python tools/mkds_maps.py "Mario Kart DS (USA).nds" --sheet DIR   and pictures to check it by
    python tools/mkds_maps.py "Mario Kart DS (USA).nds" --keep        the same placements, the decks
                                                                     and heights worked out again

It needs your own copy of the game (US, AMCE), and numpy (only this tool
does). From the game it reads each race course's checkpoints, the same ones
the console has in RAM during a race (core/mkds_reader.py): the course files
are data/Course/<course>.carc, an LZ77-compressed NARC holding
course_map.nkm, whose CPOI section is the checkpoints (0x24 bytes each, x1,
z1, x2, z2 in 20.12 fixed point first).

Every map turned out to be the course seen from above, x to the right and z
down, at about 12 world units a pixel, with the world's origin near the
middle of the picture. So for each course the tool looks for the scale
(10.5-14.5 units a pixel) and origin (within 70 pixels of the middle) that
put the line through the checkpoints' middles on the road: the colours under
that line should be ones that are rare in the rest of the picture (the
road's), which scores the Kullback-Leibler divergence of the line's colours
from the picture's. OVERRIDES has the ones that came out wrong, placed by
hand (by the finish line and the road's extent); --sheet draws each course's
checkpoints over its map so you can see.

The maps are the whole PNGs: they were cut down to the map itself once (no
credit strip, frame or second version), and placements are in their pixels.

Where the course crosses over itself (a bridge, a loop, a cannon's arc),
decks() finds it from the CPUs' path in the course file (course_map.nkm's
EPOI points, x, y and z, joined as its EPAT says): two stretches that cross on
the map at heights DECK_MIN or more apart. Each is kept with the stretch of
the upper path round it, so the overlay can draw racers up there over the
ones below (core/mkds_maps.py's DECKS). heights() keeps the course's height
at each checkpoint too (HEIGHTS), from the same path, for views that show
the course's ups and downs.
"""

import argparse
import math
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core.mkds_reader import COURSES  # noqa: E402

NUMPY_NOTE = "This tool needs numpy (pip install numpy); nothing else in DSiRPC does."

ART_DIR = os.path.join(REPO, "Assets", "MarioKartDS")
ART = "DS _ DSi - Mario Kart DS - Courses - {} Map.png"
OUT = os.path.join(REPO, "core", "mkds_maps.py")

# The course file -> its map's name in the art's file name
ART_NAMES = {
    "old_yoshi_gc": "GCN Yoshi Circuit", "old_baby_gc": "GCN Baby Park", "old_mario_sfc": "SNES Mario Circuit 1",
    "old_momo_64": "N64 Moo Moo Farm", "old_koopa_agb": "GBA Bowser Castle 2", "old_peach_agb": "GBA Peach Circuit",
    "old_luigi_gc": "GCN Luigi Circuit", "old_noko_sfc": "SNES Koopa Beach 2", "old_frappe_64": "N64 Frappe Snowland",
    "clock_course": "Tick-Tock Clock", "mansion_course": "Luigi's Mansion", "airship_course": "Airship Fortress",
    "cross_course": "Figure-8 Circuit", "bank_course": "Yoshi Falls", "old_hyudoro_64": "N64 Banshee Boardwalk",
    "ridge_course": "Shroom Ridge", "mario_course": "Mario Circuit", "garden_course": "Peach Gardens",
    "desert_course": "Desert Hills", "town_course": "Delfino Square", "rainbow_course": "Rainbow Road",
    "snow_course": "DK Pass", "beach_course": "Cheep-Cheep Beach", "koopa_course": "Bowser Castle",
    "pinball_course": "Waluigi Pinball", "stadium_course": "Wario Stadium", "old_donut_sfc": "SNES Donut Plains 1",
    "old_choco_64": "N64 Choco Mountain", "old_luigi_agb": "GBA Luigi Circuit", "old_kinoko_gc": "GCN Mushroom Bridge",
    "old_choco_sfc": "SNES Choco Island 2", "old_sky_agb": "GBA Sky Garden",
}
DECK_MIN = 80.0                                # world units between two stretches that cross: one's above
# Placed by hand: course -> (world units a pixel, origin x, origin y)
OVERRIDES = {
    "old_mario_sfc": (12.5, 333.0, 263.0),     # (the search sat it inside the road)
    "airship_course": (13.68, 255.9, 540.7),   # (its origin's below the map: outside the search)
    "stadium_course": (11.93, 372.4, 168.9),   # (its origin's 116 pixels right of the middle)
}


# -- the ROM ---------------------------------------------------------------------

def nds_files(rom):
    """{path: bytes} for every file in an NDS ROM's file system."""
    fnt, _, fat, fat_len = struct.unpack_from("<4I", rom, 0x40)
    alloc = [struct.unpack_from("<2I", rom, fat + i * 8) for i in range(fat_len // 8)]
    out = {}

    def walk(dir_id, path):
        sub, fid, _ = struct.unpack_from("<IHH", rom, fnt + (dir_id & 0xFFF) * 8)
        p = fnt + sub
        while rom[p]:
            t = rom[p]
            name = rom[p + 1:p + 1 + (t & 0x7F)].decode("latin1")
            p += 1 + (t & 0x7F)
            if t & 0x80:
                walk(struct.unpack_from("<H", rom, p)[0], path + name + "/")
                p += 2
            else:
                s, e = alloc[fid]
                out[path + name] = rom[s:e]
                fid += 1
    walk(0xF000, "")
    return out


def lz77(data):
    """Nintendo's LZ77 (type 0x10)."""
    size = struct.unpack_from("<I", data, 0)[0] >> 8
    out, p = bytearray(), 4
    while len(out) < size:
        flags = data[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                v = data[p] << 8 | data[p + 1]
                p += 2
                for _ in range((v >> 12) + 3):
                    out.append(out[-((v & 0xFFF) + 1)])
            else:
                out.append(data[p])
                p += 1
    return bytes(out)


def narc(data):
    """{name: bytes} for a NARC's top folder."""
    btaf = 0x10
    count = struct.unpack_from("<H", data, btaf + 8)[0]
    alloc = [struct.unpack_from("<2I", data, btaf + 12 + i * 8) for i in range(count)]
    btnf = btaf + struct.unpack_from("<I", data, btaf + 4)[0]
    gmif = btnf + struct.unpack_from("<I", data, btnf + 4)[0] + 8
    names = btnf + 8
    sub, fid, _ = struct.unpack_from("<IHH", data, names)
    out, q = {}, names + sub
    while data[q]:
        t = data[q]
        name = data[q + 1:q + 1 + (t & 0x7F)].decode("latin1")
        q += 1 + (t & 0x7F)
        if t & 0x80:
            q += 2
            continue
        s, e = alloc[fid]
        out[name] = data[gmif + s:gmif + e]
        fid += 1
    return out


def nkm_section(nkm, magic):
    """(the number of entries, where they start) of one of course_map.nkm's sections."""
    head = struct.unpack_from("<H", nkm, 6)[0]
    for off in struct.unpack_from(f"<{(head - 8) // 4}I", nkm, 8):
        p = head + off
        if nkm[p:p + 4] == magic:
            return struct.unpack_from("<I", nkm, p + 4)[0], p + 8
    return 0, 0


def checkpoints(nkm):
    """course_map.nkm's CPOI section -> [(x1, z1, x2, z2), ...]."""
    n, at = nkm_section(nkm, b"CPOI")
    return [tuple(v / 4096 for v in struct.unpack_from("<4i", nkm, at + i * 0x24)) for i in range(n)]


def course_files(rom_path):
    """{course file: its course_map.nkm} for the race courses in the ROM."""
    with open(rom_path, "rb") as f:
        rom = f.read()
    if rom[0xC:0x10] != b"AMCE":
        sys.exit(f"{rom_path} isn't Mario Kart DS (USA): its game code is {rom[0xC:0x10]!r}")
    files = nds_files(rom)
    return {name: narc(lz77(files[f"data/Course/{name}.carc"]))["course_map.nkm"] for name in ART_NAMES}


# -- where the course crosses over itself -----------------------------------------

def cpu_path(nkm):
    """The CPUs' path: ([(x, y, z), ...], [(point, the next point), ...]):
    EPOI's points (0x18 bytes, x y z first), joined in the runs EPAT gives
    (0xC bytes: the first point, how many, then up to three runs it leads on
    to, 0xFF for none)."""
    n, at = nkm_section(nkm, b"EPOI")
    pts = [tuple(v / 4096 for v in struct.unpack_from("<3i", nkm, at + i * 0x18)) for i in range(n)]
    m, pat = nkm_section(nkm, b"EPAT")
    runs = []
    for i in range(m):
        e = nkm[pat + i * 12:pat + i * 12 + 12]
        start, length = struct.unpack_from("<HH", e)
        runs.append((start, length, [b for b in e[4:7] if b != 0xFF]))
    links = []
    for start, length, after in runs:
        links += [(i, i + 1) for i in range(start, start + length - 1)]
        links += [(start + length - 1, runs[r][0]) for r in after if r < len(runs)]
    return pts, links


def _cross(a, b, c, d):
    """Where segments ab and cd cross on the map (x, z), as (t along ab, u along cd), or None."""
    rx, rz, sx, sz = b[0] - a[0], b[2] - a[2], d[0] - c[0], d[2] - c[2]
    den = rx * sz - rz * sx
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * sz - (c[2] - a[2]) * sx) / den
    u = ((c[0] - a[0]) * rz - (c[2] - a[2]) * rx) / den
    return (t, u) if 0 < t < 1 and 0 < u < 1 else None


def _stretch(pts, links, seg, t, reach):
    """The path from `reach` before the point t along `seg` to `reach` after
    it, as map points (x, z), every 50 units or so."""
    nxt, prv = {}, {}
    for a, b in links:
        nxt.setdefault(a, b)
        prv.setdefault(b, a)
    a, b = seg
    mid = tuple(pts[a][k] + (pts[b][k] - pts[a][k]) * t for k in (0, 2))

    def walk(frm, to, step):
        out, left, here = [], reach, mid
        while left > 0 and to is not None:
            there = (pts[to][0], pts[to][2])
            d = math.dist(here, there)
            if d >= left:
                f = left / d
                out.append((here[0] + (there[0] - here[0]) * f, here[1] + (there[1] - here[1]) * f))
                break
            out.append(there)
            left -= d
            here, frm, to = there, to, step.get(to)
        return out
    return [p for p in reversed(walk(b, a, prv))] + [mid] + walk(a, b, nxt)


def heights(nkm, cps):
    """The course's height at each checkpoint (world units, rounded): the
    CPUs' path point nearest its middle. Where the course crosses over
    itself two points can be about as near, at different heights: of the
    ones within 1.5 times the nearest's distance (or 400 units, a road's
    width, past it), the one nearest the last checkpoint's height."""
    pts, _ = cpu_path(nkm)
    if not pts:
        return ()
    out, last = [], None
    for x1, z1, x2, z2 in cps:
        mx, mz = (x1 + x2) / 2, (z1 + z2) / 2
        near = sorted((math.dist((mx, mz), (px, pz)), py) for px, py, pz in pts)
        close = [y for d, y in near if d <= max(1.5 * near[0][0], near[0][0] + 400)]
        y = close[0] if last is None else min(close, key=lambda c: abs(c - last))
        out.append(round(y))
        last = y
    return tuple(out)


def decks(nkm, cps):
    """The places the course crosses over itself: [(x, z, reach, the lower
    height, the upper, ((x, z), ...) the upper path round it), ...]. reach
    is how far from (x, z) counts as there, about the road's width: half the
    checkpoints' usual length, plus a bit."""
    pts, links = cpu_path(nkm)
    widths = sorted(math.dist((x1, z1), (x2, z2)) for x1, z1, x2, z2 in cps)
    reach = 0.6 * widths[len(widths) // 2] if widths else 300.0
    found = []
    for i, (a, b) in enumerate(links):
        for c, d in links[i + 1:]:
            if len({a, b, c, d}) < 4:
                continue
            hit = _cross(pts[a], pts[b], pts[c], pts[d])
            if not hit:
                continue
            t, u = hit
            y1 = pts[a][1] + (pts[b][1] - pts[a][1]) * t
            y2 = pts[c][1] + (pts[d][1] - pts[c][1]) * u
            if abs(y1 - y2) < DECK_MIN:
                continue
            x, z = pts[a][0] + (pts[b][0] - pts[a][0]) * t, pts[a][2] + (pts[b][2] - pts[a][2]) * t
            if any(math.dist((x, z), f[:2]) < reach for f in found):
                continue                                   # (the same crossing, by another stretch of path)
            upper = ((a, b), t) if y1 > y2 else ((c, d), u)
            line = _stretch(pts, links, upper[0], upper[1], 2 * reach)
            found.append((round(x), round(z), round(reach), round(min(y1, y2)), round(max(y1, y2)),
                          tuple((round(px), round(pz)) for px, pz in line)))
    return found


# -- the fit ---------------------------------------------------------------------

def midline(cps, step=5.0):
    """Points every `step` world units along the line through the checkpoints' middles."""
    mids = [((x1 + x2) / 2, (z1 + z2) / 2) for x1, z1, x2, z2 in cps]
    out = []
    for i, (ax, az) in enumerate(mids):
        bx, bz = mids[(i + 1) % len(mids)]
        n = max(1, int(math.hypot(bx - ax, bz - az) / step))
        out += [(ax + (bx - ax) * k / n, az + (bz - az) * k / n) for k in range(n)]
    return out


def fit(image, cps):
    """(score, world units a pixel, origin x, origin y) that best puts the
    checkpoints' middle line on the road in `image`."""
    try:
        import numpy as np
    except ImportError:
        sys.exit(NUMPY_NOTE)
    a = np.asarray(image.convert("RGB")).astype(np.int32)
    h, w, _ = a.shape
    q = (a[..., 0] >> 4) * 256 + (a[..., 1] >> 4) * 16 + (a[..., 2] >> 4)    # 4096 colour bins
    hist = np.bincount(q.ravel(), minlength=4096).astype(float) + 1
    log_hist = np.log(hist / hist.sum())
    line = np.array(midline(cps))

    def score(k, ox, oy):
        px, py = (line[:, 0] / k + ox).astype(int), (line[:, 1] / k + oy).astype(int)
        if px.min() < 0 or py.min() < 0 or px.max() >= w or py.max() >= h:
            return None
        p = np.bincount(q[py, px], minlength=4096).astype(float)
        p /= p.sum()
        nz = p > 0
        return float((p[nz] * (np.log(p[nz]) - log_hist[nz])).sum())

    best = (-1.0, 12.0, w / 2, h / 2)
    for k in np.linspace(10.5, 14.5, 41):
        for ox in np.arange(w / 2 - 70, w / 2 + 71, 2.0):
            for oy in np.arange(h / 2 - 70, h / 2 + 71, 2.0):
                s = score(k, ox, oy)
                if s is not None and s > best[0]:
                    best = (s, k, ox, oy)
    for it in range(1, 4):                        # then finer, around the best
        _, k0, x0, y0 = best
        for k in np.linspace(k0 - 0.1 / it, k0 + 0.1 / it, 9):
            for ox in np.linspace(x0 - 2 / it, x0 + 2 / it, 9):
                for oy in np.linspace(y0 - 2 / it, y0 + 2 / it, 9):
                    s = score(k, ox, oy)
                    if s is not None and s > best[0]:
                        best = (s, k, ox, oy)
    return best


def sheet(results, cps, course_decks, path):
    """Every course's map with its checkpoints drawn on, to check the fits
    by, and its decks' upper paths in cyan."""
    from PIL import Image, ImageDraw
    cell = 300
    names = list(results)
    out = Image.new("RGB", (cell * 4, (cell + 14) * ((len(names) + 3) // 4)), "white")
    label = ImageDraw.Draw(out)
    for i, name in enumerate(names):
        art, k, ox, oy = results[name]
        im = Image.open(os.path.join(ART_DIR, ART.format(art))).convert("RGB")
        d = ImageDraw.Draw(im)
        to = lambda x, z: (x / k + ox, z / k + oy)   # noqa: E731
        for x1, z1, x2, z2 in cps[name]:
            d.line([to(x1, z1), to(x2, z2)], fill=(255, 0, 255))
        mids = [to((x1 + x2) / 2, (z1 + z2) / 2) for x1, z1, x2, z2 in cps[name]]
        d.line(mids + mids[:1], fill=(255, 255, 0), width=2)
        d.ellipse([mids[0][0] - 4, mids[0][1] - 4, mids[0][0] + 4, mids[0][1] + 4], outline=(255, 0, 0), width=2)
        for x, z, reach, _, _, upper in course_decks.get(name, ()):
            d.line([to(px, pz) for px, pz in upper], fill=(0, 255, 255), width=3)
            r = reach / k
            cx, cz = to(x, z)
            d.ellipse([cx - r, cz - r, cx + r, cz + r], outline=(0, 255, 255))
        im.thumbnail((cell, cell))
        x, y = i % 4 * cell, i // 4 * (cell + 14)
        out.paste(im, (x, y + 14))
        label.text((x, y), name, fill="black")
    out.save(path)
    print(path)


def write(results, cps, course_decks, course_heights):
    lines = [
        '"""',
        "mkds_maps.py - where Mario Kart DS's course art (Assets/MarioKartDS) has",
        "the game's world: written by tools/mkds_maps.py from the courses'",
        "checkpoints in the game's own files (see there). Don't edit it by hand:",
        "change the tool's OVERRIDES and run it again.",
        "",
        "MAPS: course file (core/mkds_reader.py's COURSES) -> (the map's name in",
        "its file name, world units a pixel k, the world's origin in the map",
        "(ox, oy), and the middle of checkpoint 0 (the finish line) in the",
        "course file).",
        "A point (x, z) in the world is at (ox + x / k, oy + z / k) in the map. The",
        "overlay checks the checkpoint the console has against the last, so a",
        "course the console has otherwise (mirrored, say) isn't drawn on the",
        "wrong map.",
        "",
        "DECKS: course file -> where it crosses over itself, [(x, z, how far",
        "from there counts as there, the lower deck's height, the upper's, the",
        "upper path round it ((x, z), ...)), ...], in world units. A racer that",
        "near a crossing is on the upper deck when its height is nearer the",
        "upper one.",
        "",
        "HEIGHTS: course file -> the course's height at each checkpoint, in",
        "the checkpoints' order (world units, from the CPUs' path).",
        '"""',
        "",
        'ART = "' + ART + '"',
        "",
        "MAPS = {",
    ]
    for name, (art, k, ox, oy) in results.items():
        x1, z1, x2, z2 = cps[name][0]
        finish = (round((x1 + x2) / 2), round((z1 + z2) / 2))
        lines.append(f"    {name!r}: ({art!r}, {k:.3f}, {ox:.1f}, {oy:.1f}, {finish!r}),")
    lines += ["}", "", "DECKS = {"]
    for name, found in course_decks.items():
        if found:
            lines.append(f"    {name!r}: (")
            lines += [f"        {deck!r}," for deck in found]
            lines.append("    ),")
    lines += ["}", "", "HEIGHTS = {"]
    lines += [f"    {name!r}: {tuple(h)!r}," for name, h in course_heights.items() if h]
    lines.append("}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(OUT)


def main():
    from PIL import Image
    ap = argparse.ArgumentParser(description="Line Mario Kart DS's course art up with the game's world")
    ap.add_argument("rom", help="your Mario Kart DS (USA) ROM")
    ap.add_argument("--sheet", metavar="DIR", help="also draw the checkpoints over the maps there, to check")
    ap.add_argument("--only", nargs="*", help="place just these course files again (the rest keep theirs)")
    ap.add_argument("--keep", action="store_true", help="place none again: keep core/mkds_maps.py's placements")
    args = ap.parse_args()
    nkms = course_files(args.rom)
    cps = {name: checkpoints(nkm) for name, nkm in nkms.items()}
    kept = {}
    if args.only or args.keep:
        from core.mkds_maps import MAPS
        kept = {n: m[:4] for n, m in MAPS.items()}
    files = {f for _, f in COURSES.values()}
    results, course_decks, course_heights = {}, {}, {}
    for name, art in ART_NAMES.items():
        if name not in files:
            continue
        if name in kept and (args.keep or name not in args.only):
            _, k, ox, oy = kept[name]
        elif name in OVERRIDES:
            k, ox, oy = OVERRIDES[name]
            print(f"{name}: {k:.2f} units a pixel, origin ({ox:.0f}, {oy:.0f}) (by hand)")
        else:
            score, k, ox, oy = fit(Image.open(os.path.join(ART_DIR, ART.format(art))), cps[name])
            print(f"{name}: {k:.2f} units a pixel, origin ({ox:.0f}, {oy:.0f}), score {score:.2f}", flush=True)
        results[name] = (art, float(k), float(ox), float(oy))
        course_decks[name] = decks(nkms[name], cps[name])
        course_heights[name] = heights(nkms[name], cps[name])
        if course_decks[name]:
            print(f"{name}: crosses over itself at " + ", ".join(f"({d[0]}, {d[1]})" for d in course_decks[name]))
    write(results, cps, course_decks, course_heights)
    if args.sheet:
        os.makedirs(args.sheet, exist_ok=True)
        names = list(results)
        for i in range(0, len(names), 16):
            sheet({n: results[n] for n in names[i:i + 16]}, cps, course_decks,
                  os.path.join(args.sheet, f"mkds-maps-{i // 16 + 1}.png"))


if __name__ == "__main__":
    main()
