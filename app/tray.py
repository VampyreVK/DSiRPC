"""
tray.py - DSiRPC as a tray icon (DSiRPC.bat, or 'dsirpc.py tray'), or a menu
bar icon in the macOS app (packaging/macos/).

Right-click the icon for the menu:

    Playing Mario Kart DS              what's running (or what it waits for)
    Discord: showing Mario Kart DS     what Discord shows
    RetroAchievements: 12 of 132 ...   achievements (signed in, or not)
    ---
    Discord presence                   on/off
    Console icon  >                    the small picture for games without their own presence
    Overlay window                     on/off (a left click on the icon does this too)
    Start with Windows                 on/off ("Open at Login" on a Mac)
    ---
    Setup...                           'dsirpc.py setup' in a console window (Terminal on a Mac)
    Open log / Open DSiRPC folder      (on a Mac, the folder with your settings)
    ---
    Quit

The dot on the icon is green while the game answers, amber while DSiRPC
waits for the DSi, and red when Discord can't be reached or has no
application ID. The on/off choices are saved in dsirpc.cfg.

Only one DSiRPC can run at a time (it needs the DSi's UDP port, 4244); a
second one says so and exits.

On a Mac the icon is in the menu bar and a click opens the menu (there's no
left-click action). The menu bar owns the main thread, so changes to the
icon and the menu are handed to it (on_main), and the overlay window runs in
a process of its own (overlay/remote.py). Setup runs in Terminal, and opens
by itself the first time, when there's no dsirpc.cfg yet.
"""

import logging
import os
import subprocess
import sys
import threading

from core.paths import DATA
from . import startup
from .engine import Engine, PortInUse, LOG_FILE, ROOT

MAC = sys.platform == "darwin"

COLORS = {
    'playing': (88, 208, 128),
    'waiting': (240, 192, 48),
    'problem': (232, 72, 56),
}


def _applescript_text(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def message_box(text, title="DSiRPC"):
    """A Windows message box, a dialog on a Mac (or a printed line elsewhere)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
    elif MAC:
        subprocess.run(["osascript", "-e", f"display dialog {_applescript_text(text)} with title "
                        f"{_applescript_text(title)} buttons {{\"OK\"}} default button 1"], check=False)
    else:
        print(f"{title}: {text}")


def make_icon(status):
    """The tray icon, drawn here: a little DSi (two screens) with a status dot."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body, edge = (52, 60, 72, 255), (24, 30, 38, 255)
    screen, screen_hi = (40, 104, 112, 255), (70, 142, 148, 255)
    d.rounded_rectangle((8, 2, 56, 30), radius=6, fill=body, outline=edge, width=2)    # top half
    d.rounded_rectangle((8, 33, 56, 61), radius=6, fill=body, outline=edge, width=2)   # bottom half
    d.rectangle((15, 7, 49, 25), fill=screen)
    d.rectangle((15, 7, 49, 9), fill=screen_hi)
    d.rectangle((19, 38, 45, 56), fill=screen)
    d.rectangle((19, 38, 45, 40), fill=screen_hi)
    c = COLORS.get(status, COLORS['waiting'])
    d.ellipse((38, 38, 62, 62), fill=(255, 255, 255, 255))
    d.ellipse((41, 41, 59, 59), fill=c + (255,))
    return img


def _open(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if MAC else "xdg-open", path])


def on_main(fn):
    """Runs fn() on the menu bar's thread on a Mac (AppKit only takes
    changes there), else right away."""
    if MAC:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(fn)
    else:
        fn()


