"""
launcher_activity.py - what the launcher is doing with DSiRPC right now, for
the PC to show (the tray's tooltip and menu, Discord's second line while the
console is in the launcher, and app/activity_popup.py's little window).

The launcher talks to DSiRPC in short exchanges (core/console_sync.py): the
offline sync (its unlocks in, the achievement sets out, after DSiRPC checks
its games with RetroAchievements), the save sync (one connection a save,
core/save_session.py) and its update check (core/console_update.py). Each
one tells the tracker as it goes:

    activity = LauncherActivity()
    activity.start("saves", "Syncing saves", console="3DS", total=4)
    activity.progress(1, detail="Pokemon Platinum")
    activity.finish("2 uploaded, 2 downloaded")
    activity.current()    # the dict below, or None once it's over
    activity.line()       # "Syncing saves (1 of 4)", or None

Its view is a dict: kind ("achievements", "saves" or "update"), title,
detail ("" for none), done and total (total 0: no count, a spinner) and
unit ("bytes" when they count bytes, else ""),
console ("DSi" or "3DS"), started and changed (time.time()), and once it's
over finished (time.time(), else None), summary and ok. A finished one
stays for DONE_S, so the popup can say so; one the launcher stopped talking
in for IDLE_S (it went away, or someone is picking a save on the console)
is simply gone. Everything is thread-safe: the sync's thread writes, the
tray, the hub and the popup's feeder read.
"""

import threading
import time

IDLE_S = 30.0    # no word from the launcher this long: over (it went away mid-way, or waits for a key)
DONE_S = 4.0     # a finished one is still shown this long

KINDS = ("achievements", "saves", "update")


class LauncherActivity:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._lock = threading.Lock()
        self._view = None
        self.generation = 0      # one more for every start(), so a reader can tell a new one from the last

    def start(self, kind, title, console=None, detail="", total=0, unit=""):
        """A new exchange (the last one, finished or not, is replaced)."""
        now = self._clock()
        with self._lock:
            self.generation += 1
            self._view = {'kind': kind, 'title': title, 'detail': detail or "", 'done': 0,
                          'total': max(0, int(total or 0)), 'unit': unit or "", 'console': console or "DSi", 'started': now,
                          'changed': now, 'finished': None, 'summary': "", 'ok': True,
                          'generation': self.generation}

    def active(self, kind=None):
        """Whether an exchange (of this kind) is going on, not finished."""
        v = self.current()
        return v is not None and v['finished'] is None and (kind is None or v['kind'] == kind)

    def progress(self, done=None, total=None, detail=None, title=None, unit=None):
        """How far it got (done of total; done never goes past total, which
        grows instead), and what it's on. Nothing if nothing's going on."""
        with self._lock:
            v = self._view
            if v is None or v['finished'] is not None:
                return
            if total is not None:
                v['total'] = max(0, int(total))
            if done is not None:
                v['done'] = max(0, int(done))
                if v['total'] and v['done'] > v['total']:
                    v['total'] = v['done']
            if detail is not None:
                v['detail'] = detail
            if title is not None:
                v['title'] = title
            if unit is not None:
                v['unit'] = unit
            v['changed'] = self._clock()

    def finish(self, summary="", ok=True):
        """It's over: summary says how it went (shown for DONE_S)."""
        with self._lock:
            v = self._view
            if v is None or v['finished'] is not None:
                return
            now = self._clock()
            v['finished'] = v['changed'] = now
            v['summary'], v['ok'] = summary or "", bool(ok)
            if ok and v['total']:
                v['done'] = v['total']

    def clear(self):
        with self._lock:
            self._view = None

    def current(self):
        """A copy of what's going on (or just finished), or None."""
        with self._lock:
            v = self._view
            if v is None:
                return None
            now = self._clock()
            if v['finished'] is not None:
                if now - v['finished'] > DONE_S:
                    self._view = None
                    return None
            elif now - v['changed'] > IDLE_S:
                self._view = None
                return None
            return dict(v)

    def line(self):
        """One short line about it, for the tray and Discord, or None."""
        return describe(self.current())


def describe(view):
    """A view as one short line: "Syncing saves (3 of 12)", "Updating the
    console (40%)" (counting bytes), "Syncing saves: done", or None."""
    if not view:
        return None
    if view['finished'] is not None:
        return f"{view['title']}: {'done' if view['ok'] else 'failed'}"
    if view['total'] and view.get('unit') == "bytes":
        return f"{view['title']} ({int(fraction(view) * 100)}%)"
    if view['total']:
        return f"{view['title']} ({min(view['done'], view['total'])} of {view['total']})"
    return view['title']


def fraction(view):
    """How far along it is, 0 to 1, or None without a count (a spinner)."""
    if not view or not view['total']:
        return 1.0 if view and view['finished'] is not None and view['ok'] else None
    return max(0.0, min(1.0, view['done'] / view['total']))
