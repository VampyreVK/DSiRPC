"""
ra_game.py - a game's RetroAchievements side while it runs on the DSi:
its set, its rich presence text and its achievements, checked against the
DSi's memory with rcheevos (core/rcheevos.py).

    ra = RaGame(game, SparseRam(client), link, settings)
    ra.tick()                  # about once a second, from the state hub's thread
    ra.rich_presence           # "Racing in Figure-8 Circuit"
    ra.take_events()           # [{'type': 'achievement', ...}] since the last call

Where the set comes from, in order (see core/ra_link.py for the downloads):
ra/<code>.json (or ra/games.txt), RetroAchievements itself when you're signed
in (by the ROM's hash or the game's title), or an RA emulator's cache
(core/ra_cache.py).

How achievements are checked. An emulator checks every achievement on every
frame (60 times a second). DSiRPC reads the values a set needs from the DSi
about once a second (`interval`) and checks them then, so for rcheevos one
"frame" is one read: "the value changed since the last frame" means since the
last read, and a hit count of 60 frames takes 60 reads. Achievements about
lasting states (a flag set, a cup won) work the same; ones about split-second
events can unlock late or not at all, and in rare cases (something that must
not happen for a while, that's only true for a moment) unlock when they
shouldn't. That's why sending unlocks is a separate choice (settings.submit).
Achievements that read memory DSiRPC can't reach (the ARM9's data TCM,
0x1000000 on) are left out.
"""

import logging
import os
import queue
import re
import time

from . import game_titles
from . import games
from . import ra_cache
from . import ra_set

PING_FIRST = 30.0
PING_EVERY = 120.0
_ADDRESS = re.compile(r"0x[ \w]?([0-9a-fA-F]+)")


class RaSettings:
    def __init__(self, achievements=True, submit=False, profile=True, racache=None, auto_import=True,
                 interval=1.0):
        self.achievements = achievements   # check achievements (and say when one unlocks)
        self.submit = submit               # send unlocks to RetroAchievements (needs signing in)
        self.profile = profile             # rich presence on the RA profile (needs signing in)
        self.racache = racache             # an RA emulator's folder, to copy sets from
        self.auto_import = auto_import
        self.interval = interval           # seconds between checks


def _unreachable(memaddr):
    """True if an achievement reads absolute addresses past main RAM. (Behind
    a pointer, an address is an offset, so those are kept.)"""
    if "I:" in memaddr:
        return False
    for m in _ADDRESS.finditer(memaddr):
        try:
            if int(m.group(1), 16) >= 0x400000:
                return True
        except ValueError:
            pass
    return False


