"""A fake DSi on the loopback network, speaking rpcprobe's protocol
(core/dsirpc_client.py has it): hellos once a second, 'R' reads of its main
RAM, 'W'/'F' per-frame capture, 'U' unlocks from DSiRPC, and "DSiRPC ach"
reports. With a game (step(ram) once a frame), it runs at 60 frames a second
in real time, and captures the watched values every frame like the ARM7.

The PC side binds every address on the port, so DSiClient is pointed at
127.0.0.1 alone (pc_socket_only()) and the fake gets 127.0.0.2 or another
loopback address."""

import errno
import socket
import struct
import threading
import time

import pytest

import core.dsirpc_client as dc

PC = "127.0.0.1"
RAM_BASE = 0x02000000
RING_BYTES = 2048            # rpcprobe's WATCH_RING_BYTES
MAX_REPLY = 192              # rpcprobe's reply data limit


def free_port(dsi_ip="127.0.0.2"):
    """A UDP port free on both the PC's address and the fake DSi's. Skips
    the test where the fake DSi's address doesn't exist (macOS has only
    127.0.0.1 until `sudo ifconfig lo0 alias 127.0.0.2`)."""
    for _ in range(50):
        a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        a.bind((PC, 0))
        port = a.getsockname()[1]
        b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            b.bind((dsi_ip, port))
            return port
        except OSError as e:
            if e.errno == errno.EADDRNOTAVAIL:
                pytest.skip(f"no {dsi_ip} on this system for the fake DSi")
            continue
        finally:
            a.close()
            b.close()
    raise RuntimeError("no free port")


class _PcSocket(socket.socket):
    def bind(self, addr):
        super().bind((PC, addr[1]) if addr[0] == "0.0.0.0" else addr)


def pc_socket_only(monkeypatch):
    """Makes DSiClient bind 127.0.0.1 instead of every address."""
    monkeypatch.setattr(dc.socket, "socket", _PcSocket)


class FakeDsi(threading.Thread):
    def __init__(self, port, ram=None, code="TEST", dsi_ip="127.0.0.2", game=None, hello_every=1.0):
        super().__init__(daemon=True)
        self.port, self.code, self.dsi_ip = port, code, dsi_ip
        self.ram = bytearray(ram) if ram is not None else bytearray(0x400000)
        self.game = game                     # step(ram) once a frame, or None
        self.hello_every = hello_every
        self.lock = threading.Lock()
        self.frame = 0
        self.requests = {b"R": 0, b"W": 0, b"F": 0, b"U": 0}
        self.watches, self.ring, self.written = [], [], 0
        self.unfresh_every = 0               # mark every n-th record "no write-back" (0: never)
        self.pushed = []                     # [(id, when)] from 'U'
        self.push_room = 1000                # how many more 'U' unlocks it takes
        self.drop_next = 0                   # requests to ignore (the reply was lost)
        self.duplicate_replies = False       # send every reply twice
        self.ach_report = None               # a "DSiRPC ach ..." text sent after each hello
        self.stop_flag = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket.socket.bind(self.sock, (dsi_ip, port))
        self.sock.settimeout(0.002)

    def stop(self):
        self.stop_flag = True
        self.join(timeout=3)
        self.sock.close()

    # -- memory --------------------------------------------------------------------

    def poke(self, addr, data):
        with self.lock:
            self.ram[addr - RAM_BASE:addr - RAM_BASE + len(data)] = data

    def peek(self, addr, n):
        return bytes(self.ram[addr - RAM_BASE:addr - RAM_BASE + n])

    # -- the loop ------------------------------------------------------------------

    def run(self):
        t0 = time.time()
        next_hello = t0
        while not self.stop_flag:
            now = time.time()
            if now >= next_hello:
                self._hello()
                next_hello = now + self.hello_every
            if self.game is not None and now >= t0 + self.frame / 60.0:
                with self.lock:
                    self.game(self.ram)
                    self._capture()
                self.frame += 1
                continue
            self._serve()

    def _hello(self):
        n = int(self.frame / 60) if self.game else int(time.time())
        self.sock.sendto(f"DSiRPC hello #{n} gc={self.code} v=01 hc=1234 a9=2 vb=12 rx=0 req=0".encode(),
                         (PC, self.port))
        if self.ach_report:
            self.sock.sendto(self.ach_report.encode(), (PC, self.port))

    def _capture(self):
        if not self.watches:
            return
        vals = b"".join(self.peek(a, n) for a, n in self.watches)
        vcount = 192 | (0x8000 if self.unfresh_every and self.written % self.unfresh_every == 0 else 0)
        self.ring.append(struct.pack(">HH", self.written & 0xFFFF, vcount) + vals)
        slots = RING_BYTES // self._rec_size()
        if len(self.ring) > slots:
            self.ring.pop(0)
        self.written += 1

    def _rec_size(self):
        return 4 + sum(n for _, n in self.watches)

    def _serve(self):
        try:
            data, addr = self.sock.recvfrom(2048)
        except (socket.timeout, OSError):
            return
        if len(data) < 4 or data.startswith(b"DSiRPC"):
            return
        kind, seq, count = data[0:1], struct.unpack(">H", data[1:3])[0], data[3]
        if kind in self.requests:
            self.requests[kind] += 1
        if self.drop_next:
            self.drop_next -= 1
            return
        with self.lock:
            n, status, out = self._answer(kind, count, data)
        reply = struct.pack(">cHBB", b"D", seq, n, status) + (out if status in (0,) else b"")
        self.sock.sendto(reply, addr)
        if self.duplicate_replies:
            self.sock.sendto(reply, addr)

    def _answer(self, kind, count, data):
        if kind == b"R":
            if count > 16 or len(data) < 4 + 5 * count:
                return count, 1, b""
            out = b""
            for i in range(count):
                a, ln = struct.unpack(">IB", data[4 + 5 * i:9 + 5 * i])
                if not RAM_BASE <= a < RAM_BASE + 0x400000 or a + ln > RAM_BASE + 0x400000:
                    return count, 2, b""
                out += self.peek(a, ln)
            if len(out) > MAX_REPLY:
                return count, 1, b""
            return count, 0, out
        if kind == b"W":
            n = count & 0x7F
            self.watches = [struct.unpack(">IB", data[4 + 5 * i:9 + 5 * i]) for i in range(n)]
            self.ring, self.written = [], 0
            return count, 0, b""
        if kind == b"F":
            if not self.watches:
                return 0, 3, b""
            want = struct.unpack(">H", data[4:6])[0]
            have = len(self.ring)
            back = (self.written - want) & 0xFFFF
            lost = max(0, back - have)
            back = min(back, have)
            first = self.written - back
            room = min((MAX_REPLY - 5) // self._rec_size(), 255)
            recs = self.ring[have - back:have - back + room]
            return len(recs), 0, struct.pack(">HHB", first & 0xFFFF, lost, self._rec_size()) + b"".join(recs)
        if kind == b"U":
            taken = 0
            for i in range(count):
                if self.push_room <= 0:
                    return taken, 3, b""
                self.pushed.append(struct.unpack(">II", data[4 + 8 * i:12 + 8 * i]))
                self.push_room -= 1
                taken += 1
            return taken, 0, b""
        return 0, 1, b""
