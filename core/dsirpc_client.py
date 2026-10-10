#!/usr/bin/env python3
"""
dsirpc_client.py - PC client for the DSi memory request protocol.

Speaks the protocol in nds-bootstrap/retail/cardenginei/arm7/source/rpcprobe/probe_req.c
(UDP, big endian):

  Request  PC -> DSi:  'R' | seq u16 | count u8 | count x (addr u32, len u8)
  Response DSi -> PC:  'D' | seq u16 | count u8 | status u8 | data...

status: 0 OK, 1 malformed/too big, 2 range outside main RAM
(0x02000000-0x023FFFFF), 3 no watch list. At most 16 ranges and 192 bytes
per request; read_ranges() splits bigger jobs automatically.

Per-frame capture (rpcprobe/probe_watch.h): set_watch() sends a 'W' with up
to 8 values to read every VBlank, and fetch_frames() drains the records with
'F'. Same transport and reply header as 'R'. Each record says whether the
ARM9 read the values (through its cache, so never late, at the start of each
VBlank; builds whose hellos say a9=1 or more) or the ARM7 read main RAM
itself (may lag the game's writes).

The DSi also broadcasts "DSiRPC hello ..." packets once a second on the same
port. This client uses the first one to learn the DSi's IP (or pass --dsi-ip,
for example on a network that drops broadcasts), so don't run another tool
on the same port at the same time (DSiRPC itself, or the tools in tools/) -
they'd fight over it. Newer builds also say which game is
running (gc=, v=, hc=); see DSiClient.game.

Builds with offline play's achievement checker (rpcprobe/probe_ach.c) also
send "DSiRPC ach ..." a moment after each hello while the game has a set:
how many achievements the console is checking (and how many of them every
frame), what it has unlocked, how fast it goes, and which set it runs.
DSiClient logs them (see AchReport), so the console's unlocks can be
compared with DSiRPC's own. push_unlocks() tells the console about
achievements DSiRPC unlocked itself ('U'), so nds-bootstrap's in-game menu
shows them and the console stops checking them. On a DSi, "DSiRPC lid ..."
says the lid closed, so the console turned its Wi-Fi off for the rest of the
game; that's logged too.

Usage, from the repo root:
  python core/dsirpc_client.py                             # smoke test (see --read)
  python core/dsirpc_client.py --read 0x02000BBC:8 0x02101D40:4
  python core/dsirpc_client.py --read 0x02000BBC:8 --repeat 10 --interval 1
  python core/dsirpc_client.py --dsi-ip 192.168.2.195 --read 0x02000000:64
  python core/dsirpc_client.py --stats 60                  # link check, see link_stats()
  python core/dsirpc_client.py --watch 0x0224F924:2 --settle 5   # print what changes, see watch()
"""

import argparse
import collections
import logging
import re
import socket
import struct
import sys
import threading
import time

MAX_RANGES = 16
MAX_DATA = 192
MAX_WATCHES = 8
MAX_PUSH = 12             # unlocks in one 'U' (rpcprobe's receive buffer)
WATCH_ARM7_ONLY = 0x80    # in the 'W' count: the ARM7 reads everything itself
REC_ARM7 = 0x8000         # in a record's scanline field: the ARM7 read it
STATUS_TEXT = {0: "ok", 1: "malformed or too big", 2: "range outside main RAM", 3: "no watch list set"}


class Refused(RuntimeError):
    """The DSi answered with a status other than 0 (STATUS_TEXT; for 'U',
    3 means it only took `count`)."""

    def __init__(self, status, count):
        super().__init__(f"DSi refused request: {STATUS_TEXT.get(status, status)}")
        self.status = status
        self.count = count


def game_from_hello(text):
    """{'code': 'CPUE', 'version': 1, 'header_crc': 0x1234} from a hello, or
    None if the DSi's build doesn't report the game (older rpcprobe)."""
    f = _hello_fields(text)
    if 'gc' not in f:
        return None
    try:
        return {'code': f['gc'], 'version': int(f.get('v', '0'), 16),
                'header_crc': int(f.get('hc', '0'), 16)}
    except ValueError:
        return None


