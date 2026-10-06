#!/usr/bin/env python3
"""
build_release.py - makes the Windows download: one folder with DSiRPC, its
own Python, the two DSi files and plain instructions, zipped. Nothing needs
installing to use it.

    python packaging/build_release.py --nds-dir <folder with the .nds files> --version v0.4.0

The GitHub Action (.github/workflows/build.yml) runs this for every build and
attaches the zip to releases. It also works on a PC with internet access
(it downloads Python's embeddable package and the packages' wheels). On a
PC that isn't Windows, `--check` (start the bundled Python once) is skipped.

The zip holds one folder, DSiRPC/, so unzipping a newer release over an older
one updates it and keeps your settings (dsirpc.cfg, ra/, logs/ aren't in it):

    DSiRPC/
      README.txt              what to do, in order (packaging/README.txt)
      Setup.bat, DSiRPC.bat   first-time setup, and DSiRPC in the tray
      SD card/DSiRPC/         dsirpc-launcher.nds and nds-bootstrap-dsirpc.nds
      python/                 Python's embeddable package, with DSiRPC's
                              packages in Lib/site-packages
      dsirpc.py, app/, core/, overlay/, rpc/, utils/, tools/, third_party/,
      Assets/Consoles/, ...   DSiRPC itself
      defaults.cfg            the Discord applications it comes with, if any
                              (--discord-client-id; see utils/config.py)
      licenses/               the licenses of what's bundled
"""

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "packaging")

# Python's embeddable package (64-bit). The packages in requirements.txt are
# installed for this version, so change both together.
PYTHON_VERSION = "3.13.16"
PYTHON_URL = "https://www.python.org/ftp/python/{v}/python-{v}-embed-amd64.zip"

# What DSiRPC needs to run, relative to the repo root
FILES = [
    "dsirpc.py", "requirements.txt", "Setup.bat", "DSiRPC.bat", "LICENSE",
    "dsirpc.cfg.sample", "PokeGen4Charmap.txt", "ra/README.md",
]
FOLDERS = [
    "app", "core", "overlay", "rpc", "utils", "tools", "third_party/rcheevos",
    # The tray's Console icon menu lists these. The overlay's sprites are
    # downloaded when first needed (overlay/sprites.py).
    "Assets/Consoles",
]
SKIP = ["__pycache__", "*.pyc", "*.pyo", "tools/charmap", "*.so", "*.dylib", "*.tmp"]

NDS_FILES = ["dsirpc-launcher.nds", "nds-bootstrap-dsirpc.nds"]
SD_FOLDER = "SD card/DSiRPC"


def log(text):
    print(text, flush=True)


def skipped(rel):
    rel = rel.replace(os.sep, "/")
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, p) or rel == p or rel.startswith(p + "/") for p in SKIP)


def copy_tree(rel, dest_root):
    src = os.path.join(ROOT, rel)
    if not os.path.isdir(src):
        raise SystemExit(f"Missing folder: {rel}")
    for folder, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not skipped(os.path.relpath(os.path.join(folder, d), ROOT))]
        for name in files:
            path = os.path.join(folder, name)
            r = os.path.relpath(path, ROOT)
            if skipped(r):
                continue
            dest = os.path.join(dest_root, r)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(path, dest)


def fetch(url, dest):
    if os.path.exists(dest):
        return dest
    log(f"Downloading {url}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".tmp"
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, dest)
    return dest


def add_python(version, pkg, cache):
    """Python's embeddable package in pkg/python, set up to find DSiRPC's
    packages (Lib/site-packages) and DSiRPC itself (the folder above)."""
    py = os.path.join(pkg, "python")
    archive = fetch(PYTHON_URL.format(v=version), os.path.join(cache, f"python-{version}-embed-amd64.zip"))
    with zipfile.ZipFile(archive) as z:
        z.extractall(py)
    major, minor = version.split(".")[:2]
    pth = os.path.join(py, f"python{major}{minor}._pth")
    if not os.path.exists(pth):
        raise SystemExit(f"{os.path.basename(pth)} isn't in Python's embeddable package")
    with open(pth, "w", newline="\r\n") as f:
        f.write(f"python{major}{minor}.zip\n.\nLib\\site-packages\n..\nimport site\n")

    site = os.path.join(py, "Lib", "site-packages")
    os.makedirs(site, exist_ok=True)
    log("Installing DSiRPC's packages for Windows (requirements.txt)")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
        "--target", site, "--only-binary=:all:", "--platform", "win_amd64",
        "--python-version", f"{major}.{minor}", "--implementation", "cp",
        "-r", os.path.join(ROOT, "requirements.txt"),
    ], check=True)
    for folder, dirs, _ in os.walk(site):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(folder, d))
                dirs.remove(d)
    shutil.rmtree(os.path.join(site, "bin"), ignore_errors=True)


def add_sd_card(pkg, nds_dir, require):
    dest = os.path.join(pkg, *SD_FOLDER.split("/"))
    os.makedirs(dest, exist_ok=True)
    missing = []
    for name in NDS_FILES:
        src = os.path.join(nds_dir, name) if nds_dir else None
        if src and os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, name))
        else:
            missing.append(name)
    if missing:
        if require:
            raise SystemExit(f"Missing DSi files in {nds_dir}: {', '.join(missing)}")
        log(f"Warning: no {', '.join(missing)} (pass --nds-dir): the SD card folder is incomplete")


