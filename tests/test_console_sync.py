"""core/console_sync.py, the launcher's side door into DSiRPC: the launcher
finds it with a UDP broadcast, then over TCP hands over the console's
unlocks and takes the sets it doesn't have (core/offline.py has the
formats). The launcher here is a stand-in for launcher/source/sync.c."""

import socket
import struct
import time

import pytest

from core import offline
from core.console_sync import ConsoleSync

HOST = "127.0.0.1"


def _recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("DSiRPC hung up")
        buf += chunk
    return buf


def discover(port, payload=offline.DISCOVER + bytes([offline.VERSION])):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1.5)
    try:
        s.sendto(payload, (HOST, port))
        return s.recvfrom(64)[0]
    except socket.timeout:
        return None
    finally:
        s.close()


def exchange(port, raw):
    """Sends a request, reads the answer, hangs up: (status, taken, [(code, bytes)])."""
    with socket.create_connection((HOST, port), timeout=5) as c:
        c.sendall(raw)
        magic, version, status, taken, n, _ = offline.ANSWER_HEADER.unpack(_recv_exact(c, offline.ANSWER_HEADER.size))
        assert (magic, version) == (b"DRSA", offline.VERSION)
        sets = []
        for _ in range(n):
            code, size = struct.unpack("<4sI", _recv_exact(c, 8))
            sets.append((code.decode(), _recv_exact(c, size)))
    return status, taken, sets


class Engine:
    """app/engine.py's callbacks, recorded."""

    def __init__(self, sets=(), keep=False, fail=False):
        self.sets, self.keep, self.fail = list(sets), keep, fail
        self.asked, self.unlocks, self.consoles = [], [], []

    def sets_for(self, game, stamps, unlocks):
        self.asked.append((game, dict(stamps), [u["id"] for u in unlocks]))
        if self.fail:
            raise RuntimeError("no sets today")
        return self.sets

    def on_unlocks(self, unlocks):
        self.unlocks.append([u["id"] for u in unlocks])
        return False if self.keep else None

    def on_console(self, ip, game):
        self.consoles.append((ip, game))


@pytest.fixture
def start():
    started = []

    def go(engine, port=0):
        sync = ConsoleSync(engine.sets_for, engine.on_unlocks, engine.on_console, port=port, host=HOST)
        sync.start()
        started.append(sync)
        return sync
    yield go
    for sync in started:
        sync.stop()


def _wait_last(sync, secs=8):
    end = time.monotonic() + secs
    while sync.last is None and time.monotonic() < end:
        time.sleep(0.02)
    return sync.last


def _unlocks(*ids):
    when = offline.console_clock(time.time() - 3600)
    data = bytearray(offline.empty_unlock_file())
    for i, aid in enumerate(ids, start=1):
        data[i * 16:(i + 1) * 16] = offline.unlock_slot(aid, "IRBO", when, i)
    return bytes(data)


def test_discovery(start):
    sync = start(Engine())
    assert sync.port != 0
    assert discover(sync.port) == offline.ANSWER + struct.pack("<BH", offline.VERSION, sync.port)
    assert discover(sync.port, b"something else") is None


def test_unlocks_handed_over_and_sets_taken(start):
    engine = Engine(sets=[("IRBO", b"black's set"), ("CPUE", b"platinum's")])
    sync = start(engine)
    status, taken, sets = exchange(sync.port, offline.build_request("IRBO", {"CPUE": 7}, _unlocks(11, 12, 13)))
    assert (status, taken) == (0, 3)
    assert sets == [("IRBO", b"black's set"), ("CPUE", b"platinum's")]
    last = _wait_last(sync)
    assert last["game"] == "IRBO" and last["taken"] == 3 and last["sets"] == ["IRBO", "CPUE"]
    assert engine.asked == [("IRBO", {"CPUE": 7}, [11, 12, 13])]
    assert engine.unlocks == [[11, 12, 13]]
    assert engine.consoles == [(HOST, "IRBO")]


def test_dry_run_leaves_the_unlocks(start):
    engine = Engine(keep=True)
    sync = start(engine)
    assert exchange(sync.port, offline.build_request("IRBO", {}, _unlocks(5)))[:2] == (0, 0)
    assert engine.unlocks == [[5]]


def test_connected_without_a_game(start):
    engine = Engine()
    sync = start(engine)
    assert exchange(sync.port, offline.build_request(None, {}, b"")) == (0, 0, [])
    assert _wait_last(sync)["game"] is None
    assert engine.consoles == [(HOST, None)] and engine.unlocks == []   # nothing to hand over


def test_a_bad_request_gets_status_1(start):
    engine = Engine()
    sync = start(engine)
    assert exchange(sync.port, b"HELLO THERE, DSIRPC!" + bytes(8)) == (1, 0, [])
    assert engine.asked == [] and engine.consoles == []
    # and the next launcher is still served
    assert exchange(sync.port, offline.build_request("IRBO", {}, b""))[0] == 0


def test_sets_failing_still_takes_the_unlocks(start):
    engine = Engine(fail=True)
    sync = start(engine)
    assert exchange(sync.port, offline.build_request("IRBO", {}, _unlocks(1, 2))) == (0, 2, [])


def test_port_taken_then_free_again(start):
    first = start(Engine())
    with pytest.raises(OSError):
        ConsoleSync(lambda *a: [], lambda u: None, port=first.port, host=HOST).start()
    port = first.port
    first.stop()
    assert not first._thread.is_alive()
    again = start(Engine(), port=port)
    assert discover(port) == offline.ANSWER + struct.pack("<BH", offline.VERSION, again.port)