# What "DSiRPC ach n=" says when it isn't a number of achievements (probe_ach.h)
ACH_ERRORS = {-1: "RPCSET.BIN isn't a set this nds-bootstrap can read (update nds-bootstrap and DSiRPC together)",
              -2: "RPCSET.BIN is another game's set (start the game from the launcher)",
              -3: "the set is too big for the memory set aside for it",
              -4: "the set's program doesn't add up",
              -5: "RPCSET.BIN is damaged"}


class AchReport:
    """Follows the console's "DSiRPC ach" reports and logs what's new: the
    checker starting (or why it can't), each unlock, the unlocks saved to
    the SD card (or not), and once a minute how it goes (passes over the
    pass lane a second, the longest the checker took in one VBlank, in
    scanlines, a frame having 263; and for the frame lane, the frames it
    checked, the ones it couldn't sample because its checking fell behind,
    and the samples taken without the ARM9's cache write-back).
    on_unlocks(ids), if set, gets each batch of new unlocks (core/hub.py
    hands them to core/ra_game.py, which counts them right away), and
    on_report(latest) every report (which set the console runs)."""

    def __init__(self):
        self.latest = None
        self.latest_at = 0.0
        self.on_unlocks = None
        self.on_report = None
        self._loaded = None
        self._unlocked = self._saved = self._lost = 0
        self._reports = 0
        self._passes = self._lines = 0
        self._frames = self._dropped = self._unclean = 0
        self._run = 0             # counts the checker's starts (a new game, or the same one again)

    def take(self, text):
        f = _hello_fields(text)
        try:
            loaded = int(f.get("n", "0"))
            unlocked = int(f.get("t", "0"))
            passes, lines = int(f.get("p", "0")), int(f.get("l", "0"))
            saved, lost, waiting = int(f.get("s", "0")), int(f.get("x", "0")), int(f.get("w", "0"))
            frame_lane, frames = int(f.get("f", "0")), int(f.get("fr", "0"))
            dropped, unclean, idle = int(f.get("fd", "0")), int(f.get("fc", "0")), int(f.get("h", "0"))
            stamp = int(f["st"], 16) if f.get("st") else None
            ids = [int(i) for i in f["ids"].split(",")] if f.get("ids") else []
        except ValueError:
            return
        self.latest = {'loaded': loaded, 'unlocked': unlocked, 'passes': passes, 'lines': lines,
                       'saved': saved, 'lost': lost, 'waiting': waiting, 'ids': ids, 'frame_lane': frame_lane,
                       'frames': frames, 'dropped': dropped, 'unclean': unclean, 'idle': idle, 'stamp': stamp}
        self.latest_at = time.time()
        if loaded != self._loaded or unlocked < self._unlocked:  # another game, or the same one again
            self._run += 1
            self._loaded = loaded
            self._unlocked = self._saved = self._lost = 0
            self._reports = self._passes = self._lines = 0
            self._frames = self._dropped = self._unclean = 0
            if loaded > 0:
                logging.info(f"Console: checking {loaded} achievement(s) in game (offline play's checker)"
                             + (f", {frame_lane} of them every frame" if frame_lane else "")
                             + (f"; {waiting} unlocked earlier wait on its SD card for DSiRPC" if waiting else ""))
            elif loaded < 0:
                logging.warning(f"Console: no achievement checker: {ACH_ERRORS.get(loaded, loaded)}")
        self.latest['run'] = self._run
        if self.on_report:
            self.on_report(self.latest)
        new = unlocked - self._unlocked
        if new > 0:
            for aid in ids[-new:]:
                logging.info(f"Console: its checker unlocked achievement {aid}")
            self._unlocked = unlocked
            if self.on_unlocks and ids:
                self.on_unlocks(ids[-new:])
        if saved > self._saved:
            logging.info(f"Console: saved {saved - self._saved} unlock(s) to its SD card for DSiRPC")
            self._saved = saved
        if lost > self._lost:
            logging.warning(f"Console: couldn't save {lost - self._lost} unlock(s) to its SD card "
                            f"(no RPCUNLK.BIN, or it's full: start games from the DSiRPC launcher)")
            self._lost = lost
        self._reports += 1
        self._passes += passes
        self._lines = max(self._lines, lines)
        self._frames += frames
        self._dropped += dropped
        self._unclean += unclean
        if loaded > 0 and self._reports % 60 == 0:
            where = "in the game's idle time" if idle else "in the VBlank (this game's idle time can't be used)"
            text = (f"Console: its checker ran {where}: {self._passes / 60:.1f} passes a second over the last "
                    f"minute; its longest VBlank turn took {self._lines} scanlines")
            if frame_lane:
                text += (f"; every frame: {self._frames / 60:.1f} frames a second checked, {self._dropped} "
                         f"not sampled (it fell behind), {self._unclean} sampled without the ARM9's write-back")
            logging.info(text)
            self._passes = self._lines = 0
            self._frames = self._dropped = self._unclean = 0


