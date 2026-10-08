"""
console_sync.py - the launcher's side door into DSiRPC, for offline play
(core/offline.py has the formats). Whenever the launcher starts a game and
can find DSiRPC on the network, it hands over the achievements unlocked
while DSiRPC wasn't around and takes the achievement sets it doesn't have
yet, so they're on the SD card for the next time it plays without DSiRPC.

    sync = ConsoleSync(sets_for, on_unlocks)
    sync.start()           # UDP and TCP port 4245, on its own thread
    sync.stop()

sets_for(game, stamps, unlocks) -> [(code, .DRS bytes)] and
on_unlocks([unlock]) are the engine's (app/engine.py). Everything here runs
on this module's thread; the console waits while it works.
"""

import logging
import select
import socket
import struct
import threading
import time

from . import offline

ACCEPT_TIMEOUT = 15.0
HANGUP_TIMEOUT = 5.0


class ConsoleSync:
    def __init__(self, sets_for, on_unlocks, port=offline.SYNC_PORT, host=""):
        self.sets_for = sets_for
        self.on_unlocks = on_unlocks
        self.port = port
        self.host = host
        self.udp = None
        self.tcp = None
        self._stopping = threading.Event()
        self._thread = None
        self.last = None          # what the last exchange did, for the log and tests

    def start(self):
        """Opens the ports (OSError if one is taken) and starts listening."""
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            udp.bind((self.host, self.port))
            tcp.bind((self.host, udp.getsockname()[1]))  # the same number (port 0: tests)
            tcp.listen(2)
        except OSError:
            udp.close()
            tcp.close()
            raise
        self.udp, self.tcp = udp, tcp
        self.port = tcp.getsockname()[1]
        self._thread = threading.Thread(target=self._run, name="ConsoleSync", daemon=True)
        self._thread.start()
        logging.info(f"Waiting for the launcher's offline sync on port {self.port}")

    def stop(self):
        self._stopping.set()
        for s in (self.udp, self.tcp):
            try:
                if s:
                    s.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=3)

    # -- the thread ----------------------------------------------------------

    def _run(self):
        while not self._stopping.is_set():
            try:
                ready, _, _ = select.select([self.udp, self.tcp], [], [], 0.5)
            except (OSError, ValueError):
                return  # closed
            for s in ready:
                try:
                    if s is self.udp:
                        self._discover()
                    else:
                        conn, addr = self.tcp.accept()
                        with conn:
                            self._exchange(conn, addr)
                except OSError as e:
                    if self._stopping.is_set():
                        return
                    logging.info(f"Offline sync: {e}")
                except Exception:
                    logging.exception("Offline sync: unexpected error")

    def _discover(self):
        data, addr = self.udp.recvfrom(64)
        if data.startswith(offline.DISCOVER):
            self.udp.sendto(offline.ANSWER + struct.pack("<BH", offline.VERSION, self.port), addr)

    def _exchange(self, conn, addr):
        conn.settimeout(ACCEPT_TIMEOUT)

        def read(n):
            buf = bytearray()
            while len(buf) < n:
                chunk = conn.recv(min(65536, n - len(buf)))
                if not chunk:
                    raise ConnectionError("the console hung up")
                buf += chunk
            return bytes(buf)

        try:
            game, stamps, unlock_bytes = offline.parse_request(read(offline.REQUEST.size), read)
            unlocks = offline.read_unlocks(unlock_bytes)
        except offline.FormatError as e:
            logging.warning(f"Offline sync from {addr[0]}: {e}")
            conn.sendall(offline.build_answer(1, 0, []))
            self._await_hangup(conn)
            return
        # The sets first (that may download the game's), so the unlocks are
        # logged with their names; the sets leave out what was just unlocked.
        try:
            sets = self.sets_for(game, stamps, unlocks)
        except Exception:
            logging.exception("Offline sync: couldn't make the achievement sets")
            sets = []
        if unlocks:
            self.on_unlocks(unlocks)
        # "Taken" is every valid slot in the file (repeats included): the
        # launcher clears the file only when that matches its own count.
        taken = offline.count_unlocks(unlock_bytes)
        conn.sendall(offline.build_answer(0, taken, sets))
        self._await_hangup(conn)
        self.last = {'from': addr[0], 'game': game, 'unlocks': unlocks, 'taken': taken,
                     'sets': [code for code, _ in sets]}
        logging.info(f"Offline sync with the console at {addr[0]}"
                     + (f" (starting {game})" if game else "") + f": {taken} unlock(s) taken, "
                     f"{len(sets)} set(s) sent" + (f" ({', '.join(c for c, _ in sets)})" if sets else ""))

    @staticmethod
    def _await_hangup(conn):
        """The console hangs up once it has the answer. Closing after it does
        leaves the TIME_WAIT on its side instead of on this port, which could
        otherwise keep DSiRPC from opening the port again for a while."""
        deadline = time.monotonic() + HANGUP_TIMEOUT
        try:
            while time.monotonic() < deadline:
                conn.settimeout(max(0.1, deadline - time.monotonic()))
                if not conn.recv(4096):
                    return
        except OSError:
            pass
