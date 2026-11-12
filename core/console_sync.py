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

activity, if given, is a core/launcher_activity.py LauncherActivity: the
offline sync and the update downloads tell it how far they got, for the PC
to show (the save sync tells it through the engine, from on_saves' events).
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
SEND_CHUNK = 16 * 1024     # the answer's sets go a piece at a time, so the activity can count them

# What the offline sync's "still working" frames say it's on (offline.PROGRESS_*)
PROGRESS_TEXT = {offline.PROGRESS_CHECKING: "Checking games with RetroAchievements",
                 offline.PROGRESS_SETS: "Getting the achievement sets ready"}


def _set_name(code, data):
    """A set for the log: its code and its frame lane's ring of samples."""
    try:
        return f"{code}: {offline.read_set(data)['ring']}-sample ring"
    except offline.FormatError:
        return code


class ConsoleSync:
    def __init__(self, sets_for, on_unlocks, on_console=None, port=offline.SYNC_PORT, host="", on_notes=None,
                 saves=None, on_saves=None, on_here=None, updates=None, stats=None, on_roms=None, activity=None):
        self.sets_for = sets_for
        # ([(code, md5, started, name)], hashed, ms, progress) -> {md5:
        # offline.RA_*}: the launcher's hashes (sync version 2), before the
        # sets are made. progress(done, of, what) keeps the launcher waiting.
        self.on_roms = on_roms
        self.on_unlocks = on_unlocks
        self.on_console = on_console
        self.on_notes = on_notes      # ([shadow note], {code: the console's set's stamp}): the console's shadow
                                      # check's, before the sets are made
        self.on_here = on_here
        self.saves = saves
        self.on_saves = on_saves
        self.updates = updates
        self.stats = stats
        self.activity = activity
        self._update_sent, self._update_files = None, []    # an update's files sent so far (_update_progress())
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
            asked = data[len(offline.DISCOVER)] if len(data) > len(offline.DISCOVER) else 1
            self.udp.sendto(offline.ANSWER + struct.pack("<BH", offline.sync_version(asked), self.port), addr)
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
            console_update.handle(magic, read, conn.sendall, files,
                                  progress=self._update_progress if self.activity else None)
            self._await_hangup(conn)
            return
        if magic == playtime.MAGIC:
            times, info = self.stats() if self.stats else (None, None)
            playtime.handle(magic, read, conn.sendall, times, info)
            self._await_hangup(conn)
            return
        try:
            header = magic + read(offline.REQUEST.size - 4)
            request = offline.parse_sync(header, read)
            game, stamps, unlock_bytes = request['game'], request['stamps'], request['unlocks']
            console = offline.request_console(header)
            unlocks = offline.read_unlocks(unlock_bytes)
            notes = offline.read_shadow_notes(unlock_bytes)
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
        act = self.activity
        if act:
            act.start("achievements", "Syncing achievements", console=console,
                      detail=f"{len(unlocks)} unlock{'s' if len(unlocks) != 1 else ''} from the console"
                      if unlocks else "")
        try:
            self._answer_sync(conn, addr, request, game, stamps, unlock_bytes, unlocks, notes)
        except Exception:
            if act:
                act.finish("Lost the console", ok=False)
            raise

    def _answer_sync(self, conn, addr, request, game, stamps, unlock_bytes, unlocks, notes):
        """The offline sync's answer (after _exchange() read the request)."""
        act = self.activity
        statuses, progress = {}, None
        if request['version'] >= 2:  # (before the sets: a game RetroAchievements has no set for gets none)
            def progress(done, total, what):
                conn.sendall(offline.build_progress(done, total, what))
                if act:
                    act.progress(done, total, detail=PROGRESS_TEXT.get(what, ""), unit="")
            statuses = {r[1]: offline.RA_UNKNOWN for r in request['roms']}
            if self.on_roms:
                try:
                    statuses.update(self.on_roms(request['roms'], request['hashed'], request['hash_ms'],
                                                 progress) or {})
                except Exception:
                    logging.exception("Offline sync: on_roms failed")
        if notes and self.on_notes:  # (before the sets: what it found decides their frame lanes)
            try:
                self.on_notes(notes, stamps)
            except Exception:
                logging.exception("Offline sync: on_notes failed")
        # The sets first (that may download the game's), so the unlocks are
        # logged with their names; the sets leave out what was just unlocked.
        try:
            sets = self.sets_for(game, stamps, unlocks, progress) if progress else self.sets_for(game, stamps, unlocks)
        except Exception:
            logging.exception("Offline sync: couldn't make the achievement sets")
            sets = []
        keep = bool(unlocks) and self.on_unlocks(unlocks) is False
        # "Taken" is every valid slot in the file (repeats included): the
        # launcher clears the file only when that matches its own count, so
        # 0 leaves them there.
        taken = 0 if keep else offline.count_slots(unlock_bytes)
        notes = taken - offline.count_unlocks(unlock_bytes) if taken else 0   # (the shadow check's)
        answer = offline.build_answer(0, taken, sets, request['version'], statuses)
        if act and sets:
            act.progress(0, len(answer), detail=f"Sending {len(sets)} achievement set{'s' if len(sets) != 1 else ''}",
                         unit="bytes")
        for i in range(0, len(answer), SEND_CHUNK):
            conn.sendall(answer[i:i + SEND_CHUNK])
            if act and sets:
                act.progress(min(i + SEND_CHUNK, len(answer)))
        if act:
            got = len(unlocks) if taken else 0
            parts = ([f"{got} unlock{'s' if got != 1 else ''} taken"] if got else []) + \
                    ([f"{len(sets)} set{'s' if len(sets) != 1 else ''} sent"] if sets else [])
            act.finish(", ".join(parts) or "Everything was up to date")
        self._await_hangup(conn)
        self.last = {'from': addr[0], 'game': game, 'unlocks': unlocks, 'taken': taken,
                     'sets': [code for code, _ in sets], 'version': request['version'], 'statuses': statuses}
        logging.info(f"Offline sync with the console at {addr[0]}"
                     + (f" (starting {game})" if game else "") + f": {taken - notes} unlock(s)"
                     + (f", {notes} shadow note(s)" if notes else "") + " taken, "
                     f"{len(sets)} set(s) sent" + (f" ({', '.join(_set_name(c, d) for c, d in sets)})" if sets else ""))

    def _update_progress(self, what, sent, total, console, update=0):
        """console_update.handle()'s, as it sends the console one of its
        files. update: the bytes of all the files the console takes (0 from
        a launcher that doesn't say): one bar across them, done once the
        last one has gone. Without it, each file is one of its own."""
        act = self.activity
        if not update:
            if sent == 0 or not act.active("update"):
                act.start("update", "Updating the console", console=console, detail=f"Sending {what}", total=total,
                          unit="bytes")
            act.progress(sent, total)
            if sent >= total:
                act.finish(f"Sent {what}")
            return
        v = act.current()
        if (not act.active("update") or v['total'] != update or v['console'] != console
                or self._update_sent is None):
            act.start("update", "Updating the console", console=console, total=update, unit="bytes")
            self._update_sent, self._update_files = 0, []     # (the files sent whole so far)
        if sent == 0:
            act.progress(detail=f"Sending {what}")
        act.progress(self._update_sent + sent)
        if sent >= total:
            self._update_sent += total
            self._update_files.append(what)
            if self._update_sent >= update:
                self._update_sent = None
                act.finish("Sent " + " and ".join(self._update_files))

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