class DSiClient:
    def __init__(self, port=4244, dsi_ip=None, timeout=1.0, verbose=False):
        self.port = port
        self.dsi_ip = dsi_ip
        self.timeout = timeout
        self.verbose = verbose
        self.seq = 0
        self.last_hello = None
        self.game = None  # from the latest hello; see game_from_hello()
        self.hellos = collections.deque(maxlen=600)  # (time received, text)
        self._tick_report_due = 0.0  # when to log the console's VBlank tick next (_tick_report)
        self.ach = AchReport()
        self.idle_hook = None  # called between the requests of a long read (core/hub.py's capture)
        self._in_hook = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))

    def _handle_other(self, data, addr):
        """Anything that isn't the reply we're waiting for (mostly hellos)."""
        if data.startswith(b"DSiRPC hello"):
            self.last_hello = data.decode(errors="replace")
            self.hellos.append((time.time(), self.last_hello))
            self.game = game_from_hello(self.last_hello)
            self._tick_report()
            if self.dsi_ip is None:
                self.dsi_ip = addr[0]
                print(f"DSi found at {self.dsi_ip} ({self.last_hello})")
            elif self.verbose:
                print(f"  hello: {self.last_hello}")
        elif data.startswith(b"DSiRPC ach "):
            self.ach.take(data.decode(errors="replace"))
        elif data.startswith(b"DSiRPC lid"):
            logging.info("Console: its lid closed, so it turned its Wi-Fi off until a game is started "
                         "from the launcher again (it still checks and saves achievements)")
        elif self.verbose:
            print(f"  ignored {len(data)} bytes from {addr[0]}:{addr[1]}")

    def _tick_report(self):
        """Once a minute, what rpcprobe cost the console's ARM7 (its hellos'
        vb=, the longest VBlank tick since the hello before, in scanlines)
        and how busy the link was (rx= frames from the network, req=
        requests served), to tell its cost apart from the game's own."""
        now = time.time()
        if now < self._tick_report_due:
            return
        first = not self._tick_report_due
        self._tick_report_due = now + 60
        if first:
            return
        times = [at for at, _ in self.hellos if at >= now - 60]
        recent = [_hello_fields(text) for at, text in self.hellos if at >= now - 60]
        ticks = sorted(int(f['vb']) for f in recent if f.get('vb', '').isdigit())
        if len(ticks) < 2 or times[-1] - times[0] < 10:
            return
        text = (f"Console: its VBlank tick (rpcprobe) took up to {ticks[-1]} scanlines over the last minute "
                f"({ticks[len(ticks) // 2]} typical; a frame has 263)")
        try:
            rx = int(recent[-1]['rx']) - int(recent[0]['rx'])
            req = int(recent[-1]['req']) - int(recent[0]['req'])
            span = times[-1] - times[0]
            if rx >= 0 and req >= 0:  # (not across a restart)
                text += f", {rx / span:.1f} network frames and {req / span:.1f} requests a second"
        except (KeyError, ValueError):
            pass
        logging.info(text)

    def listen(self, seconds):
        """Takes in hellos for `seconds`, so .game and .last_hello stay
        current while no requests are being sent."""
        _listen_until(self, time.time() + seconds)

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

    def _exchange(self, kind, body, retries=3, timeout=None):
        """Sends `kind` | seq | `body` (sent again, same seq, while no reply
        comes) and returns the reply's (count, data). Raises RuntimeError if
        the DSi refused it, TimeoutError if nothing came back."""
        if self.dsi_ip is None:  # gone quiet (core/hub.py forgets it): nowhere to send
            raise TimeoutError("no DSi to ask")
        self.seq = (self.seq + 1) & 0xFFFF
        pkt = struct.pack(">cH", kind, self.seq) + body

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
                        raise Refused(status, count)
                    return count, data[5:]
                self._handle_other(data, addr)
            if self.verbose:
                print(f"  timeout (attempt {attempt + 1}/{retries})")
        raise TimeoutError("no reply from the DSi")

    def _request_once(self, ranges, retries=3, timeout=None):
        body = struct.pack(">B", len(ranges))
        for a, n in ranges:
            body += struct.pack(">IB", a, n)
        _, data = self._exchange(b"R", body, retries, timeout)
        want = sum(n for _, n in ranges)
        if len(data) < want:
            raise RuntimeError(f"short reply: {len(data)} of {want} bytes")
        out, off = [], 0
        for _, n in ranges:
            out.append(data[off:off + n])
            off += n
        return out

    def set_watch(self, watches, retries=3, timeout=None, arm7_only=False):
        """Per-frame capture: [(addr, size), ...] with size 1, 2 or 4, at
        most MAX_WATCHES. The DSi reads them every VBlank from now on and
        restarts its record numbering at 0. [] stops the capture.
        arm7_only: don't use the ARM9 even if it's there (for comparing)."""
        if len(watches) > MAX_WATCHES:
            raise ValueError(f"at most {MAX_WATCHES} watches")
        body = struct.pack(">B", len(watches) | (WATCH_ARM7_ONLY if arm7_only and watches else 0))
        for a, n in watches:
            if n not in (1, 2, 4):
                raise ValueError("watch sizes are 1, 2 or 4 bytes")
            body += struct.pack(">IB", a, n)
        self._exchange(b"W", body, retries, timeout)

    def fetch_frames(self, start, retries=1, timeout=None):
        """Records from number `start` (mod 65536) on, as many as fit in one
        reply: (first, lost, [(tick, scanline, raw values, by_arm7), ...]).
        `lost` is how many records from `start` on were already overwritten;
        `first` is the number of the first record returned. Ask again from
        first + len(records) for the next ones. by_arm7 is True when the ARM7
        read the values from main RAM (they can lag the game's writes) rather
        than the ARM9; ARM9 values are from the VBlank before."""
        count, data = self._exchange(b"F", struct.pack(">BH", 0, start & 0xFFFF), retries, timeout)
        if len(data) < 5:
            raise RuntimeError("short frame reply")
        first, lost, size = struct.unpack(">HHB", data[:5])
        if len(data) < 5 + count * size or size < 4:
            raise RuntimeError(f"short frame reply: {len(data) - 5} of {count * size} bytes")
        records = []
        for i in range(count):
            rec = data[5 + i * size:5 + (i + 1) * size]
            tick, vcount = struct.unpack(">HH", rec[:4])
            records.append((tick, vcount & 0x1FF, rec[4:], bool(vcount & REC_ARM7)))
        return first, lost, records

    def push_unlocks(self, unlocks, retries=2, timeout=None):
        """Achievements DSiRPC unlocked itself, for the console's checker
        and nds-bootstrap's in-game menu ('U'): [(achievement id, when)],
        when in seconds since 2000 by the console's clock. Returns how many
        the console took (fewer when it has no set running, or no room just
        then: send the rest again later). Raises TimeoutError."""
        taken = 0
        for i in range(0, len(unlocks), MAX_PUSH):
            batch = unlocks[i:i + MAX_PUSH]
            body = struct.pack(">B", len(batch)) + b"".join(struct.pack(">II", a, w) for a, w in batch)
            try:
                count, _ = self._exchange(b"U", body, retries, timeout)
            except Refused as e:  # status 3: only some taken
                return taken + (e.count if e.status == 3 else 0)
            taken += count
            if count < len(batch):
                break
        return taken

    def _between(self):
        """Runs idle_hook between the requests of a long read (not inside it)."""
        if self.idle_hook and not self._in_hook:
            self._in_hook = True
            try:
                self.idle_hook()
            except Exception:
                logging.exception("idle hook failed")
            finally:
                self._in_hook = False

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
                self._between()
            batch.append(p)
            batch_bytes += p[2]
        flush()
        return results


