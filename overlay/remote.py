"""
remote.py - the overlay window in a process of its own, for macOS. There the
menu bar icon (app/tray.py) needs the app's main thread, and so does any
window, so the overlay can't be a thread of the tray like on Windows.

RemoteOverlay stands in for OverlayWindow in the tray's process (same run()
and stop()): it starts the window's process and sends it the hub's snapshot
and events through a pipe each time they change. The window's process draws
them with the usual OverlayWindow, from _PipeHub, which gives it what it
needs of a StateHub. The window sends back its new size (the 1-6 keys) and
whether it was closed.
"""

import logging
import multiprocessing
import threading


class _PipeHub:
    """What OverlayWindow uses of a StateHub, fed from the pipe."""

    source = None   # no demo scenes to skip (the N key)

    def __init__(self, conn):
        from core.hub import Snapshot
        self.conn = conn
        self.window = None
        # Like a StateHub's, a snapshot from the start: the window can draw
        # its first frame before the tray's first one comes through
        self._snap = Snapshot()
        self._listeners = []
        self._lock = threading.Lock()

    def snapshot(self):
        return self._snap

    def add_listener(self, fn):
        with self._lock:
            self._listeners.append(fn)

    def remove_listener(self, fn):
        with self._lock:
            if fn in self._listeners:
                self._listeners.remove(fn)

    def pump(self):
        """Takes in what the tray sends until it says stop or goes away."""
        while True:
            try:
                msg = self.conn.recv()
            except (EOFError, OSError):
                break
            if msg[0] == 'snap':
                _, self._snap, events = msg
                with self._lock:
                    listeners = list(self._listeners)
                for fn in listeners:
                    fn(self._snap, events)
            elif msg[0] == 'stop':
                break
        if self.window:
            self.window.stop()


def _window_process(conn, scale, chroma, log_file):
    """The window's process: draws until the window is closed or the tray
    says stop."""
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format="%(asctime)s %(levelname)s overlay: %(message)s")
    from .app import OverlayWindow
    hub = _PipeHub(conn)

    def on_scale(n):
        try:
            conn.send(('scale', n))
        except (OSError, ValueError):
            pass
    try:
        window = OverlayWindow(hub, scale=scale, chroma=chroma, on_scale=on_scale)
    except ValueError as e:
        logging.warning(f"chroma: {e}; ignoring it")
        window = OverlayWindow(hub, scale=scale, on_scale=on_scale)
    hub.window = window
    threading.Thread(target=hub.pump, name="Pipe", daemon=True).start()
    closed = window.run()
    try:
        conn.send(('closed', closed))
    except (OSError, ValueError):
        pass


class RemoteOverlay:
    """OverlayWindow's run() and stop(), with the window in its own process."""

    def __init__(self, hub, scale=3, chroma=None, on_scale=None, log_file=None):
        self.hub = hub
        self.scale = scale
        self.chroma = chroma
        self.on_scale = on_scale
        self.log_file = log_file
        self._stop = threading.Event()
        self._send_lock = threading.Lock()
        self._conn = None
        self._unsent = False

    def _send(self, msg):
        with self._send_lock:
            if self._conn is None:
                return
            try:
                self._conn.send(msg)
            except (OSError, ValueError, EOFError):   # the window's process is gone
                self._conn = None
            except Exception as e:   # something in it that can't go through the pipe: skip it
                if not self._unsent:
                    logging.warning(f"Overlay window: couldn't send it the state ({e!r})")
                    self._unsent = True

    def _forward(self, snap, events):
        self._send(('snap', snap, events))

    def stop(self):
        """Closes the window from another thread (run() returns soon after)."""
        self._stop.set()

    def run(self):
        """Starts the window's process and feeds it until the window closes
        (or stop() is called). Returns True if the user closed it."""
        ctx = multiprocessing.get_context('spawn')
        here, there = ctx.Pipe()
        proc = ctx.Process(target=_window_process, name="DSiRPC overlay",
                           args=(there, self.scale, self.chroma, self.log_file), daemon=True)
        proc.start()
        there.close()
        self._conn = here
        self.hub.add_listener(self._forward)
        self._send(('snap', self.hub.snapshot(), []))
        closed = False
        try:
            while proc.is_alive():
                if self._stop.is_set():
                    self._send(('stop',))
                    proc.join(timeout=5)
                    break
                try:
                    if not here.poll(0.2):
                        continue
                    msg = here.recv()
                except (EOFError, OSError):
                    break
                if msg[0] == 'scale' and self.on_scale:
                    self.on_scale(msg[1])
                elif msg[0] == 'closed':
                    closed = msg[1]
            proc.join(timeout=5)
            if not closed and not self._stop.is_set():
                logging.warning(f"The overlay window's process ended by itself (exit code {proc.exitcode}); "
                                f"its log: {self.log_file}")
        finally:
            self.hub.remove_listener(self._forward)
            with self._send_lock:
                self._conn = None
            here.close()
            if proc.is_alive():
                proc.terminate()
        return closed
