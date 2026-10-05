"""
game_titles.py - DS and DSi game titles by game code, from GameTDB's title
list (https://www.gametdb.com, where the box art comes from too).

RetroAchievements is searched by title when there's no game file to hash
(core/ra_link.py). The title in the game's own header is only readable when
the DSi's RAM mirrors its first 4 MB, which it doesn't under nds-bootstrap on
a DSi or 3DS (the header copy sits at 0x027FFE00, past what rpcprobe reads),
so the title comes from the game code the DSi announces instead:

    titles("CPUE", cache_dir)  ->  ["Pokemon: Platinum Version", "Pokemon Platinum"]

The list (about 300 KB) is downloaded into ra/cache/dstdb.txt the first time
it's needed, and again once it's a month old.
"""

import logging
import os
import time
import urllib.error
import urllib.request

from . import games

URL = "https://www.gametdb.com/dstdb.txt?LANG=EN"
FILE_NAME = "dstdb.txt"
REFRESH_AFTER = 30 * 86400

_tables = {}   # path -> (mtime, {code: title})


def _download(path, timeout=15.0):
    req = urllib.request.Request(URL, headers={"User-Agent": "DSiRPC"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if not data.startswith(b"TITLES"):
        raise ValueError("that isn't GameTDB's title list")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def table(cache_dir, download=True):
    """{game code: title} from the downloaded list, fetching it first if
    allowed and it's missing or old. {} if there's none."""
    path = os.path.join(cache_dir, FILE_NAME)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    if download and (mtime is None or time.time() - mtime > REFRESH_AFTER):
        try:
            _download(path)
            mtime = os.path.getmtime(path)
            logging.info(f"Downloaded GameTDB's list of DS game titles to {path}")
        except (OSError, ValueError, urllib.error.URLError) as e:
            logging.info(f"Can't get GameTDB's list of DS game titles: {e}")
    if mtime is None:
        return {}
    cached = _tables.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    found = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                code, sep, title = line.partition(" = ")
                code = code.strip()
                if sep and len(code) == 4 and title.strip():
                    found[code] = title.strip()
    except OSError:
        return {}
    _tables[path] = (mtime, found)
    return found


def titles(code, cache_dir, download=True):
    """Titles the game with this code might have on RetroAchievements, best
    first: GameTDB's for the code, then for the same game's US and European
    releases (RA's titles are English), then core/games.py's name."""
    if not code or len(code) != 4:
        return []
    known = table(cache_dir, download)
    out = []
    for c in (code, code[:3] + "E", code[:3] + "P"):
        t = known.get(c)
        if t and t not in out:
            out.append(t)
    name = games.NAMES.get(code)
    if name and name not in out:
        out.append(name)
    return out
