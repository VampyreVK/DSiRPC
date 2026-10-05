"""
setup_wizard.py - 'dsirpc.py setup' (Setup.bat): first-time setup, and safe
to run again any time to change something. Every question shows the current
value; Enter keeps it.

  1. Python and packages   checks requirements.txt and offers to install
                           what's missing; checks the rcheevos library
  2. Discord               the application ID(s)
  3. RetroAchievements     an RA emulator's folder (RALibretro), whose
                           RACache holds the set files of games you've played
  4. Set files             for the game the DSi is running (and any game code
                           you type), picked from that cache into ra/
  5. Start with Windows    (Windows only)

Everything is saved to dsirpc.cfg. Nothing is sent anywhere.
"""

import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")

# (pip name, import name, minimum version)
PACKAGES = [
    ("pypresence", "pypresence", "4.6"),
    ("pygame-ce", "pygame", "2.5"),
    ("Pillow", "PIL", "10"),
    ("pystray", "pystray", "0.19"),
]

DISCORD_ID = re.compile(r"^\d{17,20}$")


def ask(prompt, default=""):
    """input() that returns `default` on Enter or when there's no console."""
    shown = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{shown}: ").strip()
    except EOFError:
        print()
        return default
    return answer or default


def yes(prompt, default=True):
    answer = ask(f"{prompt} ({'Y/n' if default else 'y/N'})").lower()
    if not answer:
        return default
    return answer.startswith("y")


def heading(n, text):
    print(f"\n[{n}/5] {text}\n" + "-" * (len(text) + 6))


def _version_tuple(text):
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def check_packages():
    """[(pip name, installed version or None, ok)]"""
    from importlib import metadata
    out = []
    for pip_name, _, minimum in PACKAGES:
        try:
            version = metadata.version(pip_name)
        except metadata.PackageNotFoundError:
            version = None
        ok = version is not None and _version_tuple(version) >= _version_tuple(minimum)
        out.append((pip_name, version, ok))
    return out


def step_packages():
    heading(1, "Python and packages")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 9):
        print("DSiRPC needs Python 3.9 or newer.")
    if not in_venv:
        print("Tip: Setup.bat makes a .venv folder just for DSiRPC, so its packages don't mix with others.")
    packages = check_packages()
    for name, version, ok in packages:
        print(f"  {name:12} {version or 'missing':10} {'ok' if ok else 'needed'}")
    if not all(ok for _, _, ok in packages):
        if yes("Install or update them now (pip install -r requirements.txt)?"):
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS])
            if r.returncode != 0:
                print("pip didn't finish; DSiRPC may not start until the packages are installed.")
    try:
        sys.path.insert(0, ROOT)
        from core.rcheevos import library, RcheevosMissing
        try:
            library()
            print("  rcheevos     ok (RetroAchievements rich presence)")
        except RcheevosMissing as e:
            print(f"  rcheevos     missing: {e}")
            print("               Games other than Platinum still show their name and box art.")
    except ImportError as e:
        print(f"  rcheevos     can't check ({e})")


def _ask_id(prompt, current):
    while True:
        value = ask(prompt + " ('-' to clear)", current)
        if value == "-":
            return ""
        if not value or DISCORD_ID.match(value):
            return value
        print("  That isn't an application ID: it's a long number (17-20 digits) from the")
        print("  Developer Portal's General Information page.")


def step_discord(cfg):
    heading(2, "Discord")
    print("DSiRPC shows your game through a Discord application, whose name is what")
    print("Discord shows after \"Playing\" (it also sends the game's name, which Discord")
    print("shows instead where it can). Make one at")
    print("  https://discord.com/developers/applications")
    print("(New Application, name it e.g. \"Pokémon Platinum\" or \"Nintendo DS\") and copy its")
    print("Application ID. One application for everything is fine.")
    print()
    cfg.discord_client_id = _ask_id("Application ID for Pokemon Platinum (and any game without its own)",
                                    cfg.discord_client_id)
    default = cfg.discord_apps.get("DEFAULT", "")
    other = _ask_id("Application ID for other games (Enter: the same one)", default)
    if other:
        cfg.discord_apps["DEFAULT"] = other
    else:
        cfg.discord_apps.pop("DEFAULT", None)
    if not cfg.has_discord_id:
        print("No application ID: DSiRPC can still run the overlay, but not the Discord presence.")


