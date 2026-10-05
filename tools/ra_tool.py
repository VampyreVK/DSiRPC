#!/usr/bin/env python3
"""
ra_tool.py - manage the RetroAchievements set files DSiRPC uses (in ra/).

A set file is the game data an RA emulator downloads while you're logged in:
RALibretro keeps it as RACache\\Data\\<RA game ID>.json in its folder after you
load the game once. DSiRPC only reads these files; it never talks to
RetroAchievements itself (see core/ra_set.py). 'dsirpc.py setup' can copy
them from RALibretro's folder for you; this tool is for doing it by hand.

Usage, from the repo root (add without --code, and rp, need the DSi's UDP port, so
not while DSiRPC runs):
  python tools/ra_tool.py add C:\\RALibretro\\RACache\\Data\\11732.json --code CPUE
  python tools/ra_tool.py add C:\\RALibretro\\RACache\\Data\\11732.json    # code from the game the DSi is running
  python tools/ra_tool.py list
  python tools/ra_tool.py info CPUE                # what's in it, and whether its rich presence parses
  python tools/ra_tool.py rp CPUE                  # its rich presence, read from the DSi once
  python tools/ra_tool.py rp CPUE --every 5        # ...and again every 5 s (Ctrl+C to stop)
  python tools/ra_tool.py rp CPUE --file ram_dump.bin
"""

import argparse
import os
import shutil
import sys
import time

# The repo root, for core/ and rpc/ (this file is in tools/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import games
from core import ra_set
from rpc import generic_presence as generic


def cmd_add(args):
    try:
        s = ra_set.load(args.file)
    except ra_set.SetFileError as e:
        print(f"Not a usable set file: {e}")
        return 1
    print(f"Set file: {s.summary()}")
    if s.console_id not in (ra_set.NINTENDO_DS, ra_set.NINTENDO_DSI, 0):
        print(f"Warning: RetroAchievements lists this game for console {s.console_id}, not the DS or DSi.")
    code = args.code
    if not code:
        from core.dsirpc_client import DSiClient
        print("No --code: waiting up to 15 s for the DSi to say which game it's running...")
        c = DSiClient(port=args.port, dsi_ip=args.dsi_ip)
        try:
            if not c.game:
                c.wait_for_dsi(15)
                c.listen(1.5)
            code = c.game["code"] if c.game else None
        finally:
            c.sock.close()
        if not code:
            print("The DSi didn't say (is the game running after the handoff?). Pass --code instead.")
            return 1
        print(f"The DSi is running {games.name(c.game)}.")
    code = code.upper()
    if len(code) != 4:
        print(f"{code!r} isn't a 4-character game code (like CPUE).")
        return 1
    os.makedirs(ra_set.RA_DIR, exist_ok=True)
    dest = os.path.join(ra_set.RA_DIR, f"{code}.json")
    if os.path.exists(dest) and not args.force:
        print(f"{dest} already exists; add --force to replace it.")
        return 1
    shutil.copyfile(args.file, dest)
    print(f"Saved as {os.path.relpath(dest)}: dsirpc.py uses it whenever the DSi runs {code}.")
    return 0


def cmd_list(args):
    if not os.path.isdir(ra_set.RA_DIR):
        print("No ra/ folder yet: add a set file with 'python tools/ra_tool.py add' or 'dsirpc.py setup'.")
        return 0
    found = False
    for name in sorted(os.listdir(ra_set.RA_DIR)):
        if not name.lower().endswith(".json"):
            continue
        found = True
        path = os.path.join(ra_set.RA_DIR, name)
        try:
            print(f"  {name:16} {ra_set.load(path).summary()}")
        except ra_set.SetFileError as e:
            print(f"  {name:16} unreadable: {e}")
    if not found:
        print("No set files in ra/.")
    return 0


