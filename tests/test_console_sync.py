"""core/console_sync.py, the launcher's side door into DSiRPC: the launcher
finds it with a UDP broadcast, then over TCP hands over the console's
unlocks and takes the sets it doesn't have (core/offline.py has the
formats). The launcher here is a stand-in for launcher/source/sync.c."""

import errno
import socket
import struct
import time

import pytest

from core import console_sync, offline
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

    def on_console(self, ip, game, console):
        self.consoles.append((ip, game, console))


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


def test_the_launchers_still_here_and_bye():
    heard = []
    engine = Engine()
    sync = ConsoleSync(engine.sets_for, engine.on_unlocks, engine.on_console, port=0, host=HOST,
                       on_here=lambda ip, here, console: heard.append((ip, here, console)))
    sync.start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(offline.HERE + bytes([2]), (HOST, sync.port))     # a 3DS, still in the launcher
        s.sendto(offline.BYE, (HOST, sync.port))                   # leaving it
        s.close()
        end = time.monotonic() + 5
        while len(heard) < 2 and time.monotonic() < end:
            time.sleep(0.02)
        assert heard == [(HOST, True, "3DS"), (HOST, False, "DSi")]
        assert discover(sync.port) is not None                     # and the door still works
    finally:
        sync.stop()


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
    assert engine.consoles == [(HOST, "IRBO", "DSi")]


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
    assert engine.consoles == [(HOST, None, "DSi")] and engine.unlocks == []   # nothing to hand over


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


def test_a_3ds_says_so(start):
    """The request's last word is TWiLight's CONSOLE_MODEL: 2 and 3 are a 3DS
    and a New 3DS, 0 a DSi (and what older launchers send)."""
    engine = Engine()
    sync = start(engine)
    for model, console in ((2, "3DS"), (3, "3DS"), (0, "DSi"), (1, "DSi")):
        assert exchange(sync.port, offline.build_request("", {}, b"", console_model=model))[0] == 0
    end = time.monotonic() + 8
    while len(engine.consoles) < 4 and time.monotonic() < end:
        time.sleep(0.02)
    assert [c for _, _, c in engine.consoles] == ["3DS", "3DS", "DSi", "DSi"]


def test_port_0_takes_a_number_free_for_both(monkeypatch):
    """The tests' port 0: the number the system picks for UDP can be taken for
    TCP (by a connection that just closed, say), as it was once on GitHub's
    runner, so another is tried. A fixed port that's taken still says so."""
    taken = {"n": 2}

    class Busy(socket.socket):
        def bind(self, address):
            if self.type == socket.SOCK_STREAM and taken["n"]:
                taken["n"] -= 1
                raise OSError(errno.EADDRINUSE, "Address already in use")
            return super().bind(address)

    monkeypatch.setattr(console_sync.socket, "socket", Busy)
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST)
    sync.start()
    try:
        assert taken["n"] == 0 and sync.port != 0
    finally:
        sync.stop()

    taken["n"] = 1
    with pytest.raises(OSError):
        ConsoleSync(lambda *a: [], lambda u: None, port=sync.port, host=HOST).start()