def step_ra(cfg):
    from core import ra_cache
    heading(3, "RetroAchievements (optional)")
    print("For games other than Platinum, DSiRPC can show the game's RetroAchievements")
    print("rich presence (\"Racing in Figure-8 Circuit\") and icon. It needs the game's")
    print("set file, which an RA emulator keeps after you load the game once while")
    print("logged in: RALibretro keeps them in RACache\\Data in its folder.")
    print()
    while True:
        path = ask("RALibretro's folder (or its RACache folder); Enter to skip, '-' to clear", cfg.racache)
        if path == "-":
            cfg.racache = ""
            return []
        if not path:
            return []
        if ra_cache.data_dir(path):
            cfg.racache = path.strip().strip('"')
            break
        print(f"  No RACache\\Data with set files in {path}.")
        if not yes("  Try another folder?"):
            return []
    sets = ra_cache.scan(cfg.racache)
    print(f"\n{len(sets)} DS/DSi set{'s' if len(sets) != 1 else ''} in {ra_cache.data_dir(cfg.racache)}:")
    have = _sets_in_ra()
    for s in sets:
        where = ", ".join(sorted(code for code, sid in have.items() if sid == s.id))
        print(f"  {s.id:>6}  {s.title}" + (f"  (in ra/ as {where})" if where else ""))
    cfg.ra_auto_import = yes("Copy a game's set into ra/ on its own when exactly one clearly matches?",
                             cfg.ra_auto_import)
    return sets


def _sets_in_ra():
    """{game code: RA game ID} for the set files already in ra/."""
    from core import ra_set
    out = {}
    if not os.path.isdir(ra_set.RA_DIR):
        return out
    for name in os.listdir(ra_set.RA_DIR):
        m = re.match(r"^([A-Z0-9]{4})\.json$", name, re.I)
        if m:
            try:
                out[m.group(1).upper()] = ra_set.load(os.path.join(ra_set.RA_DIR, name)).id
            except ra_set.SetFileError:
                pass
    for code, gid in ra_set._mapping(ra_set.RA_DIR).items():
        out.setdefault(code, int(gid))
    return out


def detect_game(port=4244, wait=10.0):
    """(game dict, header title, how) for the game the DSi runs now, or None.
    If DSiRPC is running (it holds the port), what it last saw."""
    from core.dsirpc_client import DSiClient
    try:
        client = DSiClient(port=port)
    except OSError:
        state_file = os.path.join(ROOT, "logs", "state.json")
        try:
            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            print("UDP port 4244 is in use (another DSiRPC tool?), so the DSi can't be heard here.")
            return None
        if time.time() - state.get("time", 0) < 90 and state.get("online") and state.get("game"):
            return state["game"], state.get("header_title") or "", "DSiRPC (running)"
        print("DSiRPC is running but doesn't see a game right now.")
        return None
    try:
        print(f"Listening for the DSi for {wait:.0f} s (start the game on it now if it isn't running)...")
        if not client.wait_for_dsi(wait):
            return None
        client.listen(1.5)
        if not client.game:
            return None
        from core import ra_cache
        from core.dsi_memory import DsiRam
        try:
            title, code = ra_cache.read_header(DsiRam(client))
        except (TimeoutError, RuntimeError):
            title, code = "", ""
        return client.game, (title if code == client.game["code"] else ""), "The DSi"
    finally:
        client.sock.close()


def _pick(sets, ranked=None):
    """Lets the user pick one of `sets` (ranked [(score, set)] first). The set, or None."""
    showing = [s for _, s in ranked] if ranked else list(sets)
    while True:
        for i, s in enumerate(showing, 1):
            n = len(s.official_achievements)
            extra = "" if s.rich_presence else ", no rich presence"
            print(f"  {i:>2}) {s.title} (RA game {s.id}, {n} achievement{'' if n == 1 else 's'}{extra})")
        more = len(showing) < len(sets)
        answer = ask("Number to use" + (", 'a' for all sets" if more else "") + ", Enter to skip").lower()
        if not answer:
            return None
        if answer == "a" and more:
            showing = list(sets)
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(showing):
            return showing[int(answer) - 1]
        print("  Pick one of the numbers.")


