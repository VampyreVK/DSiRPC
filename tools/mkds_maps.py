"""
mkds_maps.py - lines Mario Kart DS's course art (Assets/MarioKartDS, the
Spriters Resource's top-down course maps) up with the game's world
coordinates, and writes the result to core/mkds_maps.py for the overlay's
race view (overlay/mkds.py):

    python tools/mkds_maps.py "Mario Kart DS (USA).nds"              core/mkds_maps.py
    python tools/mkds_maps.py "Mario Kart DS (USA).nds" --sheet DIR   and pictures to check it by

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

Some sheets hold more than one map (the tides of Koopa Beach, the clock's
two states, a demo version of Mario Circuit): CROPS picks the one to use.
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
# The map to use on sheets with more than one (left, top, right, bottom);
# the rest are the sheet in 512-pixel squares, less the ripper's credit strip
CROPS = {
    "old_noko_sfc": (0, 0, 512, 512),          # (low tide; the other two are the tide coming in)
    "clock_course": (0, 0, 512, 512),
    "airship_course": (0, 518, 520, 1036),     # (the lower one, the whole airship)
    "mario_course": (521, 22, 1034, 535),      # ("Final"; the left one is the kiosk demo's)
}
# Placed by hand: course -> (world units a pixel, origin x, origin y)
OVERRIDES = {
    "old_mario_sfc": (12.5, 333.0, 263.0),     # (the search sat it inside the road)
    "airship_course": (13.68, 259.9, 542.7),   # (its origin's below the map: outside the search)
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


def checkpoints(nkm):
    """course_map.nkm's CPOI section -> [(x1, z1, x2, z2), ...]."""
    head = struct.unpack_from("<H", nkm, 6)[0]
    for off in struct.unpack_from(f"<{(head - 8) // 4}I", nkm, 8):
        p = head + off
        if nkm[p:p + 4] == b"CPOI":
            n = struct.unpack_from("<I", nkm, p + 4)[0]
            return [tuple(v / 4096 for v in struct.unpack_from("<4i", nkm, p + 8 + i * 0x24)) for i in range(n)]
    return []


def course_checkpoints(rom_path):
    """{course file: checkpoints} for the race courses in the ROM."""
    with open(rom_path, "rb") as f:
        rom = f.read()
    if rom[0xC:0x10] != b"AMCE":
        sys.exit(f"{rom_path} isn't Mario Kart DS (USA): its game code is {rom[0xC:0x10]!r}")
    files = nds_files(rom)
    return {name: checkpoints(narc(lz77(files[f"data/Course/{name}.carc"]))["course_map.nkm"])
            for name in ART_NAMES}


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


def crop_of(name, size):
    w, h = size
    return CROPS.get(name) or (0, 0, min(w, 512 * max(1, round(w / 512))), min(h, 512 * max(1, round(h / 512))))


def sheet(results, cps, path):
    """Every course's map with its checkpoints drawn on, to check the fits by."""
    from PIL import Image, ImageDraw
    cell = 300
    names = list(results)
    out = Image.new("RGB", (cell * 4, (cell + 14) * ((len(names) + 3) // 4)), "white")
    label = ImageDraw.Draw(out)
    for i, name in enumerate(names):
        art, crop, k, ox, oy = results[name]
        im = Image.open(os.path.join(ART_DIR, ART.format(art))).convert("RGB").crop(crop)
        d = ImageDraw.Draw(im)
        to = lambda x, z: (x / k + ox, z / k + oy)   # noqa: E731
        for x1, z1, x2, z2 in cps[name]:
            d.line([to(x1, z1), to(x2, z2)], fill=(255, 0, 255))
        mids = [to((x1 + x2) / 2, (z1 + z2) / 2) for x1, z1, x2, z2 in cps[name]]
        d.line(mids + mids[:1], fill=(255, 255, 0), width=2)
        d.ellipse([mids[0][0] - 4, mids[0][1] - 4, mids[0][0] + 4, mids[0][1] + 4], outline=(255, 0, 0), width=2)
        im.thumbnail((cell, cell))
        x, y = i % 4 * cell, i // 4 * (cell + 14)
        out.paste(im, (x, y + 14))
        label.text((x, y), name, fill="black")
    out.save(path)
    print(path)


def write(results, cps):
    lines = [
        '"""',
        "mkds_maps.py - where Mario Kart DS's course art (Assets/MarioKartDS) has",
        "the game's world: written by tools/mkds_maps.py from the courses'",
        "checkpoints in the game's own files (see there). Don't edit it by hand:",
        "change the tool's OVERRIDES and run it again.",
        "",
        "MAPS: course file (core/mkds_reader.py's COURSES) -> (the map's name in",
        "its file name, the part of the sheet that's the map (left, top, right,",
        "bottom), world units a pixel k, the world's origin in that part (ox, oy),",
        "and the middle of checkpoint 0 (the finish line) in the course file).",
        "A point (x, z) in the world is at (ox + x / k, oy + z / k) in the map. The",
        "overlay checks the checkpoint the console has against the last, so a",
        "course the console has otherwise (mirrored, say) isn't drawn on the",
        "wrong map.",
        '"""',
        "",
        'ART = "' + ART + '"',
        "",
        "MAPS = {",
    ]
    for name, (art, crop, k, ox, oy) in results.items():
        x1, z1, x2, z2 = cps[name][0]
        finish = (round((x1 + x2) / 2), round((z1 + z2) / 2))
        lines.append(f"    {name!r}: ({art!r}, {tuple(crop)!r}, {k:.3f}, {ox:.1f}, {oy:.1f}, {finish!r}),")
    lines.append("}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(OUT)


def main():
    from PIL import Image
    ap = argparse.ArgumentParser(description="Line Mario Kart DS's course art up with the game's world")
    ap.add_argument("rom", help="your Mario Kart DS (USA) ROM")
    ap.add_argument("--sheet", metavar="DIR", help="also draw the checkpoints over the maps there, to check")
    ap.add_argument("--only", nargs="*", help="just these course files (the rest stay as they are)")
    args = ap.parse_args()
    cps = course_checkpoints(args.rom)
    results = {}
    if args.only:
        from core.mkds_maps import MAPS
        results = {n: m[:5] for n, m in MAPS.items()}
    files = {f for _, f in COURSES.values()}
    for name, art in ART_NAMES.items():
        if name not in files or (args.only and name not in args.only):
            continue
        im = Image.open(os.path.join(ART_DIR, ART.format(art)))
        crop = crop_of(name, im.size)
        if name in OVERRIDES:
            k, ox, oy = OVERRIDES[name]
            print(f"{name}: {k:.2f} units a pixel, origin ({ox:.0f}, {oy:.0f}) (by hand)")
        else:
            score, k, ox, oy = fit(im.crop(crop), cps[name])
            print(f"{name}: {k:.2f} units a pixel, origin ({ox:.0f}, {oy:.0f}), score {score:.2f}", flush=True)
        results[name] = (art, crop, float(k), float(ox), float(oy))
    write(results, cps)
    if args.sheet:
        os.makedirs(args.sheet, exist_ok=True)
        names = list(results)
        for i in range(0, len(names), 16):
            sheet({n: results[n] for n in names[i:i + 16]}, cps, os.path.join(args.sheet, f"mkds-maps-{i // 16 + 1}.png"))


if __name__ == "__main__":
    main()
