"""tools/frame_check.py, the frame-by-frame capture check: its analysis of
a VBlank counter's steps, what it says about the ARM9 half, its arguments,
log files, and its capture and counter search against a fake DSi client."""

import csv
import time
from pathlib import Path

import pytest

from tools import frame_check as fc


def rec(n, value, scanline=192, unfresh=False):
    """A capture record: (record number, tick, scanline, [values], no write-back before it)."""
    return (n, n, scanline, [value], unfresh)


def test_analyse_steps():
    records = [rec(0, 0), rec(1, 1), rec(2, 2), rec(3, 2), rec(4, 3, 200, unfresh=True), rec(5, 5, 194), rec(6, 6),
               None,                                       # records lost: no step across
               rec(9, 10), rec(10, 11), rec(11, 3), rec(12, 4),
               None,
               rec(14, 0xFFFFFFFF), rec(15, 0)]            # wraps: +1
    out = fc.analyse(records)
    assert out["steps"] == 6 + 3 + 1
    assert out["ups"] == 4 + 2 + 1
    assert out["still"] == 1
    assert out["resets"] == 1
    assert out["catchups"] == [(1, 200, 194)]              # one count seen a frame late
    assert out["late_unfresh"] == 1                        # and that read had no write-back before it
    assert out["increase"] == 6 + 2 + 1


def test_analyse_nothing():
    assert fc.analyse([])["steps"] == 0
    assert fc.analyse([None, rec(0, 5), None])["steps"] == 0


@pytest.mark.parametrize("a9,says", [
    (None, "not in this build"),
    ("0", "not found (a9=0)"),
    ("junk", "not found (a9=0)"),
    ("1", "found (a9=1)"),
    ("2", "a9=2: 1 copy)"),
    ("3", "a9=3: 2 copies)"),
])
def test_a9_status(a9, says):
    assert says in fc.a9_status(a9)


def test_arguments():
    assert fc.parse_watch("0x021BF6A8:4") == (0x021BF6A8, 4)
    assert fc.parse_watch("0x021BF6A8:2") == (0x021BF6A8, 2)
    assert fc.parse_watch("0x02000000") == (0x02000000, 4)
    assert fc.parse_span("0x021BF000:0x1000") == (0x021BF000, 0x1000)
    assert fc.parse_span("0x02000000") == (0x02000000, 0x1000)


def test_log_paths():
    assert fc.log_paths("boot") == (fc.LOGS_DIR / "boot.csv", fc.LOGS_DIR / "boot.txt")
    assert fc.log_paths("boot.csv") == (fc.LOGS_DIR / "boot.csv", fc.LOGS_DIR / "boot.txt")
    assert fc.log_paths("runs/today") == (Path("runs/today.csv"), Path("runs/today.txt"))


def test_save_csv(tmp_path):
    path = tmp_path / "run.csv"
    fc.save_csv(path, [(0x021BF6A8, 4), (0x02100000, 2)],
                [(0, 0, 192, [7, 9], False), None, (2, 2, 193, [8, 9], True)])
    rows = list(csv.reader(open(path, newline="")))
    assert rows == [["record", "tick", "scanline", "read_by", "0x021BF6A8", "0x02100000"],
                    ["0", "0", "192", "arm9", "7", "9"], ["lost"], ["2", "2", "193", "arm7", "8", "9"]]


class FakeClient:
    """The DSi's capture ('W' and 'F', core/dsirpc_client.py) from a list of
    records, five at a time; records 20 to 24 are lost, and every fourth
    fetch times out."""

    def __init__(self, n=60):
        self.records = [(i, 192 + i % 3, (100 + i).to_bytes(4, "little") + (7).to_bytes(2, "little"), i % 5 == 0)
                        for i in range(n)]
        self.watches, self.calls = None, 0

    def set_watch(self, watches, arm7_only=False):
        self.watches = list(watches)

    def fetch_frames(self, nxt, timeout=0.3):
        self.calls += 1
        if self.calls % 4 == 0:
            raise TimeoutError
        if 20 <= nxt < 25:   # overwritten before they were fetched
            return 25, 25 - nxt, self.records[25:30]
        return nxt, 0, self.records[nxt:nxt + 5]


def test_capture():
    client = FakeClient()
    records, stats = fc.capture(client, [(0x021BF6A8, 4), (0x02100000, 2)], 0.8)
    assert client.watches == []                            # switched off at the end
    got = [r for r in records if r]
    assert [r[0] for r in got] == list(range(0, 20)) + list(range(25, 60))
    assert records[20] is None                             # the gap is marked
    assert got[0][3] == [100, 7] and got[-1][3] == [159, 7] and got[5][4] is True
    assert stats["records"] == 55 and stats["lost"] == 5 and stats["timeouts"] >= 1
    a = fc.analyse(records)
    assert a["ups"] == a["steps"] == 53 and not a["catchups"]


class CounterRam:
    """read_ranges() over RAM where 0x02100010 counts up 60 times a second
    and 0x02100020 30 times; everything else stands still."""

    def __init__(self):
        self.t0 = time.time()

    def read_ranges(self, ranges):
        out = []
        for addr, n in ranges:
            data = bytearray(n)
            for a, rate in ((0x02100010, 60), (0x02100020, 30)):
                if addr <= a < addr + n:
                    data[a - addr:a - addr + 4] = int((time.time() - self.t0) * rate + 1000).to_bytes(4, "little")
            out.append(bytes(data))
        return out


@pytest.mark.realtime
def test_find_counters():
    found = fc.find_counters(CounterRam(), 0x02100000, 0x100)
    assert [a for a, _ in found] == [0x02100010, 0x02100020]
    assert abs(found[0][1] - 60) < 6 and abs(found[1][1] - 30) < 3
