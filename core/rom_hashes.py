"""
rom_hashes.py - the console's games by their RetroAchievements hash, and
what RetroAchievements said of each, kept in ra/cache/rom_hashes.json.

The launcher hashes every game on its SD card once (launcher/source/
romhash.c, the same MD5 as core/ra_hash.py) and sends the hashes, with the
files' names, with each sync (core/offline.py, sync version 2).
RetroAchievements identifies a game and its version by that hash, so it's
the exact way to link a game to its set:

  - a game ID: the set for that version (HAS_SET);
  - the game ID plus 1,000,000,000: [guess: from what RetroAchievements
    answered for Animal Crossing: Wild World (USA), whose set only
    supports the European files] a hash it knows for that game but that no
    set supports (NOT_THIS_ROM);
  - 0: a hash it doesn't know. Then the game's title tells whether it has
    the game at all (NOT_THIS_ROM: another region, revision or a ROM hack)
    or not (NO_GAME). The title never links a set.

    {"version": 1,
     "roms": {"<md5>": {"code": "ADME", "name": "<file name>", "seen": <Unix time>, "started": <Unix time or 0>}},
     "games": {"<md5>": {"id": <what RetroAchievements answered>, "game": <0/1: the title found the game>,
                         "when": <Unix time>}}}

A hash with a set isn't asked again; one without is asked again after
ASK_AGAIN (due()). A game whose hashes are known but not answered yet gets no
set (not even one linked by its title) until they are.
"""

import json
import logging
import os
import time

from . import ra_set

VERSION = 1
UNKNOWN, HAS_SET, NOT_THIS_ROM, NO_GAME = 0, 1, 2, 3   # what the launcher is told (core/offline.py's RA_*)
INCOMPATIBLE = 1_000_000_000            # added to the game ID for a hash RetroAchievements knows but no set supports
ASK_AGAIN = 30 * 86400                  # a "no set" answer is asked again this long after (a set may have come)


def path(ra_dir=None):
    return os.path.join(ra_dir or ra_set.RA_DIR, "cache", "rom_hashes.json")


def empty():
    return {"version": VERSION, "roms": {}, "games": {}}


def load(ra_dir=None):
    p = path(ra_dir)
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") == VERSION and isinstance(data.get("roms"), dict) and isinstance(data.get("games"), dict):
            return data
        logging.warning(f"ROM hashes: {p} isn't one this DSiRPC reads: asking again")
    except FileNotFoundError:
        pass
    except (OSError, ValueError, AttributeError) as e:
        logging.warning(f"ROM hashes: couldn't read {p} ({e}): asking again")
    return empty()


