"""
dsirpc_app.py - the macOS app's entry point (packaging/macos/DSiRPC.spec).

Opening DSiRPC.app starts DSiRPC in the menu bar ('dsirpc.py tray'); the
menu's Setup... runs the same program with 'setup' in Terminal, and any of
dsirpc.py's arguments work the same way. 'selfcheck' imports everything the
app needs and loads the rcheevos library: build_app.py runs it on each build.
"""

import multiprocessing
import os
import sys

# Running from a checkout (python packaging/macos/dsirpc_app.py): find DSiRPC
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


CHECK = ["pygame", "PIL", "pypresence", "pystray", "PyObjCTools.AppHelper", "certifi", "dsirpc", "app.engine",
         "app.setup_wizard", "app.tray", "overlay.app", "overlay.remote"]


def selfcheck():
    import importlib
    for name in CHECK:
        importlib.import_module(name)
    import pystray
    from core import rcheevos
    from core.paths import DATA, MAC_APP, ROOT
    rcheevos.library()
    import certifi
    if not os.path.exists(certifi.where()):
        raise SystemExit(f"No CA certificates at {certifi.where()}")
    consoles = os.listdir(os.path.join(ROOT, "Assets", "Consoles"))
    print(f"DSiRPC app OK: pystray {pystray.Icon.__module__}, rcheevos loaded, "
          f"{len(consoles)} console pictures, data folder {DATA} (app: {MAC_APP})")
    return 0


def main():
    # The overlay window's process (overlay/remote.py) starts as this program too
    multiprocessing.freeze_support()
    if getattr(sys, "frozen", False):
        # The app's Python has no CA certificates of its own: HTTPS (the
        # sprites, RetroAchievements) uses certifi's
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        except ImportError:
            pass
    args = [a for a in sys.argv[1:] if not a.startswith("-psn_")]   # older macOS adds a process serial number
    if args == ["selfcheck"]:
        return selfcheck()
    import dsirpc
    return dsirpc.main(args or ["tray"])


if __name__ == "__main__":
    sys.exit(main())
