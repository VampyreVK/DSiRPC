"""core/dsirpc_client.py against helpers/fake_dsi.py over loopback UDP:
finding the DSi from its hellos, reads split to fit the console's limits,
refusals, lost and late replies, the per-frame capture, unlocks pushed to
the console, the console checker's reports, and watch()."""

import io
import os
import sys
import time

import pytest

import core.dsirpc_client as dc
from helpers.fake_dsi import FakeDsi, free_port, pc_socket_only

pytestmark = pytest.mark.realtime


@pytest.fixture
def dsi(monkeypatch):
    pc_socket_only(monkeypatch)
    fakes, clients = [], []

    def start(**kw):
        port = free_port()
        fake = FakeDsi(port, **kw)
        fake.start()
        fakes.append(fake)
        client = dc.DSiClient(port=port, timeout=0.3)
        clients.append(client)
        assert client.wait_for_dsi(max_wait=5), "no hello from the fake DSi"
        return fake, client
    yield start
    for fake in fakes:
        fake.stop()
    for client in clients:
        client.sock.close()


def test_finds_the_dsi_and_its_game(dsi):
    fake, client = dsi(code="IRBO")
    assert client.dsi_ip == "127.0.0.2"
    assert client.game == {"code": "IRBO", "version": 1, "header_crc": 0x1234}
    assert dc.game_from_hello("DSiRPC hello #3") is None          # an older build: no game


def test_reads_are_split_to_fit(dsi):
    fake, client = dsi()
    fake.poke(0x02000000, os.urandom(1000))
    for i in range(20):
        fake.poke(0x02100000 + 64 * i, os.urandom(7))
    ranges = [(0x02000000, 1000)] + [(0x02100000 + 64 * i, 7) for i in range(20)]
    got = client.read_ranges(ranges)
    assert got == [fake.peek(a, n) for a, n in ranges]
    assert fake.requests[b"R"] >= 6                               # 1,140 bytes, 192 a request


def test_outside_main_ram_is_refused(dsi):
    fake, client = dsi()
    with pytest.raises(dc.Refused) as e:
        client.read_ranges([(0x03800000, 4)])
    assert e.value.status == 2


def test_a_lost_reply_is_asked_again(dsi):
    fake, client = dsi()
    fake.poke(0x02000100, b"\x11\x22\x33\x44")
    fake.drop_next = 1
    assert client.read_ranges([(0x02000100, 4)]) == [b"\x11\x22\x33\x44"]
    assert fake.requests[b"R"] == 2
    fake.drop_next = 5
    with pytest.raises(TimeoutError):
        client.read_ranges([(0x02000100, 4)], retries=3)


def test_a_late_reply_is_not_taken_for_the_next(dsi):
    fake, client = dsi()
    fake.duplicate_replies = True
    fake.poke(0x02000200, b"AAAA")
    fake.poke(0x02000300, b"BBBB")
    for _ in range(5):
        assert client.read_ranges([(0x02000200, 4)]) == [b"AAAA"]
        assert client.read_ranges([(0x02000300, 4)]) == [b"BBBB"]


def _counting(ram):
    """A game: a frame counter at 0x02100000, another every other frame at 0x02100010."""
    n = int.from_bytes(ram[0x100000:0x100004], "little") + 1
    ram[0x100000:0x100004] = n.to_bytes(4, "little")
    if n % 2 == 0:
        ram[0x100010:0x100012] = (n // 2).to_bytes(2, "little")


def test_capture(dsi):
    fake, client = dsi(game=_counting)
    fake.unfresh_every = 3
    client.set_watch([(0x02100000, 4), (0x02100010, 2)])
    time.sleep(0.5)
    records, nxt = [], 0
    while len(records) < 40:
        first, lost, recs = client.fetch_frames(nxt)
        assert first == nxt and lost == 0
        records += recs
        nxt = first + len(recs)
        if not recs:
            time.sleep(0.05)
    ticks = [t for t, _, _, _ in records]
    assert ticks == list(range(len(records)))
    counter = [dc.split_values(raw, [4, 2])[0] for _, _, raw, _ in records]
    assert counter == list(range(counter[0], counter[0] + len(records)))
    halves = [dc.split_values(raw, [4, 2])[1] for _, _, raw, _ in records]
    assert all(h == c // 2 for h, c in zip(halves, counter))
    assert [i for i, (_, _, _, arm7) in enumerate(records) if arm7] == list(range(0, len(records), 3))
    assert all(vcount == 192 for _, vcount, _, _ in records)


def test_capture_overrun_and_stop(dsi):
    fake, client = dsi(game=_counting)
    client.set_watch([(0x02100000 + 4 * i, 4) for i in range(8)])   # 36-byte records: 56 in the ring
    time.sleep(1.6)
    first, lost, recs = client.fetch_frames(0)
    assert lost > 0 and first == lost and recs
    client.set_watch([])
    with pytest.raises(dc.Refused) as e:
        client.fetch_frames(0)
    assert e.value.status == 3
    with pytest.raises(ValueError):
        client.set_watch([(0x02100000, 4)] * 9)
    with pytest.raises(ValueError):
        client.set_watch([(0x02100000, 3)])


def test_pushed_unlocks(dsi):
    fake, client = dsi()
    fake.push_room = 15
    unlocks = [(900000 + i, 1000 + i) for i in range(20)]
    assert client.push_unlocks(unlocks) == 15                     # 12, then 3 of the next 8
    assert fake.pushed == unlocks[:15]
    fake.push_room = 100
    assert client.push_unlocks(unlocks[15:]) == 5


def test_console_checker_reports(dsi):
    fake, client = dsi()
    got = []
    client.ach.on_unlocks = got.append
    fake.ach_report = ("DSiRPC ach n=40 t=2 p=10 l=12 s=1 x=0 w=3 f=20 fr=60 fd=1 fc=2 h=1 st=DEADBEEF "
                       "ids=901,902")
    client.listen(2.5)
    latest = client.ach.latest
    assert (latest["loaded"], latest["unlocked"], latest["ids"], latest["stamp"]) == (40, 2, [901, 902], 0xDEADBEEF)
    assert (latest["frame_lane"], latest["frames"], latest["dropped"], latest["unclean"], latest["idle"]) == \
        (20, 60, 1, 2, 1)
    assert got == [[901, 902]]                                    # once, however often it's repeated


def test_watch_prints_what_changes(dsi, monkeypatch, capsys):
    def game(ram):
        frame = int.from_bytes(ram[0x100000:0x100004], "little") + 1
        ram[0x100000:0x100004] = frame.to_bytes(4, "little")
        ram[0x24F930] = frame & 0xFF                              # a timer: changes all the time
        if frame == 150:
            ram[0x24F925] = 0x80                                  # the player turns
        if frame == 240:
            ram[0x24F925] = 0xC0
    fake, client = dsi(game=game)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    dc.watch(client, [(0x0224F920, 0x20)], interval=0.1, settle=1.2, duration=5.0)
    out = capsys.readouterr().out
    assert "0x0224F925: 00 -> 80" in out and "0x0224F925: 80 -> C0" in out
    after_settling = out.split("Go!", 1)[1].rsplit("value(s) changed", 1)[0]
    assert "0x0224F930" not in after_settling and "0x0224F925" in after_settling   # the timer muted
    assert dc.parse_values("0-3,0x40") == {0, 1, 2, 3, 64}
