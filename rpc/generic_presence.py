"""
generic_presence.py - Discord Rich Presence for any DS game, from what DSiRPC
knows without a game-specific parser:

  - the game code from the DSi's hellos (gc=), which gives the box art from
    GameTDB (art.gametdb.com, the covers TWiLight Menu++ uses too)
  - the game's RetroAchievements set, if there's a set file in ra/ (see
    core/ra_set.py): its title, its icon, and its rich presence script,
    evaluated against the live memory (core/ra_presence.py)

The hub reads all that while the game runs (core/other_game.py); this file
only turns it into what Discord shows. Pokemon Platinum keeps its own, much
richer presence (rpc/platinum_presence.py).
"""

import urllib.request

from pypresence import ActivityType

from core import games

GAMETDB = "https://art.gametdb.com/ds/coverS"

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


def build_presence(game, ra_set=None, rich_presence=None, start=None, check_images=True, name=None):
    """The presence for a game without its own parser. `rich_presence` is the
    evaluated RA rich presence string (or None); `name` overrides the game's
    name (default: title())."""
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
    if cover:
        presence["large_image"], presence["large_text"] = cover, name
        if icon:
            n = len(ra_set.official_achievements)
            presence["small_image"] = icon
            presence["small_text"] = f"RetroAchievements: {n} achievement{'s' if n != 1 else ''}"
    elif icon:
        presence["large_image"], presence["large_text"] = icon, name
    if start:
        presence["start"] = int(start)
    return presence


def shown(presence):
    """The presence as printed in the log."""
    return {k: (v.name if isinstance(v, ActivityType) else v) for k, v in presence.items() if k != "start"}


def from_state(state, start=None, check_images=True):
    """The presence for the hub's state of a game without its own parser
    (core/other_game.py)."""
    return build_presence(state.get('game'), state.get('ra_set'), state.get('rich_presence'),
                          start, check_images=check_images, name=state.get('title'))
