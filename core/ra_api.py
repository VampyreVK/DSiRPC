"""
ra_api.py - talking to RetroAchievements' server, the way RA emulators do.

Every call is a POST of form fields to https://retroachievements.org/dorequest.php
and comes back as JSON with "Success" and, when it failed, "Error". The fields
of each request are the ones rcheevos builds (src/rapi/rc_api_user.c,
rc_api_runtime.c and rc_api_info.c, v12.5.0), including the "v" signature of
an achievement unlock.

DSiRPC identifies itself honestly in the User-Agent ("DSiRPC/x.y (Windows ...)
rcheevos/12.5"), like every RA client must. RetroAchievements doesn't know
DSiRPC as an emulator, so it only ever counts its unlocks as softcore, and
DSiRPC only ever asks for softcore (h=0).

    api = RAClient()
    user, token = api.login("Vivia", password)       # once; keep the token, not the password
    api = RAClient("Vivia", token)
    game_id = api.game_id_for_hash(md5)
    data = api.game_sets(game_id=game_id)            # the set file's JSON (achievements, rich presence)
    unlocked = api.start_session(game_id)            # achievement IDs already unlocked
    api.ping(game_id, "Racing in Figure-8 Circuit")  # every 2 minutes: shows on the profile
    api.award(achievement_id)                        # softcore unlock
"""

import hashlib
import json
import os
import platform
import urllib.error
import urllib.request

HOST = "https://retroachievements.org"
DSIRPC_VERSION = "0.3.0"
RCHEEVOS_VERSION = "12.5"   # RCHEEVOS_VERSION_STRING: the patch number is left out when it's 0
_UNRESERVED = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")


def encode_form(fields):
    """Form fields encoded byte for byte like rcheevos' URL builder: letters,
    digits and -_.~ as they are, spaces as '+', everything else (UTF-8
    bytes) as lower-case %xx."""
    def enc(value):
        out = []
        for b in str(value).encode("utf-8"):
            if b in _UNRESERVED:
                out.append(chr(b))
            elif b == 0x20:
                out.append("+")
            else:
                out.append(f"%{b:02x}")
        return "".join(out)
    return "&".join(f"{k}={enc(v)}" for k, v in fields.items())


def user_agent():
    system = platform.system() or "Unknown"
    release = platform.version() if system == "Windows" else platform.release()
    return f"DSiRPC/{DSIRPC_VERSION} ({system} {release}) rcheevos/{RCHEEVOS_VERSION}"


class RAError(Exception):
    """The server said no (wrong password, unknown game, ...). Not worth retrying."""


class RANetworkError(RAError):
    """No answer, or a server error: worth trying again later."""