class RaGame:
    def __init__(self, game, ram, link=None, settings=None, ra_dir=ra_set.RA_DIR):
        self.game = game
        self.code = (game or {}).get("code")
        self.ram = ram
        self.link = link
        self.settings = settings or RaSettings()
        self.ra_dir = ra_dir
        self.set = None
        self.runtime = None
        self.rich_presence = None
        self.header_title = None
        self.header_tries = 0
        self.match_titles = []       # titles core/ra_link.py looked the game up by
        self.game_hash = None
        self.unlocked = set()        # achievement IDs: from RetroAchievements, plus this session's
        self.session = False         # RetroAchievements knows we're playing
        self.session_at = 0.0
        self.next_ping = 0.0
        self.frames = 0
        self.frames_at_ping = 0
        self.active = {}             # achievement ID -> achievement, being checked
        self.skipped = 0             # achievements left out (memory out of reach)
        self.note = None             # why there's no set, or what's being fetched
        self.next_due = 0.0
        self.read_ok = False         # the last check read the DSi fine
        self._known = []             # [(address, size)] read last time
        self._unreadable = set()
        self._seen = set()
        self._events = []
        self.inbox = queue.Queue()   # results from core/ra_link.py's thread
        self._resolved = False

    # -- what's known ------------------------------------------------------

    @property
    def game_id(self):
        return self.set.id if self.set else 0

    @property
    def title(self):
        if self.set and self.set.title:
            return self.set.title
        if self.code in games.NAMES:
            return games.NAMES[self.code]
        return self.header_title or self.code or "a DS game"

    @property
    def total(self):
        return len(self.set.playable_achievements) if self.set else 0

    @property
    def progress(self):
        """(unlocked, total) when RetroAchievements told us what's unlocked, else None."""
        if not self.set or not self.session:
            return None
        ids = {a["id"] for a in self.set.playable_achievements}
        return len(ids & self.unlocked), len(ids)

    def describe(self):
        name = games.name(self.game)
        if not self.set:
            return f"{name}: {self.note or 'no RetroAchievements set'}"
        parts = [self.set.summary()]
        if self.active:
            parts.append(f"checking {len(self.active)} achievements")
        if self.skipped:
            parts.append(f"{self.skipped} need memory DSiRPC can't read")
        return f"{name}: " + "; ".join(parts)

    def take_events(self):
        events, self._events = self._events, []
        return events

    # -- the set -----------------------------------------------------------

    def _read_header(self):
        if self.header_title is not None or self.header_tries >= 3:
            return
        self.header_tries += 1
        try:
            title, code = ra_cache.read_header(self.ram)
        except (TimeoutError, RuntimeError):
            return
        self.header_title = title if title and code == self.code else ""
        if not self.header_title:
            logging.debug(f"{self.code}: no game header at 0x023FFE00 (read {title!r}, {code!r})")

    def _resolve(self):
        """Finds the set: ra/ first, then RetroAchievements (on the link's
        thread), then an RA emulator's cache."""
        self._resolved = True
        try:
            local = ra_set.for_game(self.code, self.ra_dir)
        except ra_set.SetFileError as e:
            logging.warning(f"RetroAchievements set file for {self.code}: {e}")
            local = None
        if local:
            self.load_set(local)
        signed_in = self.link is not None and self.link.signed_in
        if signed_in:
            self.note = None if local else "looking for its set"
            self.link.prepare(self, local)
        elif not local:
            self._try_racache()

    def _titles(self):
        """The titles to match against the RA cache's sets: the header's, else
        the ones core/ra_link.py used, else GameTDB's (if already downloaded)."""
        if self.header_title:
            return [self.header_title]
        if self.match_titles:
            return self.match_titles
        return game_titles.titles(self.code, os.path.join(self.ra_dir, "cache"), download=False)

    def _try_racache(self):
        s = self.settings
        titles = self._titles() if s.racache and s.auto_import else []
        if not titles:
            if not self.set and not self.note:
                self.note = "no set file in ra/"
            return
        sets = ra_cache.scan(s.racache)
        pick, n = None, 0
        for title in titles:
            pick = ra_cache.auto_pick(title, sets)
            if pick:
                break
            n = n or len(ra_cache.candidates(title, sets))
        if not pick:
            if n:
                self.note = f"{n} possible sets in the RA cache: pick one with 'dsirpc.py setup'"
            elif not self.note:
                self.note = "no set file in ra/"
            return
        dest = ra_cache.import_set(pick, self.code, self.ra_dir)
        if dest:
            logging.info(f"{games.name(self.game)}: copied {pick.summary()} from the RA cache to {dest}")
            self.load_set(ra_set.load(dest))

    def load_set(self, s):
        """Starts checking a set (again, if it was already loaded: a fresh
        copy from RetroAchievements)."""
        from .rcheevos import Runtime, RcheevosError
        if self.runtime:
            self.runtime.close()
            self.runtime = None
        self.set, self.note, self.active, self.skipped = s, None, {}, 0
        self._known = []
        try:
            rt = Runtime()
        except RcheevosError as e:  # the library is missing
            self.note = str(e)
            logging.warning(f"{s.title}: {e}")
            return
        if s.rich_presence:
            try:
                rt.set_rich_presence(s.rich_presence)
            except RcheevosError as e:
                logging.warning(f"{s.title}: {e}; no rich presence")
        if self.settings.achievements:
            for a in s.playable_achievements:
                if a["id"] in self.unlocked:
                    continue
                if _unreachable(a["memaddr"]):
                    self.skipped += 1
                    continue
                try:
                    rt.activate_achievement(a["id"], a["memaddr"])
                    self.active[a["id"]] = a
                except RcheevosError as e:
                    logging.warning(f"{s.title}: achievement {a['id']} ({a['title']}): {e}")
        self.runtime = rt
        logging.info(f"RetroAchievements: {self.describe()}")

    # -- results from the link's thread -------------------------------------

    def _drain(self):
        while True:
            try:
                kind, value = self.inbox.get_nowait()
            except queue.Empty:
                return
            if kind == "set":  # a fresh (or first) copy from RetroAchievements
                s, game_hash = value
                self.game_hash = game_hash or self.game_hash
                self.load_set(s)
            elif kind == "session":
                self.unlocked |= value
                self.session, self.session_at = True, time.time()
                self.next_ping = self.session_at + PING_FIRST
                for aid in list(self.active):
                    if aid in self.unlocked:
                        self.runtime.deactivate_achievement(aid)
                        del self.active[aid]
                p = self.progress
                if p:
                    logging.info(f"RetroAchievements: {self.title}, {p[0]} of {p[1]} achievements unlocked")
            elif kind == "note":
                if not self.set:
                    self.note = value
            elif kind == "noset":  # RetroAchievements has none: maybe the RA cache does
                if not self.set:
                    logging.info(f"RetroAchievements: {games.name(self.game)}: {value}")
                    self.note = value
                    self._try_racache()
            elif kind == "titles":
                self.match_titles = value
            elif kind == "hash":
                self.game_hash = value

    # -- every second ------------------------------------------------------

    def _peek(self, address, num_bytes):
        self._seen.add((address, num_bytes))
        if address + num_bytes > 0x400000:
            if address not in self._unreadable:
                self._unreadable.add(address)
                logging.debug(f"{self.title}: reads 0x{address:06X}, outside main RAM; it reads as 0")
            return 0
        return int.from_bytes(self.ram[address:address + num_bytes], "little")

    def tick(self):
        """One check: reads what the set needs, updates the rich presence,
        and notes any achievement that unlocked. Raises TimeoutError /
        RuntimeError when the DSi doesn't answer."""
        self._drain()
        if self.header_title is None:
            self._read_header()
            if self.header_title is None and self.header_tries < 3:
                return
        if not self._resolved:
            self._resolve()
            self._drain()
        if not self.runtime:
            return
        if hasattr(self.ram, "clear"):
            self.ram.clear()
        if self._known and hasattr(self.ram, "prefetch"):
            self.ram.prefetch([(a, n) for a, n in self._known if a + n <= 0x400000])
        self._seen = set()
        self.read_ok = False
        events = self.runtime.frame(self._peek)
        text = self.runtime.rich_presence(self._peek) if self.runtime.has_rich_presence else ""
        self._known = sorted(self._seen)
        self.read_ok = True
        self.frames += 1
        self.rich_presence = text or None
        for name, aid, _ in events:
            if name == "achievement_triggered" and aid in self.active:
                self._unlocked(self.active.pop(aid))
        self._ping()

    def _unlocked(self, a):
        self.runtime.deactivate_achievement(a["id"])
        self.unlocked.add(a["id"])
        sending = bool(self.settings.submit and self.link and self.link.signed_in and self.set)
        if sending:
            self.link.award(self, a["id"], self.game_hash)
        p = self.progress
        logging.info(f"Achievement unlocked: {a['title']} ({a['points']} points) in {self.title}"
                     + ("" if sending else " (not sent to RetroAchievements)")
                     + (f", {p[0]} of {p[1]}" if p else ""))
        self._events.append({
            'type': 'achievement', 'id': a["id"], 'title': a["title"], 'description': a["description"],
            'points': a["points"], 'badge_url': a["badge_url"], 'game': self.title, 'sent': sending,
            'progress': p,
        })

    def _ping(self):
        """Keeps the RetroAchievements session going and shows the rich
        presence on the profile (settings.profile), every 2 minutes (the
        first 30 s in), as RA emulators do; only while the game is being
        read."""
        if not (self.session and self.set and self.link and self.link.signed_in):
            return
        now = time.time()
        if now < self.next_ping:
            return
        self.next_ping = now + PING_EVERY
        if self.frames == self.frames_at_ping:
            return
        self.frames_at_ping = self.frames
        text = self.rich_presence if self.settings.profile else None
        self.link.ping(self.game_id, text, self.game_hash)

    def reset(self):
        """The game may have been restarted (the DSi went quiet for a while):
        forgets hit counts and previous values, as an emulator does on a reset."""
        if self.runtime:
            self.runtime.reset()

    def close(self):
        if self.runtime:
            self.runtime.close()
            self.runtime = None
