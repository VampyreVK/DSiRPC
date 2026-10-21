"""
unlocks.py - every achievement DSiRPC knows you've unlocked, wherever it
happened: on the console (offline play, or its checker while connected) or
here, sent to RetroAchievements or not (sending is a choice in setup, and
RetroAchievements can be out of reach). The console's offline sets mark
these earned (app/engine.py), so a console never loses an unlock it handed
over while RetroAchievements hasn't had it yet, and the ones
RetroAchievements doesn't have are sent when sending is on.

    ra/cache/local_unlocks.json    {"<achievement ID>": when (a Unix time, 0 if not known)}

Achievement IDs are RetroAchievements' own, unique across games, so the
file needs no game.
"""

import json
import logging
import os
import threading

from . import ra_set

LEDGER_FILE = os.path.join(ra_set.RA_DIR, "cache", "local_unlocks.json")


class UnlockLedger:
    def __init__(self, path=LEDGER_FILE):
        self.path = path
        self._lock = threading.Lock()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        out = {}
        if isinstance(data, dict):
            for aid, when in data.items():
                try:
                    out[int(aid)] = int(when or 0)
                except (TypeError, ValueError):
                    continue
        return out

    def times(self, ids=None):
        """{ID: when} for every unlock known here, or only those among ids."""
        with self._lock:
            have = self._read()
        if ids is None:
            return have
        return {aid: when for aid, when in have.items() if aid in ids}

    def add(self, unlocks):
        """Notes unlocks ({ID: when}); an earlier time wins over a later one,
        and any time over none. Returns the IDs that weren't known yet."""
        new = set()
        with self._lock:
            have = self._read()
            changed = False
            for aid, when in unlocks.items():
                aid, when = int(aid), int(when or 0)
                old = have.get(aid)
                if old is None:
                    new.add(aid)
                if old is None or (when and (not old or when < old)):
                    have[aid] = when
                    changed = True
            if changed:
                try:
                    os.makedirs(os.path.dirname(self.path), exist_ok=True)
                    with open(self.path + ".tmp", "w", encoding="utf-8") as f:
                        json.dump({str(aid): have[aid] for aid in sorted(have)}, f)
                    os.replace(self.path + ".tmp", self.path)
                except OSError as e:
                    logging.warning(f"Can't save {self.path}: {e}")
        return new
