"""
ra_cache.py - finding a game's RetroAchievements set file in an RA
emulator's cache, so ra/ can be filled without copying files by hand.

RALibretro (and other RAIntegration emulators) keep every set they download
as RACache/Data/<RA game ID>.json in their folder, once you've loaded the
game while logged in. The DSi can't tell us the RA game ID (that takes a hash
of the whole ROM), but the game's own header is in main RAM at 0x023FFE00:
its 12-character title (e.g. "POKEMON PL", "MARIOKART DS") and its game code.
The title is matched against the sets' titles:

    3  same letters and digits         "MARIOKART DS" ~ "Mario Kart DS"
    2  the set's title starts with it  "POKEMON PL"   ~ "Pokémon Platinum Version"
    1  its letters appear in order    "POKEMON D"    ~ "Pokémon Mystery Dungeon..."

A set is picked on its own only with a score of 2 or more that no other set
shares; otherwise setup (dsirpc.py setup) lists the candidates to choose
from. Hacks, homebrew and subsets (RA titles with ~...~ or [Subset ...]) are
never picked on their own. Only DS and DSi sets are considered.

Nothing here talks to RetroAchievements.
"""

import os
import re
import shutil
import unicodedata

from . import ra_set

HEADER_OFFSET = 0x3FFE00   # 0x023FFE00, as an offset from 0x02000000
_ID_FILE = re.compile(r"^(\d+)\.json$", re.I)


def data_dir(path):
    """The folder holding the <id>.json files, from the emulator's folder,
    its RACache folder or RACache/Data itself. None if there's none."""
    if not path:
        return None
    path = os.path.expandvars(os.path.expanduser(str(path).strip().strip('"')))
    for cand in (os.path.join(path, "RACache", "Data"), os.path.join(path, "Data"), path):
        if os.path.isdir(cand) and any(_ID_FILE.match(n) for n in os.listdir(cand)):
            return cand
    return None


_scan_cache = {}


def scan(path):
    """The DS and DSi sets in an emulator's cache, as RaSet objects (newest
    file first). Unreadable files are skipped."""
    folder = data_dir(path)
    if not folder:
        return []
    out = []
    for name in os.listdir(folder):
        if not _ID_FILE.match(name):
            continue
        full = os.path.join(folder, name)
        try:
            mtime = os.path.getmtime(full)
        except OSError:
            continue
        cached = _scan_cache.get(full)
        if cached and cached[0] == mtime:
            s = cached[1]
        else:
            try:
                s = ra_set.load(full)
            except ra_set.SetFileError:
                s = None
            _scan_cache[full] = (mtime, s)
        if s and s.console_id in (ra_set.NINTENDO_DS, ra_set.NINTENDO_DSI):
            out.append((mtime, s))
    out.sort(key=lambda p: -p[0])
    return [s for _, s in out]


def normalize(text):
    """Upper-case letters and digits only, accents dropped: 'Pokémon Pl.' -> 'POKEMONPL'."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text.upper() if c.isascii() and c.isalnum())


def _in_order(short, long):
    it = iter(long)
    return all(c in it for c in short)


def special(title):
    """Hacks, homebrew, subsets and the like, which are never picked on their own."""
    return "~" in (title or "") or "[SUBSET" in (title or "").upper()


def score(header_title, set_title):
    h, s = normalize(header_title), normalize(set_title)
    if not h or not s:
        return 0
    if h == s:
        return 3
    if s.startswith(h):
        return 2
    if _in_order(h, s):
        return 1
    return 0


def candidates(header_title, sets):
    """[(score, RaSet)] for sets that could be this game, best first (hacks,
    homebrew and subsets after the others with the same score)."""
    ranked = [(score(header_title, s.title), s) for s in sets]
    ranked = [p for p in ranked if p[0] > 0]
    ranked.sort(key=lambda p: (-p[0], special(p[1].title)))
    return ranked


def auto_pick(header_title, sets):
    """The one set that clearly matches the header title, or None."""
    ranked = [p for p in candidates(header_title, sets) if not special(p[1].title)]
    if not ranked or ranked[0][0] < 2:
        return None
    if len(ranked) > 1 and ranked[1][0] == ranked[0][0]:
        return None
    return ranked[0][1]


def read_header(ram):
    """(title, game code) from the game's header copy in main RAM (anything
    with slicing by offset: DsiRam or a RAM dump's bytes). ('', '') if it
    doesn't look like a header."""
    raw = bytes(ram[HEADER_OFFSET:HEADER_OFFSET + 16])
    if len(raw) < 16:
        return "", ""
    title = raw[:12].split(b"\0", 1)[0].decode("ascii", "replace").strip()
    code = raw[12:16].decode("ascii", "replace")
    if not re.fullmatch(r"[A-Z0-9]{4}", code) or not all(32 <= b < 127 for b in raw[:12].rstrip(b"\0")):
        return "", ""
    return title, code


def import_set(s, code, ra_dir=ra_set.RA_DIR, force=False):
    """Copies set `s` (an RaSet loaded from a file) into ra/ as <code>.json.
    Returns the new path, or None if one is already there (and not force)."""
    os.makedirs(ra_dir, exist_ok=True)
    dest = os.path.join(ra_dir, f"{code.upper()}.json")
    if os.path.exists(dest) and not force:
        return None
    shutil.copyfile(s.path, dest)
    return dest
