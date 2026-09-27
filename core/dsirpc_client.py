#!/usr/bin/env python3
"""
dsirpc_client.py - PC client for the DSi memory request protocol.

Speaks the protocol in nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/probe_req.c
(UDP, big endian):

  Request  PC -> DSi:  'R' | seq u16 | count u8 | count x (addr u32, len u8)
  Response DSi -> PC:  'D' | seq u16 | count u8 | status u8 | data...

status: 0 OK, 1 malformed/too big, 2 range outside main RAM
(0x02000000-0x023FFFFF). At most 16 ranges and 192 bytes per request;
read_ranges() splits bigger jobs automatically.

The DSi also broadcasts "DSiRPC hello ..." packets once a second on the same
port. This client uses the first one to learn the DSi's IP (or pass --dsi-ip,
for example on a network that drops broadcasts), so don't run another tool
on the same port at the same time (hello_listener.py, dsi_status.py,
dsirpc.py) - they'd fight over it.

Usage, from the repo root:
  python core/dsirpc_client.py                             # smoke test (see --read)
  python core/dsirpc_client.py --read 0x02000BBC:8 0x02101D40:4
  python core/dsirpc_client.py --read 0x02000BBC:8 --repeat 10 --interval 1
  python core/dsirpc_client.py --dsi-ip 192.168.2.195 --read 0x02000000:64
  python core/dsirpc_client.py --stats 60                  # link check, see link_stats()
"""

import argparse
import collections
import re
import socket
import struct
import sys
import time

MAX_RANGES = 16
MAX_DATA = 192
STATUS_TEXT = {0: "ok", 1: "malformed or too big", 2: "range outside main RAM"}


class DSiClient:
    def __init__(self, port=4244, dsi_ip=None, timeout=1.0, verbose=False):
        self.port = port
        self.dsi_ip = dsi_ip
        self.timeout = timeout
        self.verbose = verbose
        self.seq = 0
        self.last_hello = None
        self.hellos = collections.deque(maxlen=600)  # (time received, text)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))

    def _handle_other(self, data, addr):
        """Anything that isn't the reply we're waiting for (mostly hellos)."""
        if data.startswith(b"DSiRPC hello"):
            self.last_hello = data.decode(errors="replace")
            self.hellos.append((time.time(), self.last_hello))
            if self.dsi_ip is None:
                self.dsi_ip = addr[0]
                print(f"DSi found at {self.dsi_ip} ({self.last_hello})")
            elif self.verbose:
                print(f"  hello: {self.last_hello}")
        elif self.verbose:
            print(f"  ignored {len(data)} bytes from {addr[0]}:{addr[1]}")

    def wait_for_dsi(self, max_wait=15.0):
        """Block until a hello tells us the DSi's IP (if not given)."""
        deadline = time.time() + max_wait
        self.sock.settimeout(1.0)
        while self.dsi_ip is None and time.time() < deadline:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            self._handle_other(data, addr)
        return self.dsi_ip is not None

    def _request_once(self, ranges, retries=3, timeout=None):
        self.seq = (self.seq + 1) & 0xFFFF
        pkt = struct.pack(">cHB", b"R", self.seq, len(ranges))
        for a, n in ranges:
            pkt += struct.pack(">IB", a, n)

        for attempt in range(retries):
            self.sock.sendto(pkt, (self.dsi_ip, self.port))
            deadline = time.time() + (timeout or self.timeout)
            while time.time() < deadline:
                self.sock.settimeout(max(0.01, deadline - time.time()))
                try:
                    data, addr = self.sock.recvfrom(2048)
                except socket.timeout:
                    break
                if len(data) >= 5 and data[0:1] == b"D" and not data.startswith(b"DSiRPC"):
                    _, seq, count, status = struct.unpack(">cHBB", data[:5])
                    if seq != self.seq:
                        continue  # late reply to an older request
                    if status != 0:
                        raise RuntimeError(f"DSi refused request: {STATUS_TEXT.get(status, status)}")
                    body = data[5:]
                    want = sum(n for _, n in ranges)
                    if len(body) < want:
                        raise RuntimeError(f"short reply: {len(body)} of {want} bytes")
                    out, off = [], 0
                    for _, n in ranges:
                        out.append(body[off:off + n])
                        off += n
                    return out
                self._handle_other(data, addr)
            if self.verbose:
                print(f"  timeout (attempt {attempt + 1}/{retries})")
        raise TimeoutError("no reply from the DSi")

    def read_ranges(self, ranges, timeout=None, retries=3):
        """[(addr, length), ...] -> [bytes, ...]. Splits into as many requests
        as needed. Each request waits `timeout` seconds for its reply (the
        client's default if None) and is sent up to `retries` times."""
        pieces = []  # (index into ranges, addr, len)
        for i, (a, n) in enumerate(ranges):
            while n > 0:
                chunk = min(n, MAX_DATA)
                pieces.append((i, a, chunk))
                a += chunk
                n -= chunk

        results = [b""] * len(ranges)
        batch, batch_bytes = [], 0
        def flush():
            nonlocal batch, batch_bytes
            if not batch:
                return
            got = self._request_once([(a, n) for _, a, n in batch], retries, timeout)
            for (i, _, _), data in zip(batch, got):
                results[i] += data
            batch, batch_bytes = [], 0
        for p in pieces:
            if len(batch) == MAX_RANGES or batch_bytes + p[2] > MAX_DATA:
                flush()
            batch.append(p)
            batch_bytes += p[2]
        flush()
        return results


