"""
activity_popup.py - a little window in the corner of the screen while the
launcher does something with DSiRPC that takes a while: syncing saves,
checking its games with RetroAchievements, getting the achievement sets
ready and sending them, or sending the console an update
(core/launcher_activity.py says what's going on).

    +----------------------------------------------+
    | [DSi]  Syncing saves                 2 of 5  |
    |        Uploaded Pokemon Platinum             |
    |        [##########..............]            |
    +----------------------------------------------+

It's drawn the overlay's way (overlay/font.py's pixel font and overlay/ui.py's
DSi, on a small canvas scaled up with nearest-neighbour), stays on top
without taking the focus or a place on the taskbar, and:

  - only shows once something has gone on for SHOW_AFTER seconds, so the
    quick syncs at every game start don't flash it
  - says how it went for a few seconds once it's over (core/
    launcher_activity.py's DONE_S), then goes; a sync it never showed
    isn't shown just to say it's done
  - goes at a click, until the next one

ActivityPopup lives in the tray's process (app/tray.py) and watches the
activity on a thread of its own; the window is in a process of its own
(started the first time it's needed), like the overlay window on a Mac
(overlay/remote.py): pygame has one display a process, which on Windows is
the overlay's.
"""

import logging
import multiprocessing
import os
import sys
import threading
import time

from core.launcher_activity import describe, fraction

SHOW_AFTER = 1.0     # seconds something goes on before the popup shows
POLL_S = 0.1         # how often the tray's side looks at the activity
W, H = 250, 46       # the canvas, in the overlay's pixels
SCALE = 2
MARGIN = 16          # from the screen's edge, in screen pixels
TASKBAR = 56         # Windows: room for the taskbar under it
MENU_BAR = 32        # macOS: room for the menu bar above it


def should_show(view, now, shown, dismissed):
    """Whether the popup shows this view (core/launcher_activity.py's
    current()): `shown` is the generation it last showed, `dismissed` the
    one clicked away."""
    if not view or view['generation'] == dismissed:
        return False
    if view['finished'] is not None:
        return view['generation'] == shown      # (only to say how one it showed went)
    return view['generation'] == shown or now - view['started'] >= SHOW_AFTER


def count_text(view):
    """The count at the title's right: "2 of 5", "40%" (bytes), "" without one."""
    if not view or not view['total'] or view['finished'] is not None:
        return ""
    if view.get('unit') == "bytes":
        return f"{int(fraction(view) * 100)}%"
    return f"{min(view['done'], view['total'])} of {view['total']}"


# -- drawing (in the window's process; the tests draw it too) ---------------------

