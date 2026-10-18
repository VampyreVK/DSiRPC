#!/usr/bin/env python3
"""
build_app.py - makes the macOS download: DSiRPC.app, zipped with the two DSi
files and plain instructions. On a Mac (Apple silicon), from the repo root:

    python -m pip install -r requirements.txt pyinstaller certifi
    python packaging/macos/build_app.py --version v0.5.0 --nds-dir <folder with the .nds files>

The GitHub Action (.github/workflows/build.yml) runs it for every build and
attaches the zip to releases. In order, it:
  1. builds third_party/rcheevos/librcheevos.dylib if it isn't there:
     rcheevos RCHEEVOS_TAG from GitHub plus dsirpc_offline.c, with the
     system's compiler, like the Windows DLL (third_party/rcheevos/README.md)
  2. writes the Discord applications the download comes with (defaults.cfg),
     as the Windows download does
  3. runs PyInstaller (DSiRPC.spec), then the app's own self-check
  4. zips it with ditto, which keeps the app's signature and links intact:

    DSiRPC/
      DSiRPC.app
      README.txt              what to do, in order (packaging/macos/README.txt)
      SD card/DSiRPC/         dsirpc-launcher.nds and nds-bootstrap-dsirpc.nds
      licenses/

The app isn't signed with a Developer ID (PyInstaller signs it ad hoc), so
the first launch needs right-click > Open; README.txt says how.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
import build_release  # noqa: E402  (packaging/build_release.py: the SD card, licenses, defaults.cfg)

RCHEEVOS_TAG = "v12.5.0"   # third_party/rcheevos/README.md's version: dsirpc_offline.c needs the same
RCHEEVOS_URL = "https://github.com/RetroAchievements/rcheevos.git"
DYLIB = os.path.join(ROOT, "third_party", "rcheevos", "librcheevos.dylib")


def log(text):
    print(text, flush=True)


def build_rcheevos(work):
    if os.path.exists(DYLIB):
        log(f"rcheevos: using {os.path.relpath(DYLIB, ROOT)}")
        return
    src = os.path.join(work, "rcheevos")
    if not os.path.isdir(src):
        log(f"rcheevos: fetching {RCHEEVOS_TAG}")
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", RCHEEVOS_TAG, RCHEEVOS_URL, src],
                       check=True)
    sources = sorted(os.path.join("src", "rcheevos", n) for n in os.listdir(os.path.join(src, "src", "rcheevos"))
                     if n.endswith(".c"))
    sources += [os.path.join("src", "rhash", "md5.c"), os.path.join("src", "rc_compat.c"),
                os.path.join("src", "rc_util.c"), os.path.join("src", "rc_version.c"),
                os.path.join(ROOT, "third_party", "rcheevos", "dsirpc_offline.c")]
    log("rcheevos: building librcheevos.dylib")
    subprocess.run(["cc", "-O2", "-shared", "-fPIC", "-DRC_SHARED", "-Iinclude", "-Isrc", "-Isrc/rcheevos",
                    *sources, "-o", DYLIB, "-install_name", "@rpath/librcheevos.dylib"], cwd=src, check=True)


def build_app(version, defaults, work, dist):
    env = dict(os.environ, DSIRPC_VERSION=version, DSIRPC_DEFAULTS=defaults or "")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", dist, "--workpath", os.path.join(work, "pyinstaller"),
                    os.path.join(HERE, "DSiRPC.spec")], cwd=ROOT, env=env, check=True)
    app = os.path.join(dist, "DSiRPC.app")
    log("Checking the app")
    subprocess.run([os.path.join(app, "Contents", "MacOS", "DSiRPC"), "selfcheck"], check=True, timeout=120)
    return app


def main():
    ap = argparse.ArgumentParser(description="Build DSiRPC's macOS download (a zip with DSiRPC.app)")
    ap.add_argument("--version", default="dev", help="shown in README.txt and the zip's name (e.g. v0.5.0)")
    ap.add_argument("--nds-dir", help="folder with dsirpc-launcher.nds and nds-bootstrap-dsirpc.nds")
    ap.add_argument("--require-nds", action="store_true", help="fail if the .nds files aren't there")
    ap.add_argument("--discord-client-id", default=os.environ.get("DISCORD_CLIENT_ID", ""),
                    help="Discord application for Platinum and other games (default: $DISCORD_CLIENT_ID)")
    ap.add_argument("--discord-default-id", default=os.environ.get("DISCORD_DEFAULT_CLIENT_ID", ""),
                    help="Discord application for games other than Platinum (default: $DISCORD_DEFAULT_CLIENT_ID)")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where the zip goes (default dist/)")
    ap.add_argument("--work", default=os.path.join(ROOT, "build", "macos"), help="scratch folder")
    args = ap.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("The macOS app has to be built on a Mac.")

    os.makedirs(args.work, exist_ok=True)
    build_rcheevos(args.work)

    extra = os.path.join(args.work, "extra")
    shutil.rmtree(extra, ignore_errors=True)
    os.makedirs(extra)
    build_release.add_defaults(extra, args.discord_client_id.strip(), args.discord_default_id.strip())
    defaults = os.path.join(extra, "defaults.cfg")
    app = build_app(args.version, defaults if os.path.exists(defaults) else None, args.work,
                    os.path.join(args.work, "dist"))

    pkg = os.path.join(args.work, "package", "DSiRPC")
    shutil.rmtree(os.path.dirname(pkg), ignore_errors=True)
    os.makedirs(pkg)
    subprocess.run(["ditto", app, os.path.join(pkg, "DSiRPC.app")], check=True)
    build_release.add_sd_card(pkg, args.nds_dir, args.require_nds)
    build_release.add_text(pkg, args.version, args.nds_dir)   # licenses/ (and the Windows README, replaced below)
    os.remove(os.path.join(pkg, "version.txt"))
    with open(os.path.join(HERE, "README.txt"), encoding="utf-8") as f:
        text = f.read().replace("{version}", args.version)
    with open(os.path.join(pkg, "README.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    shutil.copy2(os.path.join(HERE, "THIRD-PARTY-macOS.txt"), os.path.join(pkg, "licenses", "THIRD-PARTY-macOS.txt"))

    os.makedirs(args.out, exist_ok=True)
    out_file = os.path.join(args.out, f"DSiRPC-{args.version}-macos.zip")
    if os.path.exists(out_file):
        os.remove(out_file)
    log(f"Writing {out_file}")
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", pkg, out_file], check=True)
    log(f"Done: {out_file} ({os.path.getsize(out_file) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