def save(data, ra_dir=None):
    p = path(ra_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(p + ".tmp", p)


def record(data, roms, now=None):
    """The launcher's list: [(code, md5, started, file name)] (the name may be
    left out; the code is "" for a file without one, homebrew often). Kept by
    the file's hash: files sharing a code (hacks, homebrew) stay apart."""
    now = int(time.time() if now is None else now)
    for code, md5, started, *rest in roms:
        entry = data["roms"].setdefault(md5, {"code": code, "seen": now, "started": 0})
        entry["code"], entry["seen"] = code, now
        if rest and rest[0]:
            entry["name"] = rest[0]
        if started:
            entry["started"] = now


def answer(data, md5):
    """What RetroAchievements answered for the hash, or None if not asked yet"""
    g = data["games"].get(md5)
    return g.get("id") if isinstance(g, dict) and isinstance(g.get("id"), int) else None


def due(data, md5, now=None):
    """Whether to ask RetroAchievements about the hash at this sync: not
    asked yet, or its answer was "no set" (0, or a game ID plus
    INCOMPATIBLE) ASK_AGAIN ago or more (or when isn't known): RetroAchievements
    may have linked it, or made a set for that version, since. A set found
    isn't asked about again."""
    a = answer(data, md5)
    if a is None:
        return True
    if 0 < a < INCOMPATIBLE:
        return False
    when = data["games"][md5].get("when")
    now = time.time() if now is None else now
    return not isinstance(when, (int, float)) or now - when >= ASK_AGAIN


def game_id(data, md5):
    """The game whose set to use for the hash: its ID, 0 if there's none for
    it, None if RetroAchievements hasn't been asked yet."""
    a = answer(data, md5)
    return None if a is None else (a if 0 < a < INCOMPATIBLE else 0)


def remember(data, md5, gid, title_found=None, now=None):
    """RetroAchievements' answer for the hash (and, for 0, whether the
    game's title found the game)"""
    entry = {"id": int(gid), "when": int(time.time() if now is None else now)}
    if title_found is not None:
        entry["game"] = int(bool(title_found))
    data["games"][md5] = entry


def status(data, md5):
    a = answer(data, md5)
    if a is None:
        return UNKNOWN
    if 0 < a < INCOMPATIBLE:
        return HAS_SET
    if a >= INCOMPATIBLE or data["games"][md5].get("game"):
        return NOT_THIS_ROM
    return NO_GAME


def hashes_for(data, code):
    """The hashes of the code's files, the one started last first, then the
    one seen last"""
    rows = [(e.get("started", 0), e.get("seen", 0), md5) for md5, e in data["roms"].items() if e.get("code") == code]
    return [md5 for _, _, md5 in sorted(rows, reverse=True)]


def hash_for(data, code):
    """The hash to link the code by (hashes_for()'s first), or None"""
    hs = hashes_for(data, code)
    return hs[0] if hs else None


def set_hash(data, code):
    """The hash of the code's file RetroAchievements has a set for (the one
    started last first), or None: the set the code's games on the console get
    (a ROM hack sharing the code has none of its own; the launcher only
    stages a code's set for a file it's for)"""
    for md5 in hashes_for(data, code):
        if status(data, md5) == HAS_SET:
            return md5
    return None


def unsupported(data, code):
    """True when every known file of the code has been answered and none has
    a set: RetroAchievements has no set for the versions on the console."""
    hs = hashes_for(data, code)
    return bool(hs) and all(status(data, h) in (NOT_THIS_ROM, NO_GAME) for h in hs)


def may_send(data, code):
    """Whether the console may get a set for the code: yes when no file of
    it is known by its hash (a launcher from before: linked as before), or
    when one has a set; no while its hashes wait for an answer, or when none
    has one."""
    hs = hashes_for(data, code)
    return not hs or any(status(data, h) == HAS_SET for h in hs)


def set_codes(data):
    """The codes with a file RetroAchievements has a set for: {code: game ID}"""
    out = {}
    for md5, e in data["roms"].items():
        gid = game_id(data, md5)
        if gid and e.get("code"):
            out.setdefault(e["code"], gid)
    return out


def file_name(code, ra_dir=None, data=None):
    """The file's name to call the game by instead of the game it's based on,
    when the file of the code started last is one RetroAchievements has no
    set for (a ROM hack keeps the original's code and title), else None."""
    data = data if data is not None else load(ra_dir)
    md5 = hash_for(data, code)
    if md5 is None or status(data, md5) not in (NOT_THIS_ROM, NO_GAME):
        return None
    return data["roms"][md5].get("name") or None


def drop_title_link(code, ra_dir=None):
    """A set linked to the code by its title (ra/CODE.json) when its hash says
    there's none for this version: moved to ra/cache/unsupported/, so it isn't
    used or sent to the console any more (unlocks already earned stay in
    unlocked.json). Returns the set it was (or None)."""
    ra_dir = ra_dir or ra_set.RA_DIR
    src = os.path.join(ra_dir, f"{code}.json")
    if not os.path.exists(src):
        return None
    try:
        s = ra_set.load(src)
    except ra_set.SetFileError:
        s = None
    dest_dir = os.path.join(ra_dir, "cache", "unsupported")
    os.makedirs(dest_dir, exist_ok=True)
    try:
        os.replace(src, os.path.join(dest_dir, f"{code}.json"))
    except OSError as e:
        logging.warning(f"RetroAchievements: {code}: couldn't move ra/{code}.json aside: {e}")
        return None
    return s
