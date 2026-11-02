"""
console_sync.py - the launcher's side door into DSiRPC, for offline play
(core/offline.py has the formats). Whenever the launcher starts a game and
can find DSiRPC on the network, it hands over the achievements unlocked
while DSiRPC wasn't around and takes the achievement sets it doesn't have
yet, so they're on the SD card for the next time it plays without DSiRPC.

    sync = ConsoleSync(sets_for, on_unlocks, on_console)
    sync.start()           # UDP and TCP port 4245, on its own thread
    sync.stop()

sets_for(game, stamps, unlocks) -> [(code, .DRS bytes)] and
on_unlocks([unlock]) are the engine's (app/engine.py). on_unlocks returns
False to leave the unlocks on the console (a dry run), anything else lets the
launcher clear them. on_console(ip, game, console), if given, hears about each sync as
it starts: the launcher syncs once it's connected (game None) and again as it
starts a game (its code), so DSiRPC knows the DSi is there before the game
says hello. on_here(ip, here, console), if given, hears the launcher's
"still here" (here True, every 5 s while it waits for a key) and its "bye"
(False, as it exits). Everything here runs on this module's thread; the
console waits while it works.

The launcher's save sync uses the same port: a connection that starts with
"DRSV" instead of "DRSQ" goes to core/save_session.py, with the SaveStore
saves() returns (None: save backups are off) and on_saves(event). So does
its update check: "DRUP" goes to core/console_update.py, with the
ConsoleFiles updates() returns (None: console updates are off). And its
playtimes: "DRGS" goes to core/playtime.py, with the (Playtime, info) that
stats() returns.
"""

import logging
import select
import socket
import struct
import threading
import time

from . import console_update, offline, playtime, save_session

ACCEPT_TIMEOUT = 15.0
HANGUP_TIMEOUT = 5.0


class ConsoleSync:
    def __init__(self, sets_for, on_unlocks, on_console=None, port=offline.SYNC_PORT, host="",
                 saves=None, on_saves=None, on_here=None, updates=None, stats=None):
        self.sets_for = sets_for
        self.on_unlocks = on_unlocks
        self.on_console = on_console
        self.on_here = on_here
        self.saves = saves
        self.on_saves = on_saves
        self.updates = updates
        self.stats = stats
        self.port = port
        self.host = host
        self.udp = None
        self.tcp = None
        self._stopping = threading.Event()
        self._thread = None
        self.last = None          # what the last exchange did, for the log and tests

    def start(self):
        """Opens the ports (OSError if one is taken) and starts listening.
        Port 0 (the tests) takes any number free for both: the one the
        system picks for UDP can be taken for TCP (by a connection that just
        closed, say), so then it tries another."""
        tries = 20 if self.port == 0 else 1
        for left in reversed(range(tries)):
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                udp.bind((self.host, self.port))
                tcp.bind((self.host, udp.getsockname()[1]))  # the same number
                tcp.listen(2)
                break
            except OSError:
                udp.close()
                tcp.close()
                if not left:
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
        elif self.on_here and (data.startswith(offline.HERE) or data.startswith(offline.BYE)):
            here = data.startswith(offline.HERE)
            model = data[len(offline.HERE)] if here and len(data) > len(offline.HERE) else 0
            try:
                self.on_here(addr[0], here, offline.console_name(model))
            except Exception:
                logging.exception("Offline sync: on_here failed")

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

        magic = read(4)
        if magic == save_session.MAGIC:
            store = self.saves() if self.saves else None
            save_session.handle(magic, read, conn.sendall, store, self.on_saves)
            self._await_hangup(conn)
            return
        if magic == console_update.MAGIC:
            files = self.updates() if self.updates else None
            console_update.handle(magic, read, conn.sendall, files)
            self._await_hangup(conn)
            return
        if magic == playtime.MAGIC:
            times, info = self.stats() if self.stats else (None, None)
            playtime.handle(magic, read, conn.sendall, times, info)
            self._await_hangup(conn)
            return
        try:
            header = magic + read(offline.REQUEST.size - 4)
            game, stamps, unlock_bytes = offline.parse_request(header, read)
            console = offline.request_console(header)
            unlocks = offline.read_unlocks(unlock_bytes)
        except offline.FormatError as e:
            logging.warning(f"Offline sync from {addr[0]}: {e}")
            conn.sendall(offline.build_answer(1, 0, []))
            self._await_hangup(conn)
            return
        if self.on_console:
            try:
                self.on_console(addr[0], game, console)
            except Exception:
                logging.exception("Offline sync: on_console failed")
        # The sets first (that may download the game's), so the unlocks are
        # logged with their names; the sets leave out what was just unlocked.
        try:
            sets = self.sets_for(game, stamps, unlocks)
        except Exception:
            logging.exception("Offline sync: couldn't make the achievement sets")
            sets = []
        keep = bool(unlocks) and self.on_unlocks(unlocks) is False
        # "Taken" is every valid slot in the file (repeats included): the
        # launcher clears the file only when that matches its own count, so
        # 0 leaves them there.
        taken = 0 if keep else offline.count_unlocks(unlock_bytes)
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
