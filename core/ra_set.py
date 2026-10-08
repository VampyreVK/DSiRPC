"""
ra_set.py - a game's RetroAchievements set, from a local JSON file.

DSiRPC never downloads sets or reports anything to RetroAchievements. A set
file is the game data an RA emulator downloads: RALibretro (and other
RAIntegration emulators) keep it in RACache/Data/<RA game ID>.json after you
load the game once while logged in. 'dsirpc.py setup' or tools/ra_tool.py
copies one into ra/ (or DSiRPC does it on its own; see core/ra_cache.py).

Files are looked up by the game code the DSi reports (gc= in the hellos):

    ra/<game code>.json             e.g. ra/CPUE.json
    ra/games.txt                    lines "<game code> <RA game ID>", for
                                    files kept under their RA ID (ra/11732.json)

Both of RetroAchievements' formats are understood: the older
{"PatchData": {...}} one and the newer {"Sets": [...]} one (the core set's
achievements, plus any subsets').
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RA_DIR = os.path.join(os.path.dirname(HERE), "ra")
MEDIA = "https://media.retroachievements.org"

# RetroAchievements console IDs
NINTENDO_DS = 18
NINTENDO_DSI = 78

# RetroAchievements adds pseudo-achievements from this ID up to sets it sends
# a client it doesn't know (like "Warning: Unknown Emulator", 0 points, and
# already unlocked). They aren't part of the game's set: rcheevos' own client
# leaves them out of the counts and never sends them, and so does DSiRPC.
WARNING_ID = 101000001


class SetFileError(Exception):
    pass


def _media_url(value, folder):
    """A full media URL from what the set file has: a URL already, a
    '/Images/012345.png' path, or a bare badge name."""
    if not value:
        return None
    value = str(value)
    if value.startswith("http"):
        return value
    if value.startswith("/"):
        return MEDIA + value
    return f"{MEDIA}/{folder}/{value}.png"


class RaSet:
    def __init__(self, data, path=None):
        self.path = path
        root = data
        if "PatchData" in root:
            if root.get("Success") is False:
                raise SetFileError(f"the file is an error response: {root.get('Error')}")
            root = root["PatchData"]
        self.id = int(root.get("ID") or root.get("GameId") or 0)
        self.title = root.get("Title") or ""
        self.console_id = int(root.get("ConsoleID") or root.get("ConsoleId") or 0)
        self.icon_url = _media_url(root.get("ImageIconURL") or root.get("ImageIconUrl") or root.get("ImageIcon"), "Images")
        self.rich_presence = root.get("RichPresencePatch") or ""
        self.achievements = []
        self.leaderboards = []
        if "Sets" in root:
            for s in root["Sets"]:
                self._add(s.get("Achievements") or [], s.get("Leaderboards") or [], s.get("Title"),
                          (s.get("Type") or "core").lower())
        else:
            self._add(root.get("Achievements") or [], root.get("Leaderboards") or [], None, "core")
        if not self.title:
            raise SetFileError("no game title in the file: is it a RetroAchievements set?")

    def _add(self, achievements, leaderboards, subset, set_type):
        for a in achievements:
            if int(a["ID"]) >= WARNING_ID:
                continue
            self.achievements.append({
                "id": int(a["ID"]),
                "title": a.get("Title", ""),
                "description": a.get("Description", ""),
                "points": int(a.get("Points") or 0),
                "memaddr": a.get("MemAddr", ""),
                # Flags 3 = core (official), 5 = unofficial
                "official": int(a.get("Flags") or 3) == 3,
                "badge_url": _media_url(a.get("BadgeURL") or a.get("BadgeName"), "Badge"),
                "subset": subset,
                # core, bonus, specialty or exclusive (the last two need their own ROM hash)
                "set_type": set_type,
            })
        for lb in leaderboards:
            self.leaderboards.append({
                "id": int(lb["ID"]),
                "title": lb.get("Title", ""),
                "description": lb.get("Description", ""),
                "mem": lb.get("Mem", ""),
                "format": lb.get("Format", ""),
                "hidden": bool(lb.get("Hidden")),
            })

    @property
    def official_achievements(self):
        return [a for a in self.achievements if a["official"]]

    @property
    def playable_achievements(self):
        """The official achievements of the core set and bonus sets: the ones
        that count for any version of the game."""
        return [a for a in self.official_achievements if a["set_type"] in ("core", "bonus")]

    @property
    def points(self):
        return sum(a["points"] for a in self.official_achievements)

    def summary(self):
        n = len(self.official_achievements)
        return f"{self.title} (RA game {self.id}): {n} achievements, {self.points} points" + \
               (", rich presence" if self.rich_presence else ", no rich presence")


def load(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise SetFileError(f"{path}: {e}")
    if not isinstance(data, dict):
        raise SetFileError(f"{path}: not a RetroAchievements set")
    return RaSet(data, path)


def _mapping(ra_dir):
    """{game code: RA game ID} from ra/games.txt."""
    out = {}
    path = os.path.join(ra_dir, "games.txt")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                m = re.match(r"^([A-Z0-9]{4})\s+(\d+)$", line, re.I)
                if m:
                    out[m.group(1).upper()] = m.group(2)
    except OSError:
        pass
    return out


def find(code, ra_dir=RA_DIR):
    """Path of the set file for a game code, or None."""
    if not code:
        return None
    direct = os.path.join(ra_dir, f"{code}.json")
    if os.path.exists(direct):
        return direct
    game_id = _mapping(ra_dir).get(code.upper())
    if game_id:
        path = os.path.join(ra_dir, f"{game_id}.json")
        if os.path.exists(path):
            return path
    return None


def codes(ra_dir=RA_DIR):
    """The game codes that have a set file in ra/ (CODE.json, or a line in
    ra/games.txt), sorted."""
    out = set()
    try:
        names = os.listdir(ra_dir)
    except OSError:
        names = []
    for name in names:
        m = re.match(r"^([A-Z][A-Z0-9]{3})\.json$", name, re.I)
        if m:
            out.add(m.group(1).upper())
    for code, game_id in _mapping(ra_dir).items():
        if os.path.exists(os.path.join(ra_dir, f"{game_id}.json")):
            out.add(code)
    return sorted(out)


def for_game(code, ra_dir=RA_DIR):
    """The RaSet for a game code, or None if there's no set file."""
    path = find(code, ra_dir)
    return load(path) if path else None
