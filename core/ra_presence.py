"""
ra_presence.py - a game's RetroAchievements rich presence, evaluated against
the DSi's live memory with rcheevos (core/rcheevos.py).

    reader = RichPresenceReader(ra_set, ram)   # ram: core/dsi_memory.DsiRam, or a RAM dump's bytes
    text = reader.read()                       # e.g. "Exploring Jubilife City - 3 badges"

Rich presence is read every few seconds, like Discord is updated, not every
frame. Each read fetches every address the script used last time in one
batch (DsiRam packs them into as few requests as it can), then evaluates the
script; anything new it touches (say a pointer now points elsewhere) is
fetched on the spot and joins the batch from then on.

RetroAchievements addresses for the DS are main RAM offsets (0x000000 is
0x02000000). Anything beyond main RAM (the DSi's extra RAM, the ARM9's data
TCM) can't be read over the network and reads as 0.
"""

import logging

from .rcheevos import Runtime


class RichPresenceReader:
    def __init__(self, ra_set, ram):
        if not ra_set.rich_presence:
            raise ValueError(f"{ra_set.title} has no rich presence script")
        self.ra_set = ra_set
        self.ram = ram
        self.runtime = Runtime()
        self.runtime.set_rich_presence(ra_set.rich_presence)  # RcheevosError if it doesn't parse
        self.known = []          # [(address, length)] the script read last time
        self.unreadable = set()  # addresses outside main RAM, logged once each
        self._seen = set()

    def _peek(self, address, num_bytes):
        self._seen.add((address, num_bytes))
        if address + num_bytes > len(self.ram):
            if address not in self.unreadable:
                self.unreadable.add(address)
                logging.warning(f"{self.ra_set.title}: rich presence reads 0x{address:06X}, "
                                "outside main RAM; it reads as 0")
            return 0
        return int.from_bytes(self.ram[address:address + num_bytes], "little")

    def read(self):
        """Evaluates the script against the memory as it is now. Raises
        TimeoutError/RuntimeError if the DSi doesn't answer."""
        if hasattr(self.ram, "clear"):
            self.ram.clear()
        if self.known and hasattr(self.ram, "prefetch"):
            self.ram.prefetch([(a, n) for a, n in self.known if a + n <= len(self.ram)])
        self._seen = set()
        self.runtime.frame(self._peek)
        text = self.runtime.rich_presence(self._peek)
        self.known = sorted(self._seen)
        return text

    def close(self):
        self.runtime.close()
