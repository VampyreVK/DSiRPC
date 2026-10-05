"""
generic_presence.py - Discord Rich Presence for any DS game, from what DSiRPC
knows without a game-specific parser:

  - the game code from the DSi's hellos (gc=), which gives the box art from
    GameTDB (art.gametdb.com, the covers TWiLight Menu++ uses too)
  - the game's RetroAchievements set, if there's a set file in ra/ (see
    core/ra_set.py): its title, its icon, its rich presence script, evaluated
    against the live memory, and how many of its achievements you have
    (core/ra_game.py)
  - which console you play on: a picture from Assets/Consoles (the tray
    menu's "Console icon"), shown as the small image

The hub reads all that while the game runs (core/other_game.py); this file
only turns it into what Discord shows. Pokemon Platinum keeps its own, much
richer presence (rpc/platinum_presence.py).
"""

import os
import urllib.parse
import urllib.request

from pypresence import ActivityType

from core import games

GAMETDB = "https://art.gametdb.com/ds/coverS"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLES_DIR = os.path.join(ROOT, "Assets", "Consoles")
CONSOLES_URL = "https://vampyrevk.github.io/DSiRPC/Assets/Consoles"
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".webp")
# Names for the pictures in Assets/Consoles, by file name (lower case, no
# extension). Others are named after their file.
CONSOLE_NAMES = {
    "dsixl": "Nintendo DSi XL",
    "dsi": "Nintendo DSi",
    "new-nintendo-3ds": "New Nintendo 3DS",
    "new-nintendo-3ds-xl": "New Nintendo 3DS XL",
    "3ds": "Nintendo 3DS",
    "3dsxl": "Nintendo 3DS XL",
    "2ds": "Nintendo 2DS",
}


def console_icons():
    """[(key, name, image URL)] for every picture in Assets/Consoles. Discord
    loads them from GitHub Pages, so a new one shows once it's pushed."""
    out = []
    try:
        names = sorted(os.listdir(CONSOLES_DIR), key=str.lower)
    except OSError:
        return out
    for name in names:
        stem, ext = os.path.splitext(name)
        if ext.lower() not in IMAGE_TYPES:
            continue
        label = CONSOLE_NAMES.get(stem.lower()) or stem.replace("-", " ").replace("_", " ")
        out.append((stem, label, f"{CONSOLES_URL}/{urllib.parse.quote(name)}"))
    return out


def console_icon(key):
    """(name, URL) of the picture `key` (its file name without extension, any
    case), or None (no picture, or `key` is empty)."""
    if not key:
        return None
    for stem, label, url in console_icons():
        if stem.lower() == key.lower():
            return label, url
    return None

# Region folder on GameTDB from the last letter of the game code.
REGIONS = {
    "E": "US", "P": "EN", "J": "JA", "K": "KO", "D": "DE", "F": "FR", "S": "ES",
    "I": "IT", "H": "NL", "U": "AU", "C": "ZH", "Q": "DK", "R": "RU", "V": "EN",
    "X": "EN", "Y": "EN", "Z": "EN",
}

_cover_cache = {}


def _exists(url, timeout=3.0):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "DSiRPC"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def cover_url(code, check=True):
    """GameTDB's box art for a game code, or None. Each code is checked once
    (a HEAD request per region tried) and remembered."""
    if not code or len(code) != 4 or "?" in code:
        return None
    if code in _cover_cache:
        return _cover_cache[code]
    regions = []
    for r in (REGIONS.get(code[3]), "EN", "US", "JA"):
        if r and r not in regions:
            regions.append(r)
    found = None
    for r in regions:
        url = f"{GAMETDB}/{r}/{code}.png"
        if not check or _exists(url):
            found = url
            break
    _cover_cache[code] = found
    return found


def split_text(text, limit=128):
    """Splits a rich presence string over Discord's two 128-character lines,
    at a separator if there's one, so neither line gets cut mid-word.
    Returns (details, state)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text, None
    for sep in (" | ", " • ", " · ", " - ", ", "):
        best = None
        start = 0
        while True:
            i = text.find(sep, start)
            if i < 0 or i > limit:
                break
            best = i
            start = i + 1
        if best is not None and len(text) - best - len(sep) <= limit:
            return text[:best], text[best + len(sep):]
    cut = text.rfind(" ", 0, limit)
    cut = cut if cut > limit // 2 else limit
    rest = text[cut:].strip()
    return text[:cut].rstrip(), (rest[:limit - 1] + "…" if len(rest) > limit else rest) or None


def title(game, ra_set=None):
    if ra_set and ra_set.title:
        return ra_set.title
    code = (game or {}).get("code")
    return games.NAMES.get(code, code or "a DS game")


def _clip(text, limit=128):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def build_presence(game, ra_set=None, rich_presence=None, start=None, check_images=True, name=None,
                   console=None, progress=None):
    """The presence for a game without its own parser. `rich_presence` is the
    evaluated RA rich presence string (or None); `name` overrides the game's
    name (default: title()); `console` is (name, image URL) for the small
    image (console_icon()); `progress` is (unlocked, total) achievements."""
    code = (game or {}).get("code")
    name = name or title(game, ra_set)
    presence = {
        "activity_type": ActivityType.PLAYING,
        # Shown as "Playing <name>" where Discord supports overriding the
        # application's name (otherwise the application's own name shows).
        "name": name,
    }
    if rich_presence:
        presence["details"], state = split_text(rich_presence)
        if state:
            presence["state"] = state
    else:
        presence["details"] = name
    cover = cover_url(code, check=check_images)
    icon = ra_set.icon_url if ra_set else None
    ra_line = None
    if ra_set:
        if progress:
            ra_line = f"RetroAchievements: {progress[0]} of {progress[1]} unlocked"
        else:
            n = len(ra_set.playable_achievements)
            ra_line = f"RetroAchievements: {n} achievement{'s' if n != 1 else ''}"
    if console:
        # The console you play on as the small image; the RA line moves to
        # the big image's hover text. With no other picture, the console is
        # the big image (Discord only shows a small one next to a big one).
        if cover or icon:
            presence["large_image"] = cover or icon
            presence["large_text"] = _clip(f"{name} ({ra_line})" if ra_line else name)
            presence["small_image"], presence["small_text"] = console[1], console[0]
        else:
            presence["large_image"], presence["large_text"] = console[1], f"{name} on a {console[0]}"
    elif cover:
        presence["large_image"], presence["large_text"] = cover, name
        if icon:
            presence["small_image"] = icon
            presence["small_text"] = ra_line
    elif icon:
        presence["large_image"], presence["large_text"] = icon, name
    if start:
        presence["start"] = int(start)
    return presence


def shown(presence):
    """The presence as printed in the log."""
    return {k: (v.name if isinstance(v, ActivityType) else v) for k, v in presence.items() if k != "start"}


def from_state(state, start=None, check_images=True, console=None):
    """The presence for the hub's state of a game without its own parser
    (core/other_game.py)."""
    return build_presence(state.get('game'), state.get('ra_set'), state.get('rich_presence'),
                          start, check_images=check_images, name=state.get('title'),
                          console=console, progress=state.get('progress'))
