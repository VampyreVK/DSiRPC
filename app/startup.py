"""
startup.py - "Start with Windows" ("Open at Login" on a Mac): the tray icon
starts when you sign in.

On Windows it's a value named DSiRPC under HKEY_CURRENT_USER's Run key (no
admin rights needed), which runs `pythonw dsirpc.py tray` from this folder.
It shows up in Task Manager's Startup apps like any other app, and turning it
off here removes the value again.

On a Mac it's a launch agent, ~/Library/LaunchAgents/<LABEL>.plist, that
opens the app at login (or runs `dsirpc.py tray` from a checkout); System
Settings lists it in Login Items, and turning it off here deletes the file.
"""

import os
import plistlib
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "DSiRPC"
LABEL = "io.github.vampyrevk.dsirpc"   # the macOS app's bundle identifier too


def supported():
    return sys.platform in ("win32", "darwin")


def label():
    """The menu item's name."""
    return "Open at Login" if sys.platform == "darwin" else "Start with Windows"


def pythonw():
    """pythonw.exe next to the running Python (no console window)."""
    folder, exe = os.path.split(sys.executable)
    if exe.lower() in ("python.exe", "pythonw.exe"):
        candidate = os.path.join(folder, "pythonw.exe")
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def _agent_path():
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", f"{LABEL}.plist")


def command():
    """What runs at sign-in: a command line on Windows, the launch agent's
    program and arguments on a Mac."""
    if sys.platform == "darwin":
        if getattr(sys, "frozen", False):
            # .../DSiRPC.app/Contents/MacOS/DSiRPC -> .../DSiRPC.app
            app = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))
            return ["/usr/bin/open", "-a", app]
        return [sys.executable, os.path.join(ROOT, "dsirpc.py"), "tray"]
    return f'"{pythonw()}" "{os.path.join(ROOT, "dsirpc.py")}" tray'


def current():
    """What runs at sign-in now (as command() puts it), or None."""
    if sys.platform == "darwin":
        try:
            with open(_agent_path(), "rb") as f:
                return plistlib.load(f).get("ProgramArguments")
        except (OSError, plistlib.InvalidFileException, ValueError):
            return None
    if not supported():
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, NAME)
            return value
    except OSError:
        return None


def is_enabled():
    return current() is not None


def set_enabled(on):
    if not supported():
        raise OSError("Starting at sign-in only works on Windows and macOS")
    if sys.platform == "darwin":
        path = _agent_path()
        if on:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                plistlib.dump({"Label": LABEL, "ProgramArguments": command(), "RunAtLoad": True}, f)
        elif os.path.exists(path):
            os.remove(path)
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
