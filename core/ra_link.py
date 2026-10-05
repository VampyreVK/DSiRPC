"""
ra_link.py - DSiRPC's connection to RetroAchievements, on its own thread so
the state hub never waits for the network. Only used when you're signed in
('dsirpc.py setup' keeps a login token in dsirpc.cfg, never the password).

When a game starts (core/ra_game.py calls prepare()):

  1. Which RA game is it? With a folder of game files (`roms`), the file
     with the same game code is hashed the way RA emulators do
     (core/ra_hash.py) and RetroAchievements says which game that is: the
     exact answer. Otherwise the set file in ra/ says, or the game's title is
     matched against RetroAchievements' list of DS and DSi games
     (core/ra_cache.py's rules: only one clear match counts). The title is
     the one in the game's header when that can be read, else GameTDB's for
     the game code (core/game_titles.py).
  2. Its set (achievements, rich presence) is downloaded into ra/<code>.json,
     unless the copy there is less than a day old.
  3. A session is started, which also says which achievements you already
     have, and core/ra_game.py pings every 2 minutes with the rich presence,
     which is what your RA profile shows.

Unlocks (award()) are only sent when you chose that in setup, always as
softcore. Each is written to ra/cache/pending_unlocks.json first and taken
off once RetroAchievements has it; without a connection they're retried
(1 s, 2 s, 4 s ... up to every 2 minutes, like RA emulators) and, after a
restart, sent with how long ago they happened.
"""

import heapq
import itertools
import json
import logging
import os
import threading
import time
import types

from . import game_titles
from . import ra_cache
from . import ra_set
from .ra_api import RAClient, RAError, RANetworkError
from .ra_hash import RomIndex

REFRESH_SET_AFTER = 24 * 3600
TITLE_LIST_DAYS = 7
CACHE_DIR = os.path.join(ra_set.RA_DIR, "cache")


