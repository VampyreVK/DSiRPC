"""
rcheevos.py - RetroAchievements' own rule engine (the rcheevos library) from
Python, through ctypes.

rcheevos is what emulators use to run a game's RetroAchievements set: it
parses the rich presence script and the achievement definitions and checks
them against the game's memory. DSiRPC uses it the same way, with the memory
coming from the DSi. Nothing here talks to RetroAchievements' servers.

The library is prebuilt in third_party/rcheevos/ (rcheevos.dll for Windows,
librcheevos.so for Linux; see third_party/rcheevos/README.md for the version
and how it was built).

    rt = Runtime()
    rt.set_rich_presence(script)           # raises RcheevosError if it doesn't parse
    rt.frame(peek)                         # once per poll: updates every value it watches
    text = rt.rich_presence(peek)          # the display string for the current state

`peek(address, num_bytes)` returns the little-endian value at a RetroAchievements
address (for the DS, 0x000000-0x3FFFFF is main RAM 0x02000000-0x023FFFFF).
An exception raised inside peek is re-raised once the rcheevos call returns.
"""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(os.path.dirname(HERE), "third_party", "rcheevos")

_PEEK = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)


class _Event(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("value", ctypes.c_int32), ("type", ctypes.c_uint8)]


_EVENT_HANDLER = ctypes.CFUNCTYPE(None, ctypes.POINTER(_Event))

# rc_runtime.h: RC_RUNTIME_EVENT_*
EVENT_NAMES = [
    "achievement_activated", "achievement_paused", "achievement_reset", "achievement_triggered",
    "achievement_primed", "lboard_started", "lboard_canceled", "lboard_updated", "lboard_triggered",
    "achievement_disabled", "lboard_disabled", "achievement_unprimed", "achievement_progress_updated",
]


class RcheevosError(Exception):
    pass


class RcheevosMissing(RcheevosError):
    pass


_lib = None


def library():
    """Loads the rcheevos library once. Raises RcheevosMissing if it isn't there."""
    global _lib
    if _lib is not None:
        return _lib
    if sys.platform == "win32":
        name = "rcheevos.dll"
    elif sys.platform == "darwin":
        name = "librcheevos.dylib"
    else:
        name = "librcheevos.so"
    path = os.path.join(LIB_DIR, name)
    if not os.path.exists(path):
        raise RcheevosMissing(f"rcheevos library not found: {path} (see third_party/rcheevos/README.md)")
    try:
        lib = ctypes.CDLL(path)
    except OSError as e:
        raise RcheevosMissing(f"couldn't load {path}: {e}")

    lib.rc_runtime_alloc.restype = ctypes.c_void_p
    lib.rc_runtime_alloc.argtypes = []
    lib.rc_runtime_destroy.restype = None
    lib.rc_runtime_destroy.argtypes = [ctypes.c_void_p]
    lib.rc_runtime_reset.restype = None
    lib.rc_runtime_reset.argtypes = [ctypes.c_void_p]
    lib.rc_runtime_activate_richpresence.restype = ctypes.c_int
    lib.rc_runtime_activate_richpresence.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int]
    lib.rc_runtime_get_richpresence.restype = ctypes.c_int
    lib.rc_runtime_get_richpresence.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                                                _PEEK, ctypes.c_void_p, ctypes.c_void_p]
    lib.rc_runtime_activate_achievement.restype = ctypes.c_int
    lib.rc_runtime_activate_achievement.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p,
                                                    ctypes.c_void_p, ctypes.c_int]
    lib.rc_runtime_deactivate_achievement.restype = None
    lib.rc_runtime_deactivate_achievement.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.rc_runtime_do_frame.restype = None
    lib.rc_runtime_do_frame.argtypes = [ctypes.c_void_p, _EVENT_HANDLER, _PEEK, ctypes.c_void_p, ctypes.c_void_p]
    lib.rc_error_str.restype = ctypes.c_char_p
    lib.rc_error_str.argtypes = [ctypes.c_int]
    _lib = lib
    return lib


def error_text(code):
    return library().rc_error_str(code).decode("utf-8", "replace")


class Runtime:
    """One rcheevos runtime: a rich presence script and (later) achievements,
    with the memory values they watch."""

    def __init__(self):
        self._lib = library()
        self._rt = self._lib.rc_runtime_alloc()
        if not self._rt:
            raise RcheevosError("rc_runtime_alloc failed")
        self._error = None
        self._events = []
        self.has_rich_presence = False

    def close(self):
        if self._rt:
            self._lib.rc_runtime_destroy(self._rt)
            self._rt = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _wrap_peek(self, peek):
        def cb(address, num_bytes, ud):
            if self._error is not None:
                return 0
            try:
                return int(peek(address, num_bytes)) & 0xFFFFFFFF
            except BaseException as e:  # re-raised after the C call
                self._error = e
                return 0
        return _PEEK(cb)

    def _raise_peek_error(self):
        e, self._error = self._error, None
        if e is not None:
            raise e

    def set_rich_presence(self, script):
        """Parses a rich presence script. Raises RcheevosError if it doesn't."""
        code = self._lib.rc_runtime_activate_richpresence(self._rt, script.encode("utf-8"), None, 0)
        if code != 0:
            self.has_rich_presence = False
            raise RcheevosError(f"rich presence script: {error_text(code)} ({code})")
        self.has_rich_presence = True

    def activate_achievement(self, achievement_id, memaddr):
        code = self._lib.rc_runtime_activate_achievement(self._rt, achievement_id, memaddr.encode("utf-8"), None, 0)
        if code != 0:
            raise RcheevosError(f"achievement {achievement_id}: {error_text(code)} ({code})")

    def deactivate_achievement(self, achievement_id):
        self._lib.rc_runtime_deactivate_achievement(self._rt, achievement_id)

    def reset(self):
        """Forgets hit counts and previous values (e.g. after the game was reset)."""
        self._lib.rc_runtime_reset(self._rt)

    def frame(self, peek):
        """Processes one frame: reads every value the runtime watches through
        peek and updates the rich presence and achievements. Returns the
        events, as [(event name, id, value)]."""
        self._events = []

        def on_event(ev):
            e = ev.contents
            name = EVENT_NAMES[e.type] if e.type < len(EVENT_NAMES) else str(e.type)
            self._events.append((name, e.id, e.value))

        handler = _EVENT_HANDLER(on_event)
        cpeek = self._wrap_peek(peek)
        self._lib.rc_runtime_do_frame(self._rt, handler, cpeek, None, None)
        self._raise_peek_error()
        return self._events

    def rich_presence(self, peek, size=512):
        """The rich presence display string for the values from the last frame()."""
        if not self.has_rich_presence:
            return ""
        buf = ctypes.create_string_buffer(size)
        cpeek = self._wrap_peek(peek)
        n = self._lib.rc_runtime_get_richpresence(self._rt, buf, size, cpeek, None, None)
        self._raise_peek_error()
        if n < 0:
            raise RcheevosError(f"rich presence: {error_text(n)} ({n})")
        return buf.value.decode("utf-8", "replace")
