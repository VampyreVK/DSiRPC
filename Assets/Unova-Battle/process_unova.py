"""
process_unova.py - makes Pokemon Black and White's Discord images: every
Pokemon (and its shiny) standing on each of the battle view's turfs, and
Hilbert and Hilda walking on them, as small, optimised animated GIFs.

    python Assets/Unova-Battle/process_unova.py            # Unova's Pokemon (494-649)
    python Assets/Unova-Battle/process_unova.py 1-649      # any range
    python Assets/Unova-Battle/process_unova.py trainers   # only Hilbert and Hilda

Writes (next to the other Assets folders, served by GitHub Pages):

    Assets/Unova-Battle/<turf>/<id>.gif         a foe on that turf
    Assets/Unova-Battle-Shiny/<turf>/<id>.gif   the same, shiny
    Assets/Unova-Trainer/<turf>/<Hilbert|Hilda>-<Down|Left|Right|Up>.gif   walking
        ... -Run.gif, -Bike.gif (riding), -BikeStop.gif and -Stand.gif (still)

<turf> is one of the battle platforms core/bw_data.terrain() picks (grass,
sand, snow, water, cave, indoor), drawn by overlay/unova_backdrop.py in its
day look. Only Black and White's own Pokemon (494-649) are made by default:
the older ones would add about 600 MB, so the presence shows Platinum's
dioramas for them (rpc/bw_presence.py). The
Pokemon come from Assets/Pokemon-Overworld and Shiny-Pokemon-Overworld (the
animated front sprites, drawn at 2x and facing right): halved to their real
pixels and mirrored to face left like a foe, then stood on the turf with
their feet at y=126 of a 160x160 canvas, like Platinum's dioramas. The
trainers come from Assets/Trainer-Overworld's sheets (walking, running, on
the bike), drawn bigger (TRAINER_SCALE) to fill Discord's round picture.

The GIFs are kept small, and written by save_gif() itself: one palette for
every frame, the first frame whole and after it only the pixels that
change. Where the Pokemon moves away, the frame before is cleared after
it's shown (disposal 2, just its own rectangle) so nothing leaves a trail,
and the turf around it is stored once. Needs Pillow, numpy and pygame-ce.
"""

import os
import struct
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(ASSETS))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
from PIL import Image, ImageOps, ImageSequence  # noqa: E402

CANVAS = 160
FEET_Y = 126
# The trainers are drawn 3.5x their own pixels and stand a little higher, so
# with the turf they fill Discord's round picture (nothing outside a circle
# 2 px inside the canvas, for any gait, direction or frame).
TRAINER_SCALE, TRAINER_FEET_Y = 3.5, 120
TURF_W, TURF_H = 136, 34          # the turf's top ellipse
TURFS = ['grass', 'sand', 'snow', 'water', 'cave', 'indoor']   # core/bw_data.terrain()'s platforms
DIRECTIONS = ['Down', 'Left', 'Right', 'Up']
TRANSPARENT = 255                  # palette index kept for see-through pixels

_turfs = {}


def turf(kind):
    """The turf (with its shadow) as a PIL image, drawn by the overlay's code."""
    if kind not in _turfs:
        import pygame
        from overlay.unova_backdrop import UnovaBackdrop
        surf = UnovaBackdrop(None)._make_turf(kind, 'day', TURF_W, TURF_H)
        _turfs[kind] = Image.frombytes('RGBA', surf.get_size(), pygame.image.tobytes(surf, 'RGBA'))
    return _turfs[kind]


def read_gif(path):
    frames, durations = [], []
    with Image.open(path) as im:
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert('RGBA'))
            durations.append(fr.info.get('duration', im.info.get('duration', 100)) or 100)
    return frames, durations