class RALink:
    def __init__(self, username=None, token=None, roms=None, settings=None, ra_dir=ra_set.RA_DIR, api=None):
        self.api = api or RAClient(username, token)
        self.roms = roms
        self.settings = settings
        self.ra_dir = ra_dir
        self.cache_dir = os.path.join(ra_dir, "cache")
        self.pending_file = os.path.join(self.cache_dir, "pending_unlocks.json")
        self.status = f"signed in as {self.api.username}" if self.signed_in else "not signed in"
        self._jobs = []
        self._seq = itertools.count()
        self._cv = threading.Condition()
        self._stopping = False
        self._pending = []
        self._lock = threading.RLock()   # update() holds it while _load_pending() takes it
        self._thread = threading.Thread(target=self._run, name="RetroAchievements", daemon=True)
        self._thread.start()
        if self.signed_in:
            self._load_pending()

    @property
    def signed_in(self):
        return self.api.signed_in

    @property
    def username(self):
        return self.api.username

    def update(self, username=None, token=None, roms=None):
        """New settings (dsirpc.cfg changed)."""
        with self._lock:
            if (username, token) != (self.api.username, self.api.token):
                self.api.username, self.api.token = username, token
                self.status = f"signed in as {username}" if self.signed_in else "not signed in"
                if self.signed_in:
                    self._load_pending()
            self.roms = roms

    # -- the thread --------------------------------------------------------

    def _later(self, delay, fn, *args):
        with self._cv:
            heapq.heappush(self._jobs, (time.time() + delay, next(self._seq), fn, args))
            self._cv.notify()

    def _run(self):
        while True:
            with self._cv:
                while not self._stopping and (not self._jobs or self._jobs[0][0] > time.time()):
                    self._cv.wait(timeout=(self._jobs[0][0] - time.time()) if self._jobs else None)
                if self._stopping:
                    return
                _, _, fn, args = heapq.heappop(self._jobs)
            try:
                fn(*args)
            except Exception:
                logging.exception("RetroAchievements: unexpected error")

    def stop(self):
        with self._cv:
            self._stopping = True
            self._cv.notify()
        self._thread.join(timeout=5)

    # -- games -------------------------------------------------------------

    def prepare(self, game, local_set):
        """Works out the game, gets its set and starts a session, then posts
        ('set', (RaSet, hash)), ('hash', hash), ('titles', [title]),
        ('session', unlocked IDs), ('noset', why) or ('note', text) to
        game.inbox."""
        self._later(0, self._prepare, game, local_set, 0)

    def _rom_hash(self, code):
        if not self.roms:
            return None
        try:
            found = RomIndex(self.roms, os.path.join(self.cache_dir, "roms.json")).find(code)
        except OSError as e:
            logging.warning(f"RetroAchievements: can't look through {self.roms}: {e}")
            return None
        if found:
            logging.info(f"RetroAchievements: {code} is {found[0]} (hash {found[1]})")
            return found[1]
        return None

    def _title_list(self, console_id):
        path = os.path.join(self.cache_dir, f"systemgames-{console_id}.json")
        try:
            if time.time() - os.path.getmtime(path) < TITLE_LIST_DAYS * 86400:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, ValueError):
            pass
        games = self.api.system_games(console_id)
        slim = [{"ID": g["ID"], "Title": g.get("Title", ""), "NumAchievements": g.get("NumAchievements", 0)}
                for g in games]
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(slim, f)
        except OSError:
            pass
        return slim

    def titles(self, game):
        """The titles to look a game up by: its header's, else GameTDB's for
        its code (core/game_titles.py)."""
        if game.header_title:
            return [game.header_title]
        return game_titles.titles(game.code, self.cache_dir)

    def candidates(self, header_title):
        """[(score, game)] RetroAchievements games whose title could be the
        header's, best first; game has .id, .title, .achievements."""
        items = []
        for console in (ra_set.NINTENDO_DS, ra_set.NINTENDO_DSI):
            for g in self._title_list(console):
                items.append(types.SimpleNamespace(id=int(g["ID"]), title=g.get("Title", ""),
                                                   achievements=g.get("NumAchievements", 0)))
        return ra_cache.candidates(header_title, items), ra_cache.auto_pick(header_title, items)

    def download(self, game_id=None, game_hash=None, code=None):
        """Downloads a game's set into ra/<code>.json and returns it (RaSet)."""
        data = self.api.game_sets(game_id=None if game_hash else game_id, game_hash=game_hash)
        try:
            s = ra_set.RaSet(data)
        except (ra_set.SetFileError, KeyError, ValueError, TypeError) as e:
            raise RAError(f"unexpected set data: {e}")
        if not s.id:
            raise RAError("RetroAchievements doesn't know this game")
        os.makedirs(self.ra_dir, exist_ok=True)
        dest = os.path.join(self.ra_dir, f"{code}.json")
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, dest)
        return ra_set.load(dest)

    def _prepare(self, game, local, attempt):
        code = game.code
        if not code:
            return
        try:
            game_hash = self._rom_hash(code)
            game_id = self.api.game_id_for_hash(game_hash) if game_hash else 0
            if game_hash and not game_id:
                logging.info(f"RetroAchievements doesn't know the hash of your {code} file "
                             "(a version it doesn't support?)")
                game_hash = None
            if game_hash:
                game.inbox.put(("hash", game_hash))
            if not game_id and local:
                game_id = local.id
            titles = [] if game_id else self.titles(game)
            if titles:
                game.inbox.put(("titles", titles))
            maybe = []
            for title in titles:
                ranked, pick = self.candidates(title)
                if pick:
                    game_id = pick.id
                    logging.info(f"RetroAchievements: {code} '{title}' is {pick.title} "
                                 f"(game {pick.id}), going by its title")
                    break
                maybe = maybe or ranked
            if not game_id and maybe:
                game.inbox.put(("noset", f"{len(maybe)} games there could be this one: "
                                         "pick it with 'dsirpc.py setup'"))
                return
            if not game_id:
                game.inbox.put(("noset", f"no game called '{titles[0]}' there" if titles
                                else f"can't tell what {code} is called"))
                return
            stale = local is None or local.id != game_id or \
                time.time() - os.path.getmtime(local.path) > REFRESH_SET_AFTER
            if stale:
                s = self.download(game_id, game_hash, code)
                logging.info(f"RetroAchievements: downloaded {s.summary()} as ra/{code}.json")
                game.inbox.put(("set", (s, game_hash)))
            settings = self.settings
            if settings is None or settings.profile or settings.submit:
                unlocked = self.api.start_session(game_id, game_hash)
                game.inbox.put(("session", unlocked))
        except RANetworkError as e:
            delay = min(120, 15 * (attempt + 1))
            logging.warning(f"RetroAchievements: {e}; trying again in {delay} s")
            # Meanwhile an RA emulator's cache may have the set (core/ra_game.py)
            game.inbox.put(("note" if local else "noset", f"can't connect ({e})"))
            self._later(delay, self._prepare, game, local, attempt + 1)
        except (RAError, OSError) as e:
            logging.warning(f"RetroAchievements: {code}: {e}")
            game.inbox.put(("note", str(e)))

    def ping(self, game_id, rich_presence, game_hash=None):
        self._later(0, self._ping, game_id, rich_presence, game_hash)

    def _ping(self, game_id, rich_presence, game_hash):
        try:
            self.api.ping(game_id, rich_presence, game_hash)
            logging.debug(f"RetroAchievements: ping {game_id} {rich_presence!r}")
        except RAError as e:
            logging.info(f"RetroAchievements: ping failed: {e}")

    # -- unlocks -----------------------------------------------------------

    def _save_pending(self):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            tmp = self.pending_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._pending, f, indent=1)
            os.replace(tmp, self.pending_file)
        except OSError as e:
            logging.warning(f"RetroAchievements: can't save {self.pending_file}: {e}")

    def _load_pending(self):
        try:
            with open(self.pending_file, encoding="utf-8") as f:
                pending = json.load(f)
        except (OSError, ValueError):
            return
        with self._lock:
            self._pending = [p for p in pending if isinstance(p, dict) and p.get("id")]
            mine = [p for p in self._pending if p.get("user") == self.api.username]
        for p in mine:
            logging.info(f"RetroAchievements: sending achievement {p['id']} from {time.ctime(p['when'])}")
            self._later(0, self._award, p, 0)

    def award(self, game, achievement_id, game_hash=None):
        entry = {"id": int(achievement_id), "hash": game_hash, "when": int(time.time()),
                 "user": self.api.username, "game": game.title}
        with self._lock:
            self._pending.append(entry)
            self._save_pending()
        self._later(0, self._award, entry, 0)

    def _done(self, entry):
        with self._lock:
            if entry in self._pending:
                self._pending.remove(entry)
            self._save_pending()

    def _award(self, entry, attempt):
        if entry.get("user") != self.api.username or not self.signed_in:
            return  # signed out or another account: kept in the file for later
        late = int(time.time()) - entry["when"]
        try:
            answer = self.api.award(entry["id"], entry.get("hash"), late if late >= 10 else 0)
        except RANetworkError as e:
            delay = 0 if attempt == 0 else min(120, 2 ** (attempt - 1))
            logging.warning(f"RetroAchievements: achievement {entry['id']} not sent yet ({e}); "
                            f"trying again in {delay} s")
            self._later(delay, self._award, entry, attempt + 1)
            return
        except RAError as e:
            logging.error(f"RetroAchievements didn't take achievement {entry['id']}: {e}")
            self._done(entry)
            return
        self._done(entry)
        if answer.get("AlreadyHad"):
            logging.info(f"RetroAchievements: you already had achievement {entry['id']}")
        else:
            left = answer.get("AchievementsRemaining")
            logging.info(f"RetroAchievements: achievement {entry['id']} sent (softcore score "
                         f"{answer.get('SoftcoreScore', '?')}" + (f", {left} left in the game)" if left is not None else ")"))
