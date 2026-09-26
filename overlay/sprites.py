"""
sprites.py - turns the repo's Assets/ into native-resolution pixel sprites for
the overlay, in memory. No image files are written.

The GIFs in Assets/ were made for Discord, so each kind needs undoing first:

    Pokemon-Overworld, Shiny-Pokemon-Overworld  animated front sprites, 2x nearest
                                                upscale -> party icons and the foe
                                                (halved)
    Pokemon-Battle-BackSmall, Shiny-...          2x upscale, mirrored
                                                -> your battler (halved, un-mirrored)
    Pokemon-Battle-NormalLarge, Shiny-...        1x, mirrored, pasted on the grass
                                                diorama. Only a fallback for the foe:
                                                GIF palette quantization shifts the
                                                grass colours for some sprites, so
                                                cutting the diorama out isn't exact.
    Trainer-Overworld/NPC_*.png                  4x4 sheet of 64x64 cells, drawn at
                                                2x (rows Down, Left, Right, Up)
                                                -> halved

Decoding runs on a worker thread so the window never stalls; get() returns
None until a sprite is ready.
"""

import os
import queue
import threading

import pygame
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageSequence

# Where process_diorama.py puts a sprite on its 160x160 canvas: centred on
# x=80, bottom edge at y=126. The overlay places the foe on the platform the
# same way (see SpriteBank.platform_box).
DIORAMA_CENTER_X = 80
DIORAMA_BOTTOM = 126


class Anim:
    """Frames (pygame Surfaces) with per-frame durations in milliseconds."""

    def __init__(self, frames, durations):
        self.frames = frames
        self.durations = [max(20, d) for d in durations]
        self.total = sum(self.durations)
        self.width = max(f.get_width() for f in frames)
        self.height = max(f.get_height() for f in frames)

    def frame(self, t_ms):
        if len(self.frames) == 1:
            return self.frames[0]
        t = t_ms % self.total
        for f, d in zip(self.frames, self.durations):
            if t < d:
                return f
            t -= d
        return self.frames[-1]


def _read_gif(path):
    frames, durations = [], []
    with Image.open(path) as img:
        default = img.info.get('duration', 100)
        for fr in ImageSequence.Iterator(img):
            frames.append(fr.copy().convert('RGBA'))
            durations.append(fr.info.get('duration', default) or default)
    return frames, durations


def _crop_union(frames, pad=0):
    box = None
    for f in frames:
        b = f.getchannel('A').getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3]))
    if box is None:
        return frames
    box = (max(0, box[0] - pad), max(0, box[1] - pad), box[2] + pad, box[3] + pad)
    return [f.crop(box) for f in frames]