def nudge_local_network():
    """One UDP packet to the local network's discard port, so macOS asks
    for Local Network access right away (it asks when an app first sends
    there, and DSiRPC mostly listens). Nothing listens on that port."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(b"DSiRPC", ("255.255.255.255", 9))
    except OSError as e:
        logging.info(f"Local network check: {e}")


def open_setup():
    """'dsirpc.py setup' in a console window: a new console on Windows,
    Terminal on a Mac (through a small .command file in DSiRPC's data
    folder; the app runs its own copy of setup)."""
    if MAC:
        import shlex
        if getattr(sys, "frozen", False):
            args = [sys.executable, "setup"]
        else:
            args = [sys.executable, os.path.join(ROOT, "dsirpc.py"), "setup"]
        os.makedirs(DATA, exist_ok=True)
        script = os.path.join(DATA, "DSiRPC Setup.command")
        with open(script, "w") as f:
            f.write("#!/bin/sh\nclear\n" + " ".join(shlex.quote(a) for a in args) + "\n")
        os.chmod(script, 0o755)
        subprocess.Popen(["open", script])
        return
    args = [_console_python(), os.path.join(ROOT, "dsirpc.py"), "setup"]
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(args, cwd=ROOT, creationflags=flags)


def _console_python():
    """python.exe next to the running pythonw.exe, for console programs."""
    folder, exe = os.path.split(sys.executable)
    if exe.lower() == "pythonw.exe" and os.path.exists(os.path.join(folder, "python.exe")):
        return os.path.join(folder, "python.exe")
    return sys.executable


def run_tray(cfg, **engine_args):
    import pystray
    from pystray import Menu, MenuItem as Item

    try:
        engine = Engine(cfg, discord=cfg.discord, **engine_args)
    except PortInUse:
        where = "the menu bar" if MAC else "the taskbar's notification area"
        message_box(f"DSiRPC is already running (its icon is in {where}), "
                    "or another DSiRPC tool is using the DSi's UDP port 4244.")
        return 1
    engine.persist = True
    lock = threading.Lock()
    shown = {'status': None}

    def status():
        d = engine.discord.status
        if d.startswith("can't reach") or d.startswith("no Discord"):
            return 'problem'
        return 'playing' if engine.online else 'waiting'

    def notify(body, title):
        try:
            icon.notify(body, title)
        except Exception as e:   # on a Mac it's osascript, which can fail
            logging.info(f"Couldn't show a notification: {e}")

    def refresh(events=()):
        with lock:
            s = status()
            if s != shown['status']:
                icon.icon = make_icon(s)
                shown['status'] = s
            icon.title = f"DSiRPC: {engine.headline()}"[:127]
            icon.update_menu()
            for e in events:
                if e['type'] == 'online':
                    notify(engine.headline(), "DSiRPC: DSi connected")
                elif e['type'] == 'offline':
                    notify("No data from the DSi for 30 s. DSiRPC waits for it to come back.", "DSiRPC")
                elif e['type'] == 'game_changed':
                    notify(f"Now playing {e['title']}", "DSiRPC")
                elif e['type'] == 'achievement':
                    p = e.get('progress')
                    body = f"{e['title']} ({e['points']} points)\n{e['description']}"
                    if p:
                        body += f"\n{p[0]} of {p[1]} in {e['game']}"
                    if not e['sent']:
                        body += "\n(not sent to RetroAchievements)"
                    notify(body[:255], "Achievement unlocked!")
                elif e['type'] == 'offline_unlocks':
                    n = e['count']
                    body = ", ".join(e['titles'][:3]) + (f" and {n - 3} more" if n > 3 else "")
                    body += "\n" + ("Sent to RetroAchievements." if e['sent']
                                    else "Not sent: sending unlocks is off in setup.")
                    notify(body[:255], f"{n} achievement{'s' if n != 1 else ''} from offline play")

    def toggle_discord(icon_, item):
        on = not engine.discord.enabled
        engine.set_discord(on)
        engine.cfg.discord = on
        engine.save_config()

    def overlay_closed():
        engine.cfg.overlay = False
        engine.save_config()
        on_main(refresh)

    def toggle_overlay(icon_, item):
        on = not engine.overlay_on
        engine.set_overlay(on, on_closed=overlay_closed)
        engine.cfg.overlay = on
        engine.save_config()

    def console_item(key, label):
        def pick(icon_, item):
            engine.set_console_icon(key)
            engine.save_config()

        def checked(item):
            return (engine.cfg.console_icon or "").lower() == key.lower()
        return Item(label, pick, checked=checked, radio=True)

    def console_menu():
        from rpc.generic_presence import console_icons
        items = [console_item(key, label) for key, label, _ in console_icons()]
        items.append(console_item("", "None (RetroAchievements icon)"))
        return Menu(*items)

    def toggle_startup(icon_, item):
        try:
            startup.set_enabled(not startup.is_enabled())
        except OSError as e:
            notify(f"Couldn't change it: {e}", "DSiRPC")

    def quit_(icon_, item):
        icon.stop()

    menu = Menu(
        Item(lambda i: engine.headline(), None, enabled=False),
        Item(lambda i: f"Discord: {engine.discord.status}", None, enabled=False),
        Item(lambda i: engine.ra_status(), None, enabled=False),
        Menu.SEPARATOR,
        Item("Discord presence", toggle_discord, checked=lambda i: engine.discord.enabled),
        Item("Console icon", console_menu()),
        Item("Overlay window", toggle_overlay, checked=lambda i: engine.overlay_on, default=True),
        Item(startup.label(), toggle_startup, checked=lambda i: startup.is_enabled(),
             visible=startup.supported()),
        Menu.SEPARATOR,
        Item("Setup...", lambda i, it: open_setup()),
        Item("Open log", lambda i, it: _open(LOG_FILE)),
        Item("Open DSiRPC folder", lambda i, it: _open(DATA)),
        Menu.SEPARATOR,
        Item("Quit", quit_),
    )
    icon = pystray.Icon("DSiRPC", make_icon('waiting'), "DSiRPC: starting", menu)
    engine.on_change = lambda events: on_main(lambda: refresh(events))

    def show():
        icon.visible = True

    def setup(icon_):
        try:
            on_main(show)
            if MAC:
                nudge_local_network()
            engine.start()
            if MAC and not cfg.loaded_from:
                open_setup()   # the first time: there's no dsirpc.cfg yet
            if cfg.overlay:
                engine.set_overlay(True, on_closed=overlay_closed)
            on_main(refresh)
        except Exception:
            logging.exception("Tray setup failed")

    logging.info("DSiRPC started in the tray")
    try:
        icon.run(setup=setup)
    finally:
        engine.stop()
        logging.info("DSiRPC stopped")
    return 0