def halve(frames):
    return [f.resize((max(1, f.width // 2), max(1, f.height // 2)), Image.NEAREST) for f in frames]


def crop_union(frames):
    box = None
    for f in frames:
        b = f.getchannel('A').getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return [f.crop(box) for f in frames] if box else frames


def compose(sprites, ground, feet=FEET_Y):
    """Each sprite frame on the turf, feet at `feet`, centred."""
    out = []
    tx = (CANVAS - ground.width) // 2
    ty = feet - 5 - ground.height // 2   # the feet a little below the turf's middle
    for s in sprites:
        frame = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
        frame.alpha_composite(ground, (tx, ty))
        frame.alpha_composite(s, ((CANVAS - s.width) // 2, feet - s.height))
        out.append(frame)
    return out


def _lzw(data, min_size=8):
    """GIF's LZW compression of `data` (palette indices), as giflib does it."""
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    out, acc, nacc = bytearray(), 0, 0
    size, nxt, table = min_size + 1, eoi + 1, {}

    def emit(code):
        nonlocal acc, nacc, size
        acc |= code << nacc
        nacc += size
        while nacc >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nacc -= 8
        if nxt >= 1 << size and size < 12:
            size += 1

    emit(clear)
    prefix = data[0]
    for b in data[1:]:
        code = table.get((prefix, b))
        if code is not None:
            prefix = code
            continue
        emit(prefix)
        if nxt >= 4095:
            emit(clear)
            table, nxt, size = {}, eoi + 1, min_size + 1
        else:
            table[(prefix, b)] = nxt
            nxt += 1
        prefix = b
    emit(prefix)
    emit(eoi)
    if nacc:
        out.append(acc & 0xFF)
    return bytes(out)


def _box(mask):
    """(x, y, w, h) around the True pixels of a 2D mask, or None."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) - int(xs.min()) + 1, int(ys.max()) - int(ys.min()) + 1


def save_gif(frames, durations, path):
    """Writes `frames` (RGBA, CANVAS square) as a looping GIF: one shared
    palette (255 colours + see-through). The first frame is drawn whole;
    after it each frame only draws the pixels that change. A pixel can't be
    made see-through again by drawing, so when the next frame needs some
    gone (where the Pokemon was and isn't any more) this frame is cleared
    after it's shown (disposal 2), only its own rectangle, around what it
    drew and what has to go: the Pokemon is wiped and drawn again each
    time, and the turf around it is stored once."""
    strip = Image.new('RGB', (CANVAS * len(frames), CANVAS), (0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f.convert('RGB'), (i * CANVAS, 0), f.getchannel('A').point(lambda a: 255 if a >= 128 else 0))
    pal = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = []
    for f in frames:
        q = np.array(f.convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE), dtype=np.uint8)
        q[np.array(f.getchannel('A')) < 128] = TRANSPARENT
        idx.append(q)
    n = len(idx)
    opaque = [a != TRANSPARENT for a in idx]
    delays = [max(2, round(d / 10)) for d in durations]   # centiseconds; browsers stretch 0-1 to 10
    parts = []   # (x, y, w, h, indices, delay, disposal)
    state = np.full((CANVAS, CANVAS), TRANSPARENT, np.uint8)   # what's on screen
    for k in range(n):
        target = idx[k]
        gone = opaque[k] & ~opaque[(k + 1) % n] if n > 1 else np.zeros_like(opaque[k])
        draw = state != target
        assert not np.any(draw & ~opaque[k]), "a pixel would have to be erased by drawing"
        if k == 0:
            parts.append((0, 0, CANVAS, CANVAS, target, delays[0], 1))
            state = target.copy()
            box = _box(gone)
            if box:
                # The first frame covers the whole canvas, so clearing it
                # would take the turf too: show it a moment (2 cs), then
                # clear only what has to go with an empty frame on top.
                x, y, w, h = box
                parts[-1] = parts[-1][:5] + (2, 1)
                parts.append((x, y, w, h, np.full((h, w), TRANSPARENT, np.uint8), max(2, delays[0] - 2), 2))
                state[y:y + h, x:x + w] = TRANSPARENT
            continue
        box = _box(draw | gone)
        if box is None:   # nothing changes: the previous frame stays longer
            parts[-1] = parts[-1][:5] + (parts[-1][5] + delays[k], parts[-1][6])
            continue
        x, y, w, h = box
        content = np.where(draw, target, TRANSPARENT)[y:y + h, x:x + w]
        disposal = 2 if gone.any() else 1
        parts.append((x, y, w, h, content, delays[k], disposal))
        state = np.where(draw, target, state)
        if disposal == 2:
            state[y:y + h, x:x + w] = TRANSPARENT

    colours = (pal.getpalette()[:255 * 3] + [0, 0, 0] * 256)[:256 * 3]
    out = bytearray(b'GIF89a' + struct.pack('<HHBBB', CANVAS, CANVAS, 0xF7, TRANSPARENT, 0) + bytes(colours))
    out += b'!\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00'   # loop forever
    for x, y, w, h, content, delay, disposal in parts:
        out += b'!\xf9\x04' + bytes([disposal << 2 | 1]) + struct.pack('<H', delay) + bytes([TRANSPARENT, 0])
        out += b',' + struct.pack('<HHHHB', x, y, w, h, 0) + b'\x08'
        data = _lzw(content.tobytes())
        for i in range(0, len(data), 255):
            out += bytes([len(data[i:i + 255])]) + data[i:i + 255]
        out += b'\x00'
    out += b';'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(out)


def make_mon(args):
    sid, shiny = args
    src = os.path.join(ASSETS, 'Shiny-Pokemon-Overworld' if shiny else 'Pokemon-Overworld', f'{sid}.gif')
    if not os.path.exists(src):
        return 0
    frames, durations = read_gif(src)
    sprites = [ImageOps.mirror(f) for f in crop_union(halve(frames))]
    folder = 'Unova-Battle-Shiny' if shiny else 'Unova-Battle'
    for kind in TURFS:
        save_gif(compose(sprites, turf(kind)), durations, os.path.join(ASSETS, folder, kind, f'{sid}.gif'))
    return len(TURFS)


# The trainers' sheets for each way of getting about (same layout: a row a
# direction, four frames), the GIF's name suffix, ms a frame (None: still).
GAITS = [('', '', 150), ('_run', '-Run', 90), ('_bike', '-Bike', 80), ('_bike_stop', '-BikeStop', None),
         ('', '-Stand', None)]


def make_trainers():
    n = 0
    for name, sheet_name in (('Hilbert', 'BW_196_Hilbert.png'), ('Hilda', 'BW_197_Hilda.png')):
        for sheet_suffix, suffix, ms in GAITS:
            sheet = Image.open(os.path.join(ASSETS, 'Trainer-Overworld',
                                            sheet_name.replace('.png', sheet_suffix + '.png'))).convert('RGBA')
            cell = sheet.width // 4
            for row, direction in enumerate(DIRECTIONS):
                frames = [sheet.crop((c * cell, row * cell, (c + 1) * cell, (row + 1) * cell)) for c in range(4)]
                frames = [f.resize((round(f.width * TRAINER_SCALE), round(f.height * TRAINER_SCALE)), Image.NEAREST)
                          for f in crop_union(halve(frames))]
                if ms is None:
                    frames = frames[:1]
                for kind in TURFS:
                    save_gif(compose(frames, turf(kind), TRAINER_FEET_Y), [ms or 1000] * len(frames),
                             os.path.join(ASSETS, 'Unova-Trainer', kind, f'{name}-{direction}{suffix}.gif'))
                    n += 1
    return n


def main():
    lo, hi = 494, 649
    print(f"Trainers: {make_trainers()} GIFs")
    if sys.argv[1:] == ['trainers']:
        return
    if len(sys.argv) > 1:
        lo, hi = (int(v) for v in sys.argv[1].split('-'))
    jobs = [(sid, shiny) for sid in range(lo, hi + 1) for shiny in (False, True)]
    with Pool() as pool:
        done = 0
        for i, n in enumerate(pool.imap_unordered(make_mon, jobs, chunksize=4), 1):
            done += n
            if i % 50 == 0:
                print(f"{i}/{len(jobs)} Pokemon, {done} GIFs", flush=True)
    print(f"Done: {done} Pokemon GIFs")


if __name__ == '__main__':
    main()
