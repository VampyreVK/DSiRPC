# -*- mode: python ; coding: utf-8 -*-
#
# DSiRPC.spec - PyInstaller's recipe for DSiRPC.app (macOS). build_app.py runs
# it (it builds the rcheevos library and defaults.cfg first, and passes
# DSIRPC_VERSION and DSIRPC_DEFAULTS); from the repo root, on a Mac:
#
#     python -m PyInstaller packaging/macos/DSiRPC.spec
#
# The app is a menu bar app (LSUIElement: no Dock icon), with the icon set in
# Assets/icons (adaptive.icns, light and dark). What it ships: DSiRPC's code,
# the console pictures, the charmap, the rcheevos library and defaults.cfg;
# everything it writes goes to ~/Library/Application Support/DSiRPC
# (core/paths.py).

import os
import re

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
VERSION = os.environ.get("DSIRPC_VERSION", "dev")
DEFAULTS = os.environ.get("DSIRPC_DEFAULTS", "")
# macOS wants numbers here ("0.5.0"); a dev build is 0.0.0
m = re.match(r"v?(\d+(?:\.\d+){0,2})", VERSION)
SHORT_VERSION = m.group(1) if m else "0.0.0"


def modules(package):
    """Every module of one of DSiRPC's packages, by name: some are only
    imported inside functions, so PyInstaller is told about all of them."""
    names = [package]
    for name in sorted(os.listdir(os.path.join(ROOT, package))):
        if name.endswith(".py") and name != "__init__.py":
            names.append(f"{package}.{name[:-3]}")
    return names


hidden = ["pystray._darwin", "PyObjCTools.AppHelper", "certifi", "dsirpc"]
for package in ("app", "core", "overlay", "rpc", "utils"):
    hidden += modules(package)

datas = [
    (os.path.join(ROOT, "Assets", "Consoles"), os.path.join("Assets", "Consoles")),
    (os.path.join(ROOT, "PokeGen4Charmap.txt"), "."),
    (os.path.join(ROOT, "dsirpc.cfg.sample"), "."),
    # The overlay window's Dock icon (overlay/app.py)
    (os.path.join(ROOT, "Assets", "icons", "Exports", "DSiRPC-iOS-Default-1024@1x.png"),
     os.path.join("Assets", "icons", "Exports")),
]
if DEFAULTS:
    datas.append((DEFAULTS, "."))
binaries = [(os.path.join(ROOT, "third_party", "rcheevos", "librcheevos.dylib"),
             os.path.join("third_party", "rcheevos"))]

a = Analysis(
    [os.path.join(SPECPATH, "dsirpc_app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "winreg"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DSiRPC",
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DSiRPC")

app = BUNDLE(
    coll,
    name="DSiRPC.app",
    icon=os.path.join(ROOT, "Assets", "icons", "adaptive.icns"),
    bundle_identifier="io.github.vampyrevk.dsirpc",   # app/startup.py's LABEL too
    version=SHORT_VERSION,
    info_plist={
        "CFBundleName": "DSiRPC",
        "CFBundleDisplayName": "DSiRPC",
        "CFBundleShortVersionString": SHORT_VERSION,
        "CFBundleVersion": SHORT_VERSION,
        "DSiRPCVersion": VERSION,
        "LSUIElement": True,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSLocalNetworkUsageDescription":
            "DSiRPC listens for your DSi or 3DS on the local network to show the game you play on Discord.",
        "NSHumanReadableCopyright": "DSiRPC by VampyreVK (MIT). Not affiliated with Nintendo.",
    },
)