def unlock_signature(achievement_id, username, hardcore=False, seconds_since_unlock=0):
    """The 'v' field of awardachievement: md5 of the achievement ID, the user
    name and 0/1 for hardcore (plus the ID and the delay again for a late
    unlock), as rc_api_init_award_achievement_request does."""
    text = f"{achievement_id}{username}{1 if hardcore else 0}"
    if seconds_since_unlock:
        text += f"{achievement_id}{seconds_since_unlock}"
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class RAClient:
    def __init__(self, username=None, token=None, host=None, timeout=30.0):
        self.username = username
        self.token = token
        # DSIRPC_RA_HOST points it at a test server instead
        self.host = (host or os.environ.get("DSIRPC_RA_HOST") or HOST).rstrip("/")
        self.timeout = timeout

    @property
    def signed_in(self):
        return bool(self.username and self.token)

    def _post(self, fields, auth=True):
        if auth:
            if not self.signed_in:
                raise RAError("not signed in to RetroAchievements")
            fields = {"r": fields.pop("r"), "u": self.username, "t": self.token, **fields}
        body = encode_form(fields).encode("ascii")
        req = urllib.request.Request(self.host + "/dorequest.php", data=body, method="POST", headers={
            "User-Agent": user_agent(),
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (urllib.error.URLError, OSError) as e:
            raise RANetworkError(f"can't reach RetroAchievements: {getattr(e, 'reason', e)}")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            if status >= 500 or status == 429:
                raise RANetworkError(f"RetroAchievements answered HTTP {status}")
            raise RAError(f"RetroAchievements answered HTTP {status} without JSON")
        if not isinstance(data, dict):
            raise RAError("unexpected answer from RetroAchievements")
        if data.get("Success") is False:
            message = data.get("Error") or f"HTTP {status}"
            if status >= 500 or status == 429:
                raise RANetworkError(message)
            raise RAError(message)
        if status >= 500 or status == 429:
            raise RANetworkError(f"RetroAchievements answered HTTP {status}")
        return data

    # -- account -----------------------------------------------------------

    def login(self, username, password=None, token=None):
        """Signs in with a password (or checks a token). Returns (user name as
        RA spells it, token). The password isn't kept."""
        fields = {"r": "login2", "u": username}
        if password:
            fields["p"] = password
        elif token:
            fields["t"] = token
        else:
            raise RAError("no password or token")
        data = self._post(fields, auth=False)
        if not data.get("Token"):
            raise RAError("RetroAchievements didn't send a login token")
        self.username, self.token = data.get("User") or username, data["Token"]
        return self.username, self.token

    # -- games -------------------------------------------------------------

    def game_id_for_hash(self, game_hash):
        """The RA game ID for a ROM hash (0 if RetroAchievements doesn't know it)."""
        data = self._post({"r": "gameid", "m": game_hash}, auth=False)
        return int(data.get("GameID") or 0)

    def game_sets(self, game_id=None, game_hash=None):
        """A game's achievement sets, rich presence and title: the same JSON
        core/ra_set.py reads from a set file."""
        fields = {"r": "achievementsets"}
        if game_id:
            fields["g"] = str(int(game_id))
        elif game_hash:
            fields["m"] = game_hash
        else:
            raise RAError("no game ID or hash")
        return self._post(fields)

    def system_games(self, console_id):
        """Every game RetroAchievements has for a console: [{'ID', 'Title',
        'NumAchievements', ...}]."""
        data = self._post({"r": "systemgames", "s": str(int(console_id))}, auth=False)
        return [g for g in (data.get("Response") or []) if isinstance(g, dict) and g.get("ID")]

    # -- playing -----------------------------------------------------------

    def start_session(self, game_id, game_hash=None):
        """Tells RetroAchievements a game started. Returns the achievements
        the user already has (softcore or hardcore): {ID: when it was
        earned, as a Unix time (the earliest of the two; 0 if not given)}."""
        fields = {"r": "startsession", "g": str(int(game_id))}
        if game_hash:
            fields["h"] = "0"
            fields["m"] = game_hash
        fields["l"] = RCHEEVOS_VERSION
        data = self._post(fields)
        unlocked = {}
        for key in ("Unlocks", "HardcoreUnlocks"):
            for u in data.get(key) or []:
                if isinstance(u, dict) and u.get("ID"):
                    try:
                        when = int(u.get("When") or 0)
                    except (TypeError, ValueError):
                        when = 0
                    aid = int(u["ID"])
                    old = unlocked.get(aid)
                    unlocked[aid] = when if not old else min(old, when) if when else old
        return unlocked

    def ping(self, game_id, rich_presence=None, game_hash=None):
        """Keeps the session alive and sets the rich presence text on the profile."""
        fields = {"r": "ping", "g": str(int(game_id))}
        if rich_presence:
            fields["m"] = rich_presence[:255]
        if game_hash:
            fields["h"] = "0"
            fields["x"] = game_hash
        self._post(fields)

    def award(self, achievement_id, game_hash=None, seconds_since_unlock=0):
        """A softcore unlock. Returns the server's answer (Score,
        SoftcoreScore, AchievementsRemaining); 'User already has' counts as
        success."""
        fields = {"r": "awardachievement", "a": str(int(achievement_id)), "h": "0"}
        if game_hash:
            fields["m"] = game_hash
        if seconds_since_unlock:
            fields["o"] = str(int(seconds_since_unlock))
        fields["v"] = unlock_signature(achievement_id, self.username, False, int(seconds_since_unlock or 0))
        try:
            return self._post(fields)
        except RAError as e:
            if str(e).startswith("User already has") and not isinstance(e, RANetworkError):
                return {"Success": True, "AlreadyHad": True}
            raise
