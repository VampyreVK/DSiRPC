"""
process_unova.py - makes Pokemon Black and White's Discord images: every
Pokemon (and its shiny) standing on each of the battle view's turfs, and
Hilbert and Hilda walking on them, as small, optimised animated GIFs.

    python Assets/Unova-Battle/process_unova.py            # Unova's Pokemon (494-649)
    python Assets/Unova-Battle/process_unova.py 1-649      # any range

Writes (next to the other Assets folders, served by GitHub Pages):

    Assets/Unova-Battle/<turf>/<id>.gif         a foe on that turf
    Assets/Unova-Battle-Shiny/<turf>/<id>.gif   the same, shiny
    Assets/Unova-Trainer/<turf>/<Hilbert|Hilda>-<Down|Left|Right|Up>.gif

<turf> is one of the battle platforms core/bw_data.terrain() picks (grass,
sand, snow, water, cave, indoor), drawn by overlay/unova_backdrop.py in its
day look. Only Black and White's own Pokemon (494-649) are made by default:
the older ones would add about 600 MB, so the presence shows Platinum's
dioramas for them (rpc/bw_presence.py). The
Pokemon come from Assets/Pokemon-Overworld and Shiny-Pokemon-Overworld (the
animated front sprites, drawn at 2x and facing right): halved to their real
pixels and mirrored to face left like a foe, then stood on the turf with
their feet at y=126 of a 160x160 canvas, like Platinum's dioramas. The
trainers come from Assets/Trainer-Overworld's walking sheets.

The GIFs are kept small: one palette for every frame, and after the first
frame only the pixels that change are stored (the rest are transparent and
left in place), so the turf is stored once. Needs Pillow and pygame-ce.
"""

import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(ASSETS))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from PIL import Image, ImageOps, ImageSequence  # noqa: E402

CANVAS = 160
FEET_Y = 126
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


def compose(sprites, ground):
    """Each sprite frame on the turf, feet at FEET_Y, centred."""
    out = []
    tx = (CANVAS - ground.width) // 2
    ty = FEET_Y - 5 - ground.height // 2   # the feet a little below the turf's middle
    for s in sprites:
        frame = Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))
        frame.alpha_composite(ground, (tx, ty))
        frame.alpha_composite(s, ((CANVAS - s.width) // 2, FEET_Y - s.height))
        out.append(frame)
    return out


def save_gif(frames, durations, path):
    """One shared palette (255 colours + see-through), delta frames."""
    # The palette, from every frame side by side (alpha flattened).
    strip = Image.new('RGB', (CANVAS * len(frames), CANVAS), (0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f.convert('RGB'), (i * CANVAS, 0), f.getchannel('A').point(lambda a: 255 if a >= 128 else 0))
    pal = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = []
    for f in frames:
        p = f.convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE)
        p.paste(TRANSPARENT, mask=f.getchannel('A').point(lambda a: 255 if a < 128 else 0))
        out.append(p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0,
                disposal=1, transparency=TRANSPARENT, optimize=False)


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


def make_trainers():
    n = 0
    for name, sheet_name in (('Hilbert', 'BW_196_Hilbert.png'), ('Hilda', 'BW_197_Hilda.png')):
        sheet = Image.open(os.path.join(ASSETS, 'Trainer-Overworld', sheet_name)).convert('RGBA')
        cell = sheet.width // 4
        for row, direction in enumerate(DIRECTIONS):
            frames = [sheet.crop((c * cell, row * cell, (c + 1) * cell, (row + 1) * cell)) for c in range(4)]
            walk = crop_union(halve(frames))
            for kind in TURFS:
                save_gif(compose(walk, turf(kind)), [150] * 4,
                         os.path.join(ASSETS, 'Unova-Trainer', kind, f'{name}-{direction}.gif'))
                n += 1
    return n


def main():
    lo, hi = 494, 649
    if len(sys.argv) > 1:
        lo, hi = (int(v) for v in sys.argv[1].split('-'))
    print(f"Trainers: {make_trainers()} GIFs")
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