def _add(code, s):
    from core import ra_cache
    dest = ra_cache.import_set(s, code)
    if dest is None:
        if not yes(f"ra/{code}.json already exists. Replace it?", False):
            return
        dest = ra_cache.import_set(s, code, force=True)
    print(f"Saved {s.title} as {os.path.relpath(dest, ROOT)}.")


def step_sets(cfg, sets):
    from core import games, ra_cache
    heading(4, "Set files for your games")
    if not sets:
        print("No RA cache to pick from (step 3). You can still add a set file by hand:")
        print("  python tools/ra_tool.py add <the .json file> --code <game code>")
        return
    have = _sets_in_ra()
    if yes("Look for the game the DSi is running now?"):
        found = detect_game()
        if not found:
            print("No game heard from the DSi.")
        else:
            game, header_title, how = found
            code = game["code"]
            print(f"{how} says it's running {games.name(game)}" +
                  (f" (header title '{header_title}')" if header_title else "") + ".")
            if games.is_platinum(game):
                print("Pokemon Platinum has its own presence and needs no set file.")
            elif code in have and not yes(f"ra/ already has a set for {code} (RA game {have[code]}). Pick another?", False):
                pass
            else:
                ranked = ra_cache.candidates(header_title, sets) if header_title else []
                if ranked:
                    print("Sets that match its title, best first:")
                else:
                    print("No set's title matches; all of them:")
                s = _pick(sets, ranked)
                if s:
                    _add(code, s)
    print("\nA game's code is 4 letters or digits: AMCE in the NTR-AMCE-USA on Mario Kart DS's")
    print("cartridge label, and in DSiRPC's log while the game runs.")
    while True:
        code = ask("Add a set for another game code? Enter to finish").upper()
        if not code:
            return
        if not re.fullmatch(r"[A-Z0-9]{4}", code):
            print("  A game code is 4 letters or digits, like AMCE.")
            continue
        s = _pick(sets)
        if s:
            _add(code, s)


def step_startup():
    from . import startup
    heading(5, "Start with Windows")
    if not startup.supported():
        print("Only on Windows; skipped.")
        return
    on = startup.is_enabled()
    want = yes("Start DSiRPC in the tray when you sign in to Windows?", on)
    if want != on or (want and startup.current() != startup.command()):
        try:
            startup.set_enabled(want)
            print("On." if want else "Off.")
        except OSError as e:
            print(f"Couldn't change it: {e}")


def run_setup():
    sys.path.insert(0, ROOT)
    from utils.config import Config, OLD_CONFIG_NAME
    print("DSiRPC setup")
    print("============")
    print("Enter keeps the value in [brackets]. Run this again any time to change something.")
    step_packages()
    cfg = Config()
    migrated = cfg.loaded_from and os.path.basename(cfg.loaded_from) == OLD_CONFIG_NAME
    step_discord(cfg)
    sets = step_ra(cfg)
    try:
        cfg.save()  # before the DSi step, so a running DSiRPC picks up the RA folder
    except OSError as e:
        print(f"Couldn't save {cfg.path}: {e}")
    step_sets(cfg, sets)
    step_startup()
    try:
        cfg.save()
        print(f"\nSaved {cfg.path}.")
        if migrated:
            print(f"(Your settings from {OLD_CONFIG_NAME} are in it now; the old file isn't used anymore.)")
    except OSError as e:
        print(f"\nCouldn't save {cfg.path}: {e}")
        return 1
    print()
    print("All set. Start DSiRPC with DSiRPC.bat (it sits in the tray, by the clock),")
    print("or 'python dsirpc.py' to run it in a console. If the DSi is never found,")
    print("allow Python through the Windows firewall on private networks.")
    if sys.stdin and sys.stdin.isatty():
        ask("Press Enter to close")
    return 0
