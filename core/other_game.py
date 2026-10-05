"""
other_game.py - any game without its own parser (everything but Pokemon
Platinum), while it runs on the DSi.

What DSiRPC knows about it:
  - the game code from the DSi's hellos (gc=), and the title from the game's
    own header in main RAM (core/ra_cache.read_header)
  - its RetroAchievements set, if there's a set file in ra/ (core/ra_set.py),
    or one can be found in an RA emulator's cache (core/ra_cache.py, the
    racache setting in dsirpc.cfg)
  - the set's rich presence text, evaluated against the live memory
    (core/ra_presence.py)

OtherGame.read() returns the state the hub hands out for such a game:

    {'kind': 'other', 'game': {...from the hello...}, 'title': 'Mario Kart DS',
     'header_title': 'MARIOKART DS', 'ra_set': RaSet or None,
     'rich_presence': 'Racing in Figure-8 Circuit' or None, 'started': time.time()}
"""

import logging
import time

from . import games
from . import ra_cache
from . import ra_set


class OtherGame:
    HELLO_TIMEOUT = 15.0

    def __init__(self, game, ram, client=None, racache=None, auto_import=True, ra_dir=ra_set.RA_DIR):
        """`ram`: core/dsi_memory.DsiRam (or a RAM dump's bytes); `client`:
        the DSiClient, used to tell whether the DSi is still there when
        there's no rich presence to read (None for a RAM dump); `racache`:
        an RA emulator's folder to look for the set in, if ra/ has none."""
        self.game = game
        self.code = (game or {}).get("code")
        self.ram = ram
        self.client = client
        self.racache = racache
        self.auto_import = auto_import
        self.ra_dir = ra_dir
        self.ra = None
        self.reader = None
        self.header_title = None
        self.header_tries = 0
        self.started = time.time()
        self.note = None    # why there's no set, for status lines
        self._load_set()

    def _load_set(self):
        try:
            self.ra = ra_set.for_game(self.code, self.ra_dir)
        except ra_set.SetFileError as e:
            logging.warning(f"RetroAchievements set file for {self.code}: {e}")
            self.note = "its set file in ra/ can't be read"
            return
        if not self.ra:
            self.note = "no RetroAchievements set file in ra/"
            return
        self.note = None
        if self.ra.rich_presence:
            try:
                from .ra_presence import RichPresenceReader
                from .rcheevos import RcheevosError
                try:
                    self.reader = RichPresenceReader(self.ra, self.ram)
                except RcheevosError as e:
                    logging.warning(f"{self.ra.title}: {e}; showing the game without it")
            except ImportError as e:
                logging.warning(f"rich presence unavailable: {e}")

    def _read_header(self):
        """The title from the game's header (once; a few tries if the DSi
        doesn't answer). Only trusted when the header's code is the hello's."""
        if self.header_title is not None or self.header_tries >= 3:
            return
        self.header_tries += 1
        try:
            title, code = ra_cache.read_header(self.ram)
        except (TimeoutError, RuntimeError):
            return
        self.header_title = title if title and code == self.code else ""

    def _try_import(self):
        """Looks for this game's set in the RA emulator's cache, and copies
        it into ra/ if exactly one clearly matches."""
        if self.ra or not (self.racache and self.auto_import and self.header_title):
            return
        self.auto_import = False  # once per session
        sets = ra_cache.scan(self.racache)
        pick = ra_cache.auto_pick(self.header_title, sets)
        if not pick:
            n = len(ra_cache.candidates(self.header_title, sets))
            if n:
                self.note = f"{n} possible sets in the RA cache: pick one with 'dsirpc.py setup'"
            logging.info(f"{games.name(self.game)}: no set in the RA cache clearly matches "
                         f"'{self.header_title}' ({n} possible)")
            return
        dest = ra_cache.import_set(pick, self.code, self.ra_dir)
        if dest:
            logging.info(f"{games.name(self.game)}: copied {pick.summary()} from the RA cache to {dest}")
            self._load_set()

    @property
    def title(self):
        if self.ra and self.ra.title:
            return self.ra.title
        if self.code in games.NAMES:
            return games.NAMES[self.code]
        return self.header_title or self.code or "a DS game"

    def describe(self):
        name = games.name(self.game)
        if not self.ra:
            return f"{name}: {self.note or 'no RetroAchievements set'}, showing the game only"
        rp = "with its rich presence" if self.reader else "no rich presence"
        return f"{name}: {self.ra.summary()}; {rp}"

    def _dsi_there(self):
        if self.client is None:
            return True
        last = self.client.hellos[-1][0] if self.client.hellos else 0.0
        return time.time() - last < self.HELLO_TIMEOUT

    def read(self):
        """The state now, or None if the DSi isn't answering. Raises
        TimeoutError/RuntimeError when a rich presence read fails."""
        if self.header_title is None:
            self._read_header()
            self._try_import()
        text = None
        if self.reader:
            text = self.reader.read()
        elif not self._dsi_there():
            return None
        return {
            'kind': 'other',
            'game': self.game,
            'title': self.title,
            'header_title': self.header_title or None,
            'ra_set': self.ra,
            'rich_presence': text or None,
            'started': self.started,
        }

    def close(self):
        if self.reader:
            self.reader.close()
            self.reader = None
