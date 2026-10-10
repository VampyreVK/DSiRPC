"""
frame_capture.py - checking achievements frame by frame on the PC, from the
DSi's per-frame capture (core/dsirpc_client.py's set_watch() and
fetch_frames(); rpcprobe/probe_watch.c on the console).

DSiRPC's usual reads come about once a second, so for rcheevos one "frame"
is a whole second: a flag that's set for one frame is missed, a ResetIf can
miss what should reset it, and hit counts count seconds. The capture reads
up to 8 values (1, 2 or 4 bytes each) at the start of every VBlank into a
ring on the console, which this drains a few times a second, and each
record is one real frame for rcheevos. So the achievements whose memory
fits in those 8 values are checked exactly as on an emulator; core/ra_game.py
picks which (the ones that need it most, that the console doesn't already
check every frame) and checks the rest the usual way.

    cap = FrameCapture(client)
    ids = cap.use([(id, memaddr), ...])  # in order of need: the ones that fit
    cap.service()                        # a few times a second: [triggered ids]
    cap.stop()

An achievement only fits if every address it reads is fixed: one with
AddAddress (I:) reads where a pointer in memory says, so it's left out.
"""

import logging
import time

from . import dsirpc_client
from .rcheevos import Runtime, RcheevosError

RAM_SIZE = 0x400000
RAM_BASE = 0x02000000


def footprint(memaddr):
    """{(RetroAchievements address, bytes)} an achievement reads, or None if
    that depends on memory (AddAddress) or it doesn't parse."""
    if "I:" in memaddr:
        return None
    rt = Runtime()
    seen = set()
    try:
        rt.activate_achievement(1, memaddr)
        rt.frame(lambda a, n: seen.add((a, n)) or 0)
    except RcheevosError:
        return None
    finally:
        rt.close()
    if any(a + n > RAM_SIZE for a, n in seen):
        return None
    return seen


def windows(reads):
    """The fewest watches (address, 1/2/4 bytes) covering every byte of
    `reads` ({(address, bytes)}), in address order."""
    need = sorted({a + k for a, n in reads for k in range(n)})
    out, i = [], 0
    while i < len(need):
        start = need[i]
        last = start
        while i < len(need) and need[i] < start + 4:
            last = need[i]
            i += 1
        size = last - start + 1
        size = 4 if size == 3 else size
        if start + size > RAM_SIZE:
            size = RAM_SIZE - start
        out.append((start, size))
    return out


class FrameCapture:
    FETCH_EVERY = 0.25      # seconds between drains (the ring holds about a second at worst)
    MAX_FETCHES = 8         # requests per drain

    def __init__(self, client):
        self.client = client
        self.ids = []           # the achievements checked frame by frame
        self.watches = []       # [(RA address, bytes)]
        self.runtime = None
        self.next = 0           # the next record number wanted
        self.due = 0.0
        self.frames = 0         # records checked
        self.lost = 0           # records the ring lost before they were fetched
        self.failed = 0         # drains that got no reply
        self.resent = 0         # times the console held another watch list's records
        self._map = []          # [(address, offset in a record)] per byte

    @property
    def active(self):
        return self.runtime is not None

    def use(self, achievements):
        """achievements: [(id, memaddr)], most needed first. Checks as many
        as fit in the capture's watches from now on (each time the one that
        needs the fewest more watches, the most needed of those), and starts
        the capture again if its watches change; returns their ids."""
        left = [(i, aid, memaddr, fp) for i, (aid, memaddr) in enumerate(achievements)
                for fp in [footprint(memaddr)] if fp]
        chosen, reads, wins = [], set(), []
        while left:
            best = None
            for k, (i, aid, memaddr, fp) in enumerate(left):
                w = windows(reads | fp)
                if len(w) <= dsirpc_client.MAX_WATCHES and (best is None or (len(w), i) < best[0]):
                    best = ((len(w), i), k, w)
            if best is None:
                break
            i, aid, memaddr, fp = left.pop(best[1])
            chosen.append((aid, memaddr))
            reads |= fp
            wins = best[2]
        ids = [aid for aid, _ in chosen]
        if ids == self.ids and wins == self.watches and self.runtime:
            return ids
        self.stop(send=not chosen)
        if not chosen:
            return []
        rt = Runtime()
        for aid, memaddr in chosen:
            rt.activate_achievement(aid, memaddr)
        try:
            self.client.set_watch([(RAM_BASE + a, n) for a, n in wins], retries=2)
        except (TimeoutError, RuntimeError) as e:
            logging.info(f"Per-frame checking couldn't start: {e}")
            rt.close()
            return []
        self.runtime, self.ids, self.watches = rt, ids, wins
        self._map, off = [], 0
        for a, n in wins:
            self._map += [(a + k, off + k) for k in range(n)]
            off += n
        self.next, self.due = 0, time.time() + self.FETCH_EVERY
        logging.info(f"Checking {len(ids)} achievement(s) on the PC every frame (from {len(wins)} watched values)")
        return ids

    def service(self):
        """Drains the ring if it's time: each record is a frame for
        rcheevos. Returns the achievements that triggered."""
        if not self.runtime or time.time() < self.due:
            return []
        self.due = time.time() + self.FETCH_EVERY
        triggered = []
        for _ in range(self.MAX_FETCHES):
            try:
                first, lost, records = self.client.fetch_frames(self.next, retries=1, timeout=0.3)
            except dsirpc_client.Refused as e:
                if e.status == 3:  # no watch list: the console started over (another game, or a reset)
                    self._restart()
                return triggered
            except (TimeoutError, RuntimeError):
                self.failed += 1
                return triggered
            if records and len(records[0][2]) != sum(n for _, n in self.watches):
                # Not this watch list's records (the console came back still
                # holding an older one): give it ours again and start over.
                if not self.resent:
                    logging.info("Per-frame checking: the console's records aren't this watch list's; sending it again")
                self.resent += 1
                self._restart()
                return triggered
            if lost:
                self.lost += lost
                logging.debug(f"Per-frame checking: {lost} frame(s) were gone before they could be fetched")
            for _, _, raw, _ in records:
                mem = {a: raw[o] for a, o in self._map}

                def peek(address, n, mem=mem):
                    return int.from_bytes(bytes(mem.get(address + k, 0) for k in range(n)), "little")
                for name, aid, _ in self.runtime.frame(peek):
                    if name == "achievement_triggered":
                        triggered.append(aid)
                        self.runtime.deactivate_achievement(aid)
                self.frames += 1
            self.next = (first + len(records)) & 0xFFFF
            full = (dsirpc_client.MAX_DATA - 5) // (4 + sum(n for _, n in self.watches))
            if len(records) < min(full, 255):
                break  # caught up
        return triggered

    def drop(self, aid):
        """An achievement unlocked elsewhere (the console, or the 1 Hz check)."""
        if aid in self.ids:
            self.ids.remove(aid)
            if self.runtime:
                self.runtime.deactivate_achievement(aid)

    def _restart(self):
        try:
            self.client.set_watch([(RAM_BASE + a, n) for a, n in self.watches], retries=1)
            self.next = 0
            if self.runtime:
                self.runtime.reset()
        except (TimeoutError, RuntimeError):
            pass

    def stop(self, send=True):
        if self.runtime:
            self.runtime.close()
            self.runtime = None
            if send:
                try:
                    self.client.set_watch([], retries=1)
                except (TimeoutError, RuntimeError):
                    pass
        self.ids, self.watches, self._map = [], [], []