def _hello_fields(text):
    return {k: v for k, v in re.findall(r"(\w+)=(\S+)", text)}


def _listen_until(c, until):
    """Takes in hellos (and drops late replies) until `until`, so their
    arrival times are accurate."""
    while True:
        left = until - time.time()
        if left <= 0:
            return
        c.sock.settimeout(left)
        try:
            data, addr = c.sock.recvfrom(2048)
        except socket.timeout:
            return
        if data.startswith(b"DSiRPC"):  # replies (late ones) are dropped
            c._handle_other(data, addr)


def link_stats(c, seconds, rate=4.0):
    """Link check: sends a small read `rate` times a second for `seconds`
    and prints how many came back and how fast, next to what the DSi's own
    hello counters say: `req` (requests it answered), `rx` (every frame it
    drained from the wifi chip, other devices' broadcasts included) and the
    spacing of the hellos (about 1 s normally; the DSi puts a hello off while
    it's part way through draining a big frame, so a longer spacing means it
    was busy draining). Unicast frames lost over the air are resent by the
    wifi itself, so a request the DSi never answered was almost certainly
    dropped inside the DSi's wifi chip."""
    c.hellos.clear()
    sends = []  # (time sent, answered, latency)
    t_end = time.time() + seconds
    print(f"Sending a small read every {1.0 / rate:g} s (or when the last one times out) for {seconds:g} s...")
    while time.time() < t_end:
        t0 = time.time()
        try:
            c.read_ranges([(0x02000BBC, 8)], retries=1)
            sends.append((t0, True, time.time() - t0))
        except (TimeoutError, RuntimeError):
            sends.append((t0, False, None))
        _listen_until(c, t0 + 1.0 / rate)
    _listen_until(c, time.time() + 2.5)  # one more hello, so the counters cover the last requests

    answered = [lat for _, ok, lat in sends if ok]
    lost = len(sends) - len(answered)
    print(f"\nReads: {len(sends)} sent, {len(answered)} answered, {lost} lost "
          f"({100.0 * lost / max(1, len(sends)):.0f}%)")
    if answered:
        lat = sorted(answered)
        median, p90 = lat[len(lat) // 2], lat[min(len(lat) - 1, int(0.9 * len(lat)))]
        print(f"Reply time: median {median * 1000:.0f} ms, 90% under {p90 * 1000:.0f} ms, "
              f"worst {lat[-1] * 1000:.0f} ms")

    hellos = [(t, _hello_fields(text)) for t, text in c.hellos]
    hellos = [(t, f) for t, f in hellos if 'rx' in f and 'req' in f]
    if len(hellos) < 2:
        print("Not enough hellos with counters to compare (is this the stage 5 build?)")
        return
    (t0, f0), (t1, f1) = hellos[0], hellos[-1]
    span = t1 - t0
    d_req = (int(f1['req']) - int(f0['req'])) & 0xFFFF
    d_rx = (int(f1['rx']) - int(f0['rx'])) & 0xFFFF
    sent_in_span = sum(1 for t, _, _ in sends if t0 <= t < t1)
    ok_in_span = sum(1 for t, ok, _ in sends if ok and t0 <= t < t1)
    gaps = [b[0] - a[0] for a, b in zip(hellos, hellos[1:])]
    vb = max(int(f.get('vb', 0)) for _, f in hellos)
    print(f"DSi side over {span:.0f} s: answered {d_req} of the {sent_in_span} requests sent in that time; "
          f"we got {ok_in_span} replies")
    print(f"Frames drained: {d_rx / span:.1f}/s ({(d_rx - d_req) / span:.1f}/s not ours)")
    print(f"Hello spacing: average {sum(gaps) / len(gaps):.2f} s, longest {max(gaps):.2f} s; longest tick vb={vb}")
    modes = {'53': "CMD53 block transfers", '52': "CMD52, one byte per command"}
    if 'rxm' in f1:
        print(f"The DSi reads its wifi chip with: {modes.get(f1['rxm'], f1['rxm'])}; "
              f"failed CMD53 reads: {f1.get('e53', '?')}")
    if 'txm' in f1:
        d_rep = (int(f1.get('rep', 0)) - int(f0.get('rep', 0))) & 0xFFFF
        print(f"The DSi sends with: {modes.get(f1['txm'], f1['txm'])}; failed CMD53 writes: {f1.get('t53', '?')}; "
              f"requests we had to send again: {d_rep} (total {f1.get('rep', '?')})")
    lost_in = sent_in_span - d_req
    lost_out = d_req - ok_in_span
    tol = max(2, 0.05 * sent_in_span)  # requests in flight at either end of the window
    if lost_in > tol:
        print(f"-> {lost_in} requests never reached the game side: the DSi isn't draining its wifi "
              "chip as fast as frames arrive, so the chip drops some.")
    if lost_out > tol:
        print(f"-> {lost_out} replies were sent but never arrived (lost on the way back).")
    if lost_in <= tol and lost_out <= tol:
        print("-> Hardly anything lost.")


def hexdump(addr, data):
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexpart = " ".join(f"{b:02X}" for b in chunk)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  0x{addr + off:08X}: {hexpart:<47}  {text}")


def parse_range(s):
    addr, _, length = s.partition(":")
    return int(addr, 0), int(length or "16", 0)


def main():
    ap = argparse.ArgumentParser(description="DSiRPC stage 5 memory client")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (the DSi always uses 4244)")
    ap.add_argument("--dsi-ip", help="the IP the launcher shows; skips waiting for a hello packet")
    ap.add_argument("--read", nargs="+", type=parse_range, metavar="ADDR:LEN",
                    default=[(0x02000BBC, 8)],
                    help="ranges to read (default: the SDK marker in Platinum's "
                         "main code, which should read 21 06 C0 DE DE C0 06 21)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=1.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--stats", type=float, metavar="SECONDS",
                    help="link check: send small reads for this long and report losses and delays")
    args = ap.parse_args()

    c = DSiClient(port=args.port, dsi_ip=args.dsi_ip, timeout=args.timeout, verbose=args.verbose)
    if not c.wait_for_dsi():
        print("No hello from the DSi within 15 s - is the game running after the handoff?")
        sys.exit(1)

    if args.stats:
        link_stats(c, args.stats)
        return

    ok = fail = 0
    for i in range(args.repeat):
        try:
            t0 = time.time()
            results = c.read_ranges(args.read)
            ms = (time.time() - t0) * 1000
            print(f"read #{i + 1} ({ms:.0f} ms):")
            for (a, _), data in zip(args.read, results):
                hexdump(a, data)
            ok += 1
        except (TimeoutError, RuntimeError) as e:
            print(f"read #{i + 1}: {e}")
            fail += 1
        if i < args.repeat - 1:
            time.sleep(args.interval)

    print(f"\n{ok} ok, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