class Painter:
    def __init__(self):
        from overlay.font import PixelFont
        self.font = PixelFont()

    def draw(self, canvas, view, t_ms):
        """The popup for `view` on a W x H canvas."""
        import pygame
        from overlay import ui
        t = ui.THEME
        done = view['finished'] is not None
        failed = done and not view['ok']
        accent = t['hp_red'] if failed else t['hp_green']
        canvas.fill((0, 0, 0))
        ui.panel(canvas, (0, 0, W, H), fill=t['bar'], border=t['bar_lo'], hi=t['bar_hi'], lo=t['bar_lo'], radius=3)

        # The DSi, its Wi-Fi sign lighting up arc by arc while it works,
        # green once done (red if it failed)
        ix, iy = 4, (H - ui.DSI_H) // 2
        ui.dsi(canvas, ix, iy)
        if done:
            ui.dsi_wifi(canvas, ix, iy, on=accent)
        else:
            ui.dsi_wifi(canvas, ix, iy, lit=1 + (t_ms // 300) % 4, off=(46, 56, 70))

        tx = ix + ui.DSI_W + 4
        right = W - 6
        count = count_text(view)
        cw = self.font.width(count) + 6 if count else 0
        title = view['title'] if not done else f"{view['title']}: {'failed' if failed else 'done'}"
        self.font.draw(canvas, self.font.fit(title, right - tx - cw), (tx, 5), t['text_light'],
                       t['text_light_shadow'])
        if count:
            self.font.draw(canvas, count, (right, 5), t['hp_label'], t['text_light_shadow'], align='right')
        detail = view['summary'] if done else view['detail']
        if not detail:
            detail = f"On the {view['console']}"
        self.font.draw(canvas, self.font.fit(detail, right - tx), (tx, 17), (186, 204, 208), t['text_light_shadow'])

        # The bar: how far it is, or a block going back and forth without a count
        bx, by, bw, bh = tx, 32, right - tx, 7
        pygame.draw.rect(canvas, t['hp_frame'], (bx, by, bw, bh))
        pygame.draw.rect(canvas, t['hp_empty'], (bx + 1, by + 1, bw - 2, bh - 2))
        frac = fraction(view)
        inner = bw - 2
        if frac is None:
            seg = max(8, inner // 4)
            span = inner - seg
            pos = (t_ms // 16) % (2 * span) if span > 0 else 0
            x = pos if pos <= span else 2 * span - pos
            lo, hi = t['hp_yellow'], t['hp_yellow_hi']
            pygame.draw.rect(canvas, lo, (bx + 1 + x, by + 1, seg, bh - 2))
            pygame.draw.line(canvas, hi, (bx + 1 + x, by + 1), (bx + x + seg, by + 1))
        elif frac > 0 or done:
            fw = max(1, int(inner * (1.0 if done else frac)))
            lo = accent
            hi = t['hp_red_hi'] if failed else t['hp_green_hi']
            pygame.draw.rect(canvas, lo, (bx + 1, by + 1, fw, bh - 2))
            pygame.draw.line(canvas, hi, (bx + 1, by + 1), (bx + fw, by + 1))


# -- the window's process -------------------------------------------------------

def _place(size):
    """Where the window goes: the bottom right corner on Windows (above the
    taskbar, by the notifications), the top right on a Mac (under the menu
    bar, where its notifications are)."""
    import pygame
    try:
        sw, sh = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError):
        return (MARGIN, MARGIN)
    w, h = size
    if sys.platform == "darwin":
        return (sw - w - MARGIN, MENU_BAR + MARGIN)
    return (sw - w - MARGIN, sh - h - TASKBAR - MARGIN)


def _popup_process(conn, log_file=None):
    """The window: shows the views the tray sends (None hides it), and
    sends back ('dismissed', generation) when it's clicked."""
    if log_file:
        logging.basicConfig(filename=log_file, level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    # Shown without taking the focus from whatever you're doing
    os.environ.setdefault("SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN", "1")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    try:
        pygame.display.init()
        size = (W * SCALE, H * SCALE)
        window = pygame.Window("DSiRPC", size, _place(size), hidden=True, borderless=True,
                               always_on_top=True, utility=True)
    except Exception:
        logging.exception("Activity popup: no window")
        return
    painter = Painter()
    canvas = pygame.Surface((W, H))
    view, visible = None, False
    clock = pygame.time.Clock()
    try:
        while True:
            try:
                while conn.poll(0):
                    msg = conn.recv()
                    if msg[0] == 'stop':
                        return
                    if msg[0] == 'view':
                        view = msg[1]
            except (EOFError, OSError):
                return
            for e in pygame.event.get():
                if e.type == pygame.MOUSEBUTTONDOWN and view:
                    try:
                        conn.send(('dismissed', view['generation']))
                    except (EOFError, OSError):
                        return
                    view = None
            if view is None:
                if visible:
                    window.hide()
                    visible = False
                clock.tick(10)
                continue
            painter.draw(canvas, view, pygame.time.get_ticks())
            surf = window.get_surface()
            pygame.transform.scale(canvas, surf.get_size(), surf)
            window.flip()
            if not visible:
                window.position = _place(window.size)
                window.show()
                visible = True
            clock.tick(30)
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        pygame.quit()


# -- the tray's side ---------------------------------------------------------------

class ActivityPopup:
    """Watches the activity and shows the popup when should_show() says so.
    enabled() (the tray menu's "Activity popup") is asked each time;
    on_line(line), if given, hears describe()'s line each time it changes
    (None once it's over), for the tray's tooltip and menu."""

    def __init__(self, activity, enabled=lambda: True, on_line=None, log_file=None):
        self.activity = activity
        self.enabled = enabled
        self.on_line = on_line
        self.log_file = log_file
        self._stop = threading.Event()
        self._thread = None
        self._proc = None
        self._conn = None
        self.shown = 0          # the generation last shown
        self.dismissed = 0      # the generation clicked away
        self._sent = None
        self._line = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name="ActivityPopup", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._close()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logging.exception("Activity popup failed")
            self._stop.wait(POLL_S)

    def tick(self, now=None):
        """One look at the activity: what the window should show, sent if
        that changed, and the tray told about a new line."""
        view = self.activity.current()
        now = time.time() if now is None else now
        line = describe(view)
        if line != self._line:
            self._line = line
            if self.on_line:
                try:
                    self.on_line(line)
                except Exception:
                    logging.exception("Activity popup: on_line failed")
        self._read_back()
        want = view if self.enabled() and should_show(view, now, self.shown, self.dismissed) else None
        if want is not None:
            self.shown = want['generation']
        # (the window animates by itself: only what it says is sent)
        key = None if want is None else (want['generation'], want['title'], want['detail'], count_text(want),
                                         round(fraction(want) or 0, 3), want['finished'] is not None)
        if key != self._sent:
            self._sent = key
            self._send(('view', want))

    def _read_back(self):
        conn = self._conn
        try:
            while conn is not None and conn.poll(0):
                msg = conn.recv()
                if msg[0] == 'dismissed':
                    self.dismissed = msg[1]
        except (EOFError, OSError):
            self._close()

    def _send(self, msg):
        if msg[1] is None and self._proc is None:
            return          # nothing to hide
        if self._proc is None or not self._proc.is_alive():
            self._open()
        try:
            self._conn.send(msg)
        except (EOFError, OSError, AttributeError):
            self._close()

    def _open(self):
        self._close()
        ctx = multiprocessing.get_context('spawn')
        here, there = ctx.Pipe()
        self._proc = ctx.Process(target=_popup_process, name="DSiRPC activity", args=(there, self.log_file),
                                 daemon=True)
        self._proc.start()
        there.close()
        self._conn = here

    def _close(self):
        conn, proc = self._conn, self._proc
        self._conn = self._proc = None
        if conn is not None:
            try:
                conn.send(('stop',))
            except (EOFError, OSError):
                pass
            conn.close()
        if proc is not None:
            proc.join(timeout=2)
            if proc.is_alive():
                proc.terminate()
