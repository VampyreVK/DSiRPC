"""
dsi_memory.py - read the real DSi's RAM through DSiRPC's memory request protocol.

DsiRam looks like the 4 MB RAM dump that PlatinumParser expects
(len() and slicing by offset from 0x02000000), but it only fetches the parts
that actually get read. Fetched data is cached in 64-byte blocks until
clear() is called, so one parse sees one consistent-ish snapshot and the next
parse starts fresh. SparseRam does the same with exact byte ranges, for the
scattered small values RetroAchievements sets read.

The UDP protocol client itself is core/dsirpc_client.py.
"""

from .dsirpc_client import DSiClient


def connect(port=4244, dsi_ip=None, timeout=1.0, verbose=False, max_wait=15.0):
    """Opens the UDP socket and waits for a hello from the DSi (unless dsi_ip
    is given). Returns the client, or None if the DSi never said hello."""
    client = DSiClient(port=port, dsi_ip=dsi_ip, timeout=timeout, verbose=verbose)
    if not client.wait_for_dsi(max_wait):
        return None
    return client


class DsiRam:
    BASE = 0x02000000
    SIZE = 0x400000  # main RAM, same as a full RAM dump
    BLOCK = 64

    def __init__(self, client):
        self.client = client
        self._blocks = {}
        self.bytes_fetched = 0
        self.batches = 0

    def clear(self):
        self._blocks.clear()
        self.bytes_fetched = 0
        self.batches = 0

    def __len__(self):
        return self.SIZE

    def prefetch(self, ranges):
        """ranges: [(offset from BASE, length), ...]. Fetches every block they
        touch that isn't cached yet, in one batch (read_ranges packs it into
        as few requests as the protocol allows)."""
        wanted = set()
        for start, length in ranges:
            if length <= 0:
                continue
            start = max(start, 0)
            stop = min(start + length, self.SIZE)
            for b in range(start // self.BLOCK, (stop - 1) // self.BLOCK + 1):
                if b not in self._blocks:
                    wanted.add(b)
        if not wanted:
            return

        # Neighbouring blocks become one range.
        runs = []
        for b in sorted(wanted):
            if runs and runs[-1][0] + runs[-1][1] == b:
                runs[-1][1] += 1
            else:
                runs.append([b, 1])

        data = self.client.read_ranges([(self.BASE + b * self.BLOCK, n * self.BLOCK) for b, n in runs])
        for (b, n), chunk in zip(runs, data):
            for k in range(n):
                self._blocks[b + k] = chunk[k * self.BLOCK:(k + 1) * self.BLOCK]
        self.bytes_fetched += sum(n * self.BLOCK for _, n in runs)
        self.batches += 1

    def __getitem__(self, key):
        if isinstance(key, int):
            return self[key:key + 1][0]
        start, stop, step = key.indices(self.SIZE)
        if step != 1:
            raise ValueError("DsiRam only supports contiguous slices")
        if stop <= start:
            return b""
        self.prefetch([(start, stop - start)])
        first = start // self.BLOCK
        joined = b"".join(self._blocks[b] for b in range(first, (stop - 1) // self.BLOCK + 1))
        offset = start - first * self.BLOCK
        return joined[offset:offset + (stop - start)]


class SparseRam:
    """Like DsiRam, but fetches exactly the bytes asked for (ranges less than
    GAP bytes apart become one), for many small values spread over memory,
    like a RetroAchievements set's: Mario Kart DS's 100 or so values fit in
    one request this way, where 64-byte blocks would take several. Cached
    until clear()."""

    BASE = DsiRam.BASE
    SIZE = DsiRam.SIZE
    GAP = 16

    def __init__(self, client):
        self.client = client
        self._ranges = []        # sorted, non-overlapping [start, bytes]
        self.bytes_fetched = 0
        self.batches = 0

    def clear(self):
        self._ranges = []
        self.bytes_fetched = 0
        self.batches = 0

    def __len__(self):
        return self.SIZE

    def _find(self, start, stop):
        lo, hi = 0, len(self._ranges)
        while lo < hi:  # last range starting at or before `start`
            mid = (lo + hi) // 2
            if self._ranges[mid][0] <= start:
                lo = mid + 1
            else:
                hi = mid
        if lo:
            s, data = self._ranges[lo - 1]
            if stop <= s + len(data):
                return data[start - s:stop - s]
        return None

    def _store(self, start, data):
        stop = start + len(data)
        keep, merged_start, merged = [], start, data
        for s, d in self._ranges:
            e = s + len(d)
            if e < merged_start or s > merged_start + len(merged):
                keep.append([s, d])
                continue
            # overlapping or touching: join, the new bytes win
            lo = min(s, merged_start)
            buf = bytearray(max(e, merged_start + len(merged)) - lo)
            buf[s - lo:e - lo] = d
            buf[merged_start - lo:merged_start - lo + len(merged)] = merged
            merged_start, merged = lo, bytes(buf)
        keep.append([merged_start, merged])
        keep.sort(key=lambda r: r[0])
        self._ranges = keep
        return stop

    def prefetch(self, ranges):
        """ranges: [(offset from BASE, length), ...]: fetches the ones that
        aren't cached yet, in one batch."""
        wanted = []
        for start, length in sorted(ranges):
            start = max(0, start)
            stop = min(start + length, self.SIZE)
            if stop <= start or self._find(start, stop) is not None:
                continue
            if wanted and start <= wanted[-1][1] + self.GAP:
                wanted[-1][1] = max(wanted[-1][1], stop)
            else:
                wanted.append([start, stop])
        if not wanted:
            return
        data = self.client.read_ranges([(self.BASE + a, b - a) for a, b in wanted])
        for (a, b), chunk in zip(wanted, data):
            self._store(a, chunk)
        self.bytes_fetched += sum(b - a for a, b in wanted)
        self.batches += 1

    def __getitem__(self, key):
        if isinstance(key, int):
            return self[key:key + 1][0]
        start, stop, step = key.indices(self.SIZE)
        if step != 1:
            raise ValueError("SparseRam only supports contiguous slices")
        if stop <= start:
            return b""
        got = self._find(start, stop)
        if got is None:
            self.prefetch([(start, stop - start)])
            got = self._find(start, stop)
        return got