def _set_for(code):
    path = ra_set.find(code.upper())
    if not path:
        print(f"No set file for {code} in ra/ ({code}.json, or a line in ra/games.txt).")
        return None
    try:
        return ra_set.load(path)
    except ra_set.SetFileError as e:
        print(f"Unreadable set file: {e}")
        return None


def cmd_info(args):
    s = _set_for(args.code)
    if not s:
        return 1
    print(s.summary())
    print(f"  file:  {os.path.relpath(s.path)}")
    print(f"  icon:  {s.icon_url}")
    cover = generic.cover_url(args.code.upper())
    print(f"  box art (GameTDB): {cover or 'none found'}")
    unofficial = len(s.achievements) - len(s.official_achievements)
    if unofficial:
        print(f"  plus {unofficial} unofficial achievement(s)")
    print(f"  leaderboards: {len(s.leaderboards)}")
    if s.rich_presence:
        try:
            from core.rcheevos import Runtime, RcheevosError
            rt = Runtime()
            try:
                rt.set_rich_presence(s.rich_presence)
                print("  rich presence: parses fine")
            except RcheevosError as e:
                print(f"  rich presence: {e}")
            rt.close()
        except ImportError as e:
            print(f"  rich presence: can't check ({e})")
    return 0


def cmd_rp(args):
    s = _set_for(args.code)
    if not s:
        return 1
    if not s.rich_presence:
        print(f"{s.title} has no rich presence script.")
        return 1
    from core.ra_presence import RichPresenceReader
    from core.rcheevos import RcheevosError
    try:
        reader = RichPresenceReader(s, b"")
    except RcheevosError as e:
        print(f"{s.title}: {e}")
        return 1
    reader.close()
    client = None
    if args.file:
        with open(args.file, "rb") as f:
            ram = f.read()
    else:
        from core.dsirpc_client import DSiClient
        from core.dsi_memory import DsiRam
        client = DSiClient(port=args.port, dsi_ip=args.dsi_ip)
        if not client.wait_for_dsi(15):
            print("No hello from the DSi within 15 s - is the game running after the handoff?")
            return 1
        ram = DsiRam(client)
        running = client.game["code"] if client.game else None
        if running and running != args.code.upper():
            print(f"Note: the DSi is running {games.name(client.game)}, not {args.code.upper()}.")
    reader = RichPresenceReader(s, ram)
    try:
        while True:
            t0 = time.time()
            try:
                text = reader.read()
                fetched = getattr(ram, "bytes_fetched", None)
                extra = f"  ({len(reader.known)} values, {fetched} bytes read)" if fetched is not None else ""
                print(time.strftime("%H:%M:%S"), repr(text) + extra)
            except (TimeoutError, RuntimeError) as e:
                print(time.strftime("%H:%M:%S"), f"read failed: {e}")
            if not args.every or args.file:
                break
            time.sleep(max(0.0, args.every - (time.time() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()
        if client:
            client.sock.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Manage DSiRPC's RetroAchievements set files (ra/)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="copy a set file into ra/ under a game code")
    a.add_argument("file", help="the set file (e.g. RALibretro's RACache\\Data\\<id>.json)")
    a.add_argument("--code", help="the game code (default: the game the DSi is running)")
    a.add_argument("--force", action="store_true", help="replace an existing file")
    sub.add_parser("list", help="list the set files in ra/")
    i = sub.add_parser("info", help="show what a game's set file holds")
    i.add_argument("code")
    r = sub.add_parser("rp", help="evaluate a game's rich presence against the DSi (or a RAM dump)")
    r.add_argument("code")
    r.add_argument("--every", type=float, help="read again every N seconds")
    r.add_argument("--file", help="a 4 MB RAM dump instead of the DSi")
    for p in (a, r):
        p.add_argument("--dsi-ip", help="the IP the launcher shows; skips waiting for a hello packet")
        p.add_argument("--port", type=int, default=4244, help="UDP port (the DSi always uses 4244)")
    args = ap.parse_args()
    return {"add": cmd_add, "list": cmd_list, "info": cmd_info, "rp": cmd_rp}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
