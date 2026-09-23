"""
dsi_memory.py - read the real DSi's RAM through DSiRPC's memory request protocol.

DsiRam looks like the 4 MB RAM dump that PlatinumParser expects
(len() and slicing by offset from 0x02000000), but it only fetches the parts
that actually get read. Fetched data is cached in 64-byte blocks until
clear() is called, so one parse sees one consistent-ish snapshot and the next
parse starts fresh.

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