def _hello_fields(text):
    return {k: v for k, v in re.findall(r"(\w+)=(\S+)", text)}


def split_values(raw, sizes):
    """A frame record's raw values -> ints, one per watch (little endian,
    as they are in the DS's memory)."""
    out, off = [], 0
    for n in sizes:
        out.append(int.from_bytes(raw[off:off + n], "little"))
        off += n
    return out


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

    hellos = [(t, _hello_fields(text), text) for t, text in c.hellos]
    numbered = [(int(m.group(1)), int(f.get('vb', 0))) for _, f, text in hellos
                for m in [re.search(r"#(\d+)", text)] if m]
    hellos = [(t, f) for t, f, _ in hellos if 'rx' in f and 'req' in f]
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
    if f1.get('txm') == '53':
        # Each hello's vb covers the ticks since the hello before it,
        # including that hello's own send. Every 10th hello (#0, #10, ...)
        # still goes out with CMD52, so the hello after it shows that slow
        # tick; the others show what the rest of the ticks cost.
        after_cmd52 = [vb for num, vb in numbered if num % 10 == 1]
        rest = sorted(vb for num, vb in numbered if num % 10 != 1)
        if rest:
            print(f"Longest tick apart from the CMD52 heartbeat hellos: vb={rest[-1]} (typical {rest[len(rest) // 2]}); "
                  f"with one: vb={max(after_cmd52) if after_cmd52 else '-'}")
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