def _halve(frames):
    return [f.resize((f.width // 2, f.height // 2), Image.NEAREST) for f in frames]


def _strip_diorama(frames, bg):
    """Keeps only the pixels that differ from the diorama background, above
    the line the sprite was pasted on, minus stray specks."""
    out = []
    for f in frames:
        diff = ImageChops.difference(f, bg)
        r, g, b, a = diff.split()
        mask = ImageChops.lighter(ImageChops.lighter(r, g), ImageChops.lighter(b, a))
        mask = mask.point(lambda v: 255 if v else 0)
        # Pixels that are transparent in the frame can't be sprite.
        mask = ImageChops.multiply(mask, f.getchannel('A').point(lambda v: 255 if v else 0))
        mask.paste(0, (0, DIORAMA_BOTTOM, mask.width, mask.height))
        # Anything outside the (slightly grown) bbox of the eroded mask is a speck.
        core = mask.filter(ImageFilter.MinFilter(3)).getbbox()
        if core:
            keep = Image.new('L', mask.size, 0)
            keep.paste(255, (max(0, core[0] - 3), max(0, core[1] - 3), core[2] + 3, core[3] + 3))
            mask = ImageChops.multiply(mask, keep)
        sprite = Image.new('RGBA', f.size, (0, 0, 0, 0))
        sprite.paste(f, (0, 0), mask)
        out.append(sprite)
    return out


# Platform recolouring: (saturation, per-channel multiply, add) per terrain,
# and (multiply, add) per time of day, matching backdrop.py's tints.
PLATFORM_LOOK = {
    'snow': (0.15, (0.9, 0.95, 1.0), (110, 116, 124)),
    'cave': (0.3, (0.72, 0.6, 0.5), (8, 4, 0)),
    'indoor': (0.2, (0.92, 0.86, 0.78), (40, 34, 24)),
}
TIME_LOOK = {
    'evening': ((0.92, 0.78, 0.72), (18, 4, 0)),
    'night': ((0.45, 0.5, 0.72), (0, 0, 10)),
}


def _tint(img, mul, add):
    r, g, b, a = img.split()
    chans = [c.point(lambda v, m=m, k=k: max(0, min(255, int(v * m + k)))) for c, m, k in zip((r, g, b), mul, add)]
    return Image.merge('RGBA', (*chans, a))


class SpriteBank:
    def __init__(self, assets_dir):
        self.assets = assets_dir
        self._pil = {}        # key -> (frames, durations) decoded on the worker
        self._anims = {}      # key -> Anim (pygame surfaces, main thread only)
        self._missing = set()
        self._queued = set()
        # Where the platform sits inside the 160x160 diorama canvas
        # (left, top, right, bottom), set once platform() has loaded.
        self.platform_box = None
        self._lock = threading.Lock()
        self._q = queue.Queue()
        threading.Thread(target=self._worker, name="SpriteLoader", daemon=True).start()

    # -- public ---------------------------------------------------------------

    def party_icon(self, species_id, shiny=False):
        return self.get(('icon', species_id, shiny))

    def front(self, species_id, shiny=False):
        return self.get(('front', species_id, shiny))

    def back(self, species_id, shiny=False):
        return self.get(('back', species_id, shiny))

    def trainer(self, character, direction):
        """character 'Lucas' or 'Dawn', direction 'down'/'left'/'right'/'up'."""
        return self.get(('trainer', character, direction))

    def platform(self, place='field', when='day'):
        """The grass platform, recoloured for the terrain ('field', 'snow',
        'cave', 'indoor') and time of day (see backdrop.py)."""
        return self.get(('platform', place, when))

    def get(self, key):
        anim = self._anims.get(key)
        if anim is not None:
            return anim
        with self._lock:
            pil = self._pil.pop(key, None)
            if pil is None:
                if key not in self._queued and key not in self._missing:
                    self._queued.add(key)
                    self._q.put(key)
                return None
        frames = [pygame.image.frombytes(f.tobytes(), f.size, 'RGBA').convert_alpha() for f in pil[0]]
        anim = Anim(frames, pil[1])
        self._anims[key] = anim
        return anim

    # -- worker ---------------------------------------------------------------

    def _worker(self):
        while True:
            key = self._q.get()
            try:
                result = self._load(key)
            except Exception:
                result = None
            with self._lock:
                self._queued.discard(key)
                if result is None:
                    self._missing.add(key)
                else:
                    self._pil[key] = result

    def _path(self, *parts):
        return os.path.join(self.assets, *parts)

    def _load(self, key):
        kind = key[0]
        if kind == 'icon':
            _, sid, shiny = key
            folder = 'Shiny-Pokemon-Overworld' if shiny else 'Pokemon-Overworld'
            frames, durs = _read_gif(self._path(folder, f'{sid}.gif'))
            return _crop_union(_halve(frames)), durs
        if kind == 'back':
            _, sid, shiny = key
            folder = 'Shiny-Battle-BackSmall' if shiny else 'Pokemon-Battle-BackSmall'
            frames, durs = _read_gif(self._path(folder, f'{sid}.gif'))
            frames = [ImageOps.mirror(f) for f in _halve(frames)]
            return _crop_union(frames), durs
        if kind == 'front':
            _, sid, shiny = key
            icon = self._path('Shiny-Pokemon-Overworld' if shiny else 'Pokemon-Overworld', f'{sid}.gif')
            if os.path.exists(icon):
                return self._load(('icon', sid, shiny))
            folder = 'Shiny-Battle-NormalLarge' if shiny else 'Pokemon-Battle-NormalLarge'
            frames, durs = _read_gif(self._path(folder, f'{sid}.gif'))
            bg_path = self._path(folder, 'BattleBackgroundNormal.png')
            if not os.path.exists(bg_path):
                bg_path = self._path('Pokemon-Battle-NormalLarge', 'BattleBackgroundNormal.png')
            bg = Image.open(bg_path).convert('RGBA').resize(frames[0].size, Image.NEAREST)
            frames = [ImageOps.mirror(f) for f in _strip_diorama(frames, bg)]
            return _crop_union(frames), durs
        if kind == 'trainer':
            _, character, direction = key
            sheet = Image.open(self._path('Trainer-Overworld',
                                          'NPC_198_Lucas.png' if character == 'Lucas' else 'NPC_201_Dawn.png')).convert('RGBA')
            row = ['down', 'left', 'right', 'up'].index(direction)
            cell = sheet.width // 4
            frames = [sheet.crop((c * cell, row * cell, (c + 1) * cell, (row + 1) * cell)) for c in range(4)]
            # The sheets are drawn at 2x (every pixel doubled); halve to native.
            return _crop_union(_halve(frames)), [150] * 4
        if kind == 'platform':
            _, place, when = key
            img = Image.open(self._path('Pokemon-Battle-NormalLarge', 'BattleBackgroundNormal.png')).convert('RGBA')
            box = img.getchannel('A').getbbox()
            self.platform_box = box
            img = img.crop(box)
            if place in PLATFORM_LOOK:
                sat, mul, add = PLATFORM_LOOK[place]
                img = _tint(ImageEnhance.Color(img).enhance(sat), mul, add)
            if when in TIME_LOOK:
                img = _tint(img, *TIME_LOOK[when])
            return [img], [1000]
        return None
