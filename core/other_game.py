"""
other_game.py - any game without its own parser (everything but Pokemon
Platinum), while it runs on the DSi.

What DSiRPC knows about it comes from its RetroAchievements side
(core/ra_game.py): the game code from the DSi's hellos (gc=), the title from
the set or the game's own header, and, if there's a set, its rich presence
text and achievement progress. The overlay's game card
(overlay/gamecard.py) shows all of it.

OtherGame.read() returns the state the hub hands out for such a game:

    {'kind': 'other', 'game': {...from the hello...}, 'title': 'Mario Kart DS',
     'header_title': 'MARIOKART DS', 'ra_set': RaSet or None,
     'rich_presence': 'Racing in Figure-8 Circuit' or None,
     'progress': (12, 132) or None, 'started': time.time(),
     'unlocked': frozenset of achievement IDs (RetroAchievements' and this
     session's), 'recent': [(achievement ID, time.time()), ...] this
     session's last few unlocks, oldest first, 'ra_note': why there's no
     set (or what's being fetched) or None, 'signed_in': True/False}
"""

import time


class OtherGame:
    HELLO_TIMEOUT = 15.0

    def __init__(self, game, ra_game, client=None):
        """`ra_game`: the game's core/ra_game.RaGame (read by its owner, the
        hub's source); `client`: the DSiClient, used to tell whether the DSi
        is still there when there's no rich presence being read (None for a
        RAM dump)."""
        self.game = game
        self.code = (game or {}).get("code")
        self.ra = ra_game
        self.client = client
        self.started = time.time()

    @property
    def title(self):
        return self.ra.title

    @property
    def reading(self):
        """True while the RetroAchievements side reads the DSi's memory."""
        return bool(self.ra.runtime)

    def describe(self):
        return self.ra.describe()

    def _dsi_there(self):
        if self.client is None:
            return True
        if self.ra.runtime:
            return self.ra.read_ok
        last = self.client.hellos[-1][0] if self.client.hellos else 0.0
        return time.time() - last < self.HELLO_TIMEOUT

    def read(self):
        """The state now, or None if the DSi isn't answering."""
        if not self._dsi_there():
            return None
        return {
            'kind': 'other',
            'game': self.game,
            'title': self.title,
            'header_title': self.ra.header_title or None,
            'ra_set': self.ra.set,
            'rich_presence': self.ra.rich_presence,
            'progress': self.ra.progress,
            'started': self.started,
            'unlocked': frozenset(self.ra.unlocked),
            'recent': self.ra.session_unlocks[-3:],
            'ra_note': self.ra.note,
            'signed_in': bool(self.ra.link and self.ra.link.signed_in),
        }

    def close(self):
        pass