WATCH_LINES = 40   # changes printed per read at most


def parse_values(text):
    """'0-3,0x40,0x80' -> {0, 1, 2, 3, 64, 128}."""
    values = set()
    for part in text.split(","):
        lo, _, hi = part.strip().partition("-")
        values.update(range(int(lo, 0), int(hi or lo, 0) + 1))
    return values


def watch(c, ranges, interval=0.2, width=1, settle=0.0, only=None, duration=None):
    """Reads `ranges` over and over and prints every value that changes, a
    `width`-byte little-endian value at a time, with the seconds since the
    start. Values that change during the first `settle` seconds are muted
    from then on (stand still meanwhile: what changes anyway is timers and
    animation). `only`: a set of values; a change is printed only when the
    old and the new value are both in it. Typing a note and Enter prints it
    as a marker; Ctrl+C (or `duration` seconds) stops and prints a summary."""
    fmt = {1: "<B", 2: "<H", 4: "<I"}[width]
    digits = 2 * width
    t0 = time.time()
    last, counts, values, muted = {}, {}, {}, set()
    lock = threading.Lock()

    def notes():
        for line in sys.stdin:
            with lock:
                print(f"[{time.time() - t0:7.2f}s] ---- {line.strip() or 'mark'} ----", flush=True)
    threading.Thread(target=notes, daemon=True).start()

    total = sum(n for _, n in ranges)
    print(f"Watching {total} bytes in {len(ranges)} range(s), {width} byte(s) at a time"
          + (f", only the values {sorted(only)[:12]}{'...' if len(only) > 12 else ''}" if only else "")
          + ". Type a note and Enter to mark the log, Ctrl+C to stop.")
    if settle > 0:
        print(f"Stand still for {settle:g} s: whatever changes meanwhile is muted.")
    settled, misses = settle <= 0, 0
    try:
        while duration is None or time.time() - t0 < duration:
            try:
                results = c.read_ranges(ranges)
            except (TimeoutError, RuntimeError) as e:
                misses += 1
                if misses in (1, 10) or misses % 50 == 0:
                    print(f"(no reply: {e}; {misses} so far)", flush=True)
                time.sleep(interval)
                continue
            now = time.time() - t0
            lines = []
            if not settled and now >= settle:
                settled = True
                lines.append(f"[{now:7.2f}s] settled: {len(muted)} value(s) changed while you stood still and "
                             f"are muted. Go!")
            for (a, _), data in zip(ranges, results):
                for off in range(0, len(data) - width + 1, width):
                    addr = a + off
                    v = struct.unpack_from(fmt, data, off)[0]
                    old = last.get(addr)
                    last[addr] = v
                    if old is None or old == v or addr in muted:
                        continue
                    if not settled:
                        muted.add(addr)
                        continue
                    if only is not None and (old not in only or v not in only):
                        continue
                    counts[addr] = counts.get(addr, 0) + 1
                    seen = values.setdefault(addr, [old])
                    if v not in seen and len(seen) < 8:
                        seen.append(v)
                    lines.append(f"[{now:7.2f}s] 0x{addr:08X}: {old:0{digits}X} -> {v:0{digits}X}   ({old} -> {v})")
            if lines:
                extra = len(lines) - WATCH_LINES
                with lock:
                    print("\n".join(lines[:WATCH_LINES]) + (f"\n  ... and {extra} more" if extra > 0 else ""),
                          flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    print(f"\n{len(counts)} value(s) changed" + (f" ({len(muted)} muted)" if muted else "")
          + (":" if counts else "."))
    for addr in sorted(counts)[:60]:
        seen = " ".join(f"{v:0{digits}X}" for v in values[addr])
        print(f"  0x{addr:08X}: {counts[addr]:4d} change(s), values {seen}")
    if len(counts) > 60:
        print(f"  ... and {len(counts) - 60} more")


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
    ap.add_argument("--interval", type=float, help="seconds between reads (default 1, or 0.2 with --watch)")
    ap.add_argument("--timeout", type=float, default=1.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--stats", type=float, metavar="SECONDS",
                    help="link check: send small reads for this long and report losses and delays")
    ap.add_argument("--watch", nargs="+", type=parse_range, metavar="ADDR:LEN",
                    help="read these ranges over and over and print every value that changes")
    ap.add_argument("--width", type=int, choices=(1, 2, 4), default=1,
                    help="--watch: compare and print 1, 2 or 4 bytes at a time (little endian)")
    ap.add_argument("--settle", type=float, default=0.0, metavar="SECONDS",
                    help="--watch: mute whatever changes in the first SECONDS (stand still meanwhile)")
    ap.add_argument("--only", type=parse_values, metavar="VALUES",
                    help="--watch: only print changes between these values, e.g. 0-3 or 0,0x40,0x80,0xC0")
    ap.add_argument("--duration", type=float, metavar="SECONDS", help="--watch: stop after this long")
    args = ap.parse_args()

    c = DSiClient(port=args.port, dsi_ip=args.dsi_ip, timeout=args.timeout, verbose=args.verbose)
    if not c.wait_for_dsi():
        print("No hello from the DSi within 15 s - is the game running after the handoff?")
        sys.exit(1)

    if args.stats:
        link_stats(c, args.stats)
        return
    if args.watch:
        watch(c, args.watch, args.interval or 0.2, args.width, args.settle, args.only, args.duration)
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
            time.sleep(args.interval or 1.0)

    print(f"\n{ok} ok, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
