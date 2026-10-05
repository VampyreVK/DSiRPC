"""
startup.py - "Start with Windows": the tray icon starts when you sign in.

It's a value named DSiRPC under HKEY_CURRENT_USER's Run key (no admin rights
needed), which runs `pythonw dsirpc.py tray` from this folder. It shows up in
Task Manager's Startup apps like any other app, and turning it off here
removes the value again.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "DSiRPC"


def supported():
    return sys.platform == "win32"


def pythonw():
    """pythonw.exe next to the running Python (no console window)."""
    folder, exe = os.path.split(sys.executable)
    if exe.lower() in ("python.exe", "pythonw.exe"):
        candidate = os.path.join(folder, "pythonw.exe")
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def command():
    return f'"{pythonw()}" "{os.path.join(ROOT, "dsirpc.py")}" tray'


def current():
    """The command Windows runs at sign-in, or None."""
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
        raise OSError("Start with Windows only works on Windows")
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
