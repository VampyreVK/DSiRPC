"""
tray.py - DSiRPC as a tray icon (DSiRPC.bat, or 'dsirpc.py tray').

Right-click the icon for the menu:

    Playing Mario Kart DS              what's running (or what it waits for)
    Discord: showing Mario Kart DS     what Discord shows
    RetroAchievements: 12 of 132 ...   achievements (signed in, or not)
    ---
    Discord presence                   on/off
    Console icon  >                    the small picture for games without their own presence
    Overlay window                     on/off (a left click on the icon does this too)
    Start with Windows                 on/off
    ---
    Setup...                           'dsirpc.py setup' in a console window
    Open log / Open DSiRPC folder
    ---
    Quit

The dot on the icon is green while the game answers, amber while DSiRPC
waits for the DSi, and red when Discord can't be reached or has no
application ID. The on/off choices are saved in dsirpc.cfg.

Only one DSiRPC can run at a time (it needs the DSi's UDP port, 4244); a
second one says so and exits.
"""

import logging
import os
import subprocess
import sys
import threading

from . import startup
from .engine import Engine, PortInUse, LOG_FILE, ROOT

COLORS = {
    'playing': (88, 208, 128),
    'waiting': (240, 192, 48),
    'problem': (232, 72, 56),
}


def message_box(text, title="DSiRPC"):
    """A Windows message box (or a printed line elsewhere)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
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
        subprocess.Popen(["xdg-open", path])


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
        message_box("DSiRPC is already running (its icon is in the taskbar's notification area), "
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
                    icon.notify(engine.headline(), "DSiRPC: DSi connected")
                elif e['type'] == 'offline':
                    icon.notify("No data from the DSi for 30 s. DSiRPC waits for it to come back.", "DSiRPC")
                elif e['type'] == 'game_changed':
                    icon.notify(f"Now playing {e['title']}", "DSiRPC")
                elif e['type'] == 'achievement':
                    p = e.get('progress')
                    body = f"{e['title']} ({e['points']} points)\n{e['description']}"
                    if p:
                        body += f"\n{p[0]} of {p[1]} in {e['game']}"
                    if not e['sent']:
                        body += "\n(not sent to RetroAchievements)"
                    icon.notify(body[:255], "Achievement unlocked!")

    def toggle_discord(icon_, item):
        on = not engine.discord.enabled
        engine.set_discord(on)
        engine.cfg.discord = on
        engine.save_config()

    def overlay_closed():
        engine.cfg.overlay = False
        engine.save_config()
        refresh()

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
            icon.notify(f"Couldn't change it: {e}", "DSiRPC")

    def open_setup(icon_, item):
        args = [_console_python(), os.path.join(ROOT, "dsirpc.py"), "setup"]
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(args, cwd=ROOT, creationflags=flags)

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
        Item("Start with Windows", toggle_startup, checked=lambda i: startup.is_enabled(),
             visible=startup.supported()),
        Menu.SEPARATOR,
        Item("Setup...", open_setup),
        Item("Open log", lambda i, it: _open(LOG_FILE)),
        Item("Open DSiRPC folder", lambda i, it: _open(ROOT)),
        Menu.SEPARATOR,
        Item("Quit", quit_),
    )
    icon = pystray.Icon("DSiRPC", make_icon('waiting'), "DSiRPC: starting", menu)
    engine.on_change = refresh

    def setup(icon_):
        try:
            icon.visible = True
            engine.start()
            if cfg.overlay:
                engine.set_overlay(True, on_closed=overlay_closed)
            refresh()
        except Exception:
            logging.exception("Tray setup failed")

    logging.info("DSiRPC started in the tray")
    try:
        icon.run(setup=setup)
    finally:
        engine.stop()
        logging.info("DSiRPC stopped")
    return 0
