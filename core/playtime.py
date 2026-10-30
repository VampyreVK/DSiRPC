"""
playtime.py - how long each game has been played while DSiRPC was watching
(the console said hello and kept answering), and when it was last played,
for the launcher's game picker and achievement list in its modern look
(launcher/source/stats.c is the console's side).

    ra/cache/playtime.json    {"CPUE": {"seconds": 148320, "last": 1730239200}}

    playtime = Playtime()
    playtime.tick("CPUE")     # whenever the hub updates while the game is online
    playtime.flush()          # as DSiRPC stops

The time between two ticks of the same game counts, unless they're more than
GAP apart (the console slept, or went away and came back); the file is
written at most every SAVE_EVERY seconds, and by flush(). Offline play isn't
counted: DSiRPC doesn't see it.

The launcher asks after its first sync, over the offline sync's TCP port
(core/console_sync.py hands over any connection that starts with "DRGS").
Little-endian:

    request:  "DRGS" | version u16 (1) | MAC[6] | console model u8 | 7 bytes 0
              (20 bytes, as long as the offline sync's request, so a DSiRPC
              from before playtimes turns it down at once)
    answer:   "DRGA" | status u16 (0 OK, 4 bad request) | n u16 | flags u8
              (bit 0: Discord connected) | PC name length u8 | the
              RetroAchievements user's length u8 | 1 byte 0, then the PC's
              name and the user's (ASCII, up to 32 each; no user: not signed
              in), then n x (4 game code | u32 seconds played | u32 last
              played: seconds since 2000-01-01 by the PC's clock, local time,
              as the console dates things)
"""

import calendar
import json
import logging
import os
import socket
import struct
import sys
import threading
import time

from . import ra_set

PLAYTIME_FILE = os.path.join(ra_set.RA_DIR, "cache", "playtime.json")
MAGIC = b"DRGS"
VERSION = 1
HEADER = struct.Struct("<4sH6sB7x")
ANSWER = struct.Struct("<4sHHBBBx")
ENTRY = struct.Struct("<4sII")
OK, BAD_REQUEST = 0, 4
GAP = 60.0
SAVE_EVERY = 60.0
MAX_GAMES = 1024
TEXT_MAX = 32
UNIX_2000 = 946684800


def valid_code(code):
    return len(code) == 4 and all(c.isascii() and (c.isupper() or c.isdigit()) for c in code)


def console_time(t):
    """A Unix time as the console counts: seconds since 2000 in local time
    (0 stays 0)."""
    if not t:
        return 0
    return max(0, calendar.timegm(time.localtime(t)) - UNIX_2000)


def pc_name():
    """What the launcher calls this PC ("DSiRPC on ..."): its name, without
    its domain, or on a Mac just "macOS" (a Mac's name is usually only its
    model, like "MacBookPro")."""
    if sys.platform == "darwin":
        return "macOS"
    try:
        return socket.gethostname().split(".")[0]
    except OSError:
        return ""


class Playtime:
    def __init__(self, path=PLAYTIME_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._games = self._read()
        self._last = None          # (code, time) of the last tick
        self._saved = time.time()
        self._dirty = False

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        out = {}
        if isinstance(data, dict):
            for code, g in data.items():
                if not valid_code(code) or not isinstance(g, dict):
                    continue
                try:
                    out[code] = {'seconds': float(g.get('seconds') or 0), 'last': int(g.get('last') or 0)}
                except (TypeError, ValueError):
                    continue
        return out

    def _write(self):
        data = {code: {'seconds': int(round(g['seconds'])), 'last': g['last']} for code, g in self._games.items()}
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
            self._dirty = False
        except OSError as e:
            logging.warning(f"Couldn't save the playtimes: {e}")
        self._saved = time.time()

    def tick(self, code, now=None):
        """The game is running (the hub heard from it): counts the time since
        its last tick, if that was this game and not too long ago."""
        if not valid_code(code or ""):
            return
        now = time.time() if now is None else now
        with self._lock:
            g = self._games.setdefault(code, {'seconds': 0.0, 'last': 0})
            if self._last and self._last[0] == code and 0 < now - self._last[1] <= GAP:
                g['seconds'] += now - self._last[1]
            g['last'] = int(now)
            self._last = (code, now)
            self._dirty = True
            if now - self._saved >= SAVE_EVERY:
                self._write()

    def flush(self):
        with self._lock:
            if self._dirty:
                self._write()

    def games(self):
        """{code: (seconds played, last played as a Unix time)}"""
        with self._lock:
            return {code: (int(round(g['seconds'])), g['last']) for code, g in self._games.items()}


def _ascii(text):
    return (text or "").encode("ascii", "replace")[:TEXT_MAX]


def handle(magic, read, send, playtime, info=None):
    """Answers one request: magic is the 4 bytes already read, read(n) and
    send(bytes) talk to the console. playtime is the Playtime (None: nothing
    to tell), info {'pc': name, 'ra': RetroAchievements user or "",
    'discord': connected}."""
    rest = read(HEADER.size - 4)
    _, version, _, _ = HEADER.unpack(magic + rest)
    if version != VERSION:
        send(ANSWER.pack(b"DRGA", BAD_REQUEST, 0, 0, 0, 0))
        return
    info = info or {}
    pc, ra = _ascii(info.get('pc')), _ascii(info.get('ra'))
    have = sorted((playtime.games() if playtime else {}).items())[:MAX_GAMES]
    out = [ANSWER.pack(b"DRGA", OK, len(have), 1 if info.get('discord') else 0, len(pc), len(ra)), pc, ra]
    out += [ENTRY.pack(code.encode(), min(secs, 0xFFFFFFFF), console_time(last)) for code, (secs, last) in have]
    send(b"".join(out))
    logging.debug(f"Playtimes: sent {len(have)} game(s) to the console")


# -- a console, for tests ------------------------------------------------------

def request(mac=b"\0\x09\xbf\x12\x3f\x21", model=0, version=VERSION):
    return HEADER.pack(MAGIC, version, mac, model)


def parse_answer(data):
    """-> (status, flags, pc, ra, {code: (seconds, last)})"""
    magic, status, n, flags, pc_len, ra_len = ANSWER.unpack_from(data)
    if magic != b"DRGA":
        raise ValueError("not a playtime answer")
    at = ANSWER.size
    pc = data[at:at + pc_len].decode()
    ra = data[at + pc_len:at + pc_len + ra_len].decode()
    at += pc_len + ra_len
    games = {}
    for i in range(n):
        code, secs, last = ENTRY.unpack_from(data, at + i * ENTRY.size)
        games[code.decode()] = (secs, last)
    return status, flags, pc, ra, games