def add_text(pkg, version, nds_dir):
    with open(os.path.join(HERE, "README.txt"), encoding="utf-8") as f:
        text = f.read().replace("{version}", version)
    with open(os.path.join(pkg, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    with open(os.path.join(pkg, "version.txt"), "w", newline="\r\n") as f:
        f.write(f"DSiRPC {version}\nPython {PYTHON_VERSION}\n")

    lic = os.path.join(pkg, "licenses")
    os.makedirs(lic, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "THIRD-PARTY.txt"), os.path.join(lic, "THIRD-PARTY.txt"))
    # nds-bootstrap's GPLv3, from the CI artifact or a full checkout
    candidates = [os.path.join(ROOT, "nds-bootstrap", "LICENSE")]
    if nds_dir:
        candidates.insert(0, os.path.join(nds_dir, "LICENSE-nds-bootstrap.txt"))
    found = next((c for c in candidates if os.path.exists(c)), None)
    if found:
        shutil.copy2(found, os.path.join(lic, "nds-bootstrap-GPLv3.txt"))
    else:
        log("Warning: nds-bootstrap's license wasn't found (licenses/nds-bootstrap-GPLv3.txt)")


def add_defaults(pkg, client_id, default_id):
    if not (client_id or default_id):
        log("No Discord application given: setup will ask for one (--discord-client-id)")
        return
    for value in (client_id, default_id):
        if value and not (value.isdigit() and 17 <= len(value) <= 20):
            raise SystemExit(f"{value!r} isn't a Discord application ID")
    with open(os.path.join(pkg, "defaults.cfg"), "w", newline="\r\n") as f:
        f.write("# The Discord applications this download of DSiRPC comes with. dsirpc.cfg\n"
                "# (your settings, which setup writes) can name others instead. This file is\n"
                "# replaced by each new release.\n\n"
                f"[connection]\ndiscord_client_id: {client_id}\n\n"
                f"[discord_apps]\ndefault: {default_id}\n")


def check(pkg):
    """Starts the bundled Python once: imports everything DSiRPC uses."""
    if sys.platform != "win32":
        log("Not on Windows: skipping the check of the bundled Python")
        return
    py = os.path.join(pkg, "python", "python.exe")
    code = ("import pypresence, pygame, PIL, pystray, ssl, ctypes, winreg\n"
            "from core import rcheevos; rcheevos.library()\n"
            "import app.engine, app.tray, app.setup_wizard, overlay.app\n"
            "print('Bundled Python works:', __import__('sys').version)\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    subprocess.run([py, "-c", code], cwd=os.path.join(pkg, "python"), env=env, check=True)
    subprocess.run([py, "dsirpc.py", "--help"], cwd=pkg, env=env, check=True, stdout=subprocess.DEVNULL)


def make_zip(pkg, out_file):
    log(f"Writing {out_file}")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    base = os.path.dirname(pkg)
    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder, dirs, files in os.walk(pkg):
            dirs.sort()
            for name in sorted(files):
                path = os.path.join(folder, name)
                z.write(path, os.path.relpath(path, base))


def main():
    ap = argparse.ArgumentParser(description="Build DSiRPC's Windows download (a zip)")
    ap.add_argument("--version", default="dev", help="shown in README.txt and the zip's name (e.g. v0.4.0)")
    ap.add_argument("--nds-dir", help="folder with dsirpc-launcher.nds and nds-bootstrap-dsirpc.nds")
    ap.add_argument("--require-nds", action="store_true", help="fail if the .nds files aren't there")
    ap.add_argument("--python", default=PYTHON_VERSION, help=f"Python version to bundle (default {PYTHON_VERSION})")
    ap.add_argument("--discord-client-id", default=os.environ.get("DISCORD_CLIENT_ID", ""),
                    help="Discord application for Platinum and other games (default: $DISCORD_CLIENT_ID)")
    ap.add_argument("--discord-default-id", default=os.environ.get("DISCORD_DEFAULT_CLIENT_ID", ""),
                    help="Discord application for games other than Platinum (default: $DISCORD_DEFAULT_CLIENT_ID)")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where the zip goes (default dist/)")
    ap.add_argument("--work", default=os.path.join(ROOT, "build", "package"), help="scratch folder")
    ap.add_argument("--check", action="store_true", help="start the bundled Python once (Windows only)")
    args = ap.parse_args()

    pkg = os.path.join(args.work, "DSiRPC")
    shutil.rmtree(pkg, ignore_errors=True)
    os.makedirs(pkg)

    for rel in FILES:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            raise SystemExit(f"Missing file: {rel}")
        dest = os.path.join(pkg, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if rel.endswith(".bat"):
            # cmd needs CRLF line endings (a checkout outside Windows has LF)
            with open(src, "rb") as f:
                data = f.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            with open(dest, "wb") as f:
                f.write(data)
        else:
            shutil.copy2(src, dest)
    for rel in FOLDERS:
        copy_tree(rel, pkg)

    add_python(args.python, pkg, os.path.join(args.work, "cache"))
    add_sd_card(pkg, args.nds_dir, args.require_nds)
    add_text(pkg, args.version, args.nds_dir)
    add_defaults(pkg, args.discord_client_id.strip(), args.discord_default_id.strip())
    if args.check:
        check(pkg)
    out_file = os.path.join(args.out, f"DSiRPC-{args.version}-windows.zip")
    make_zip(pkg, out_file)
    log(f"Done: {out_file} ({os.path.getsize(out_file) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
