"""
setup_wizard.py - 'dsirpc.py setup' (Setup.bat): first-time setup, and safe
to run again any time to change something. Every question shows the current
answer in [brackets]; Enter keeps it.

  1. Python packages      checks requirements.txt and offers to install what's
                          missing; checks the rcheevos library
  2. Discord              the application ID(s)
  3. RetroAchievements    signing in (the password is only used to get a
                          login token), your profile, sending unlocks
  4. Your game files      a folder of .nds files, to tell RetroAchievements
                          exactly which game you play (optional)
  5. Achievement sets     for the game the DSi runs now, or any game code:
                          from RetroAchievements or RALibretro's cache
  6. Start with Windows   (Windows only)

Everything is saved to dsirpc.cfg.
"""

import getpass
import json
import os
import re
import subprocess
import sys
import textwrap
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")
STEPS = 6

# (pip name, import name, minimum version)
PACKAGES = [
    ("pypresence", "pypresence", "4.6"),
    ("pygame-ce", "pygame", "2.5"),
    ("Pillow", "PIL", "10"),
    ("pystray", "pystray", "0.19"),
]

DISCORD_ID = re.compile(r"^\d{17,20}$")


def say(text=""):
    """Prints a paragraph, wrapped to the console, indented two spaces. Lines
    starting with "  1." or "  -" are list items: their wrapped lines line up
    under the text."""
    if not text:
        print()
        return
    for para in text.split("\n"):
        m = re.match(r"^(\s*(?:\d+\.|-)\s+)", para)
        hang = "  " + " " * len(m.group(1)) if m else "  "
        print(textwrap.fill(para, width=78, initial_indent="  ", subsequent_indent=hang) if para else "")


def ask(prompt, default=""):
    """input() that returns `default` on Enter or when there's no console."""
    shown = f" [{default}]" if default else ""
    try:
        answer = input(f"  {prompt}{shown}: ").strip()
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
    title = f"Step {n} of {STEPS}: {text}"
    print(f"\n{title}\n" + "-" * len(title))


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


# -- 1. packages -------------------------------------------------------------

def step_packages():
    heading(1, "Python packages")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    say(f"Checking that this Python ({sys.version.split()[0]}) has everything DSiRPC needs...")
    if sys.version_info < (3, 9):
        say("DSiRPC needs Python 3.9 or newer. Get it from https://www.python.org/downloads/")
    if not in_venv:
        say("(Tip: Setup.bat gives DSiRPC its own copy of Python in the .venv folder, so its "
            "packages can't clash with anything else you have.)")
    packages = check_packages()
    for name, version, ok in packages:
        print(f"    {name:12} {version or 'not installed':14} {'ok' if ok else 'needs installing'}")
    if not all(ok for _, _, ok in packages):
        if yes("Install the missing ones now?"):
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS])
            if r.returncode != 0:
                say("The install didn't finish (see the messages above). DSiRPC won't start until "
                    "these packages are installed.")
    try:
        sys.path.insert(0, ROOT)
        from core.rcheevos import library, RcheevosMissing
        try:
            library()
            print("    rcheevos     (RetroAchievements' own library)  ok")
        except RcheevosMissing as e:
            print(f"    rcheevos     missing: {e}")
            say("Without it there are no achievements or RetroAchievements rich presence; games "
                "still show their name and box art.")
    except ImportError as e:
        print(f"    rcheevos     can't check ({e})")


# -- 2. Discord --------------------------------------------------------------

def _ask_id(prompt, current):
    while True:
        value = ask(prompt, current)
        if value == "-":
            return ""
        if not value or DISCORD_ID.match(value):
            return value
        say("That doesn't look like an Application ID: it's a long number (17 to 20 digits). "
            "Copy it from the application's General Information page.")


def step_discord(cfg):
    heading(2, "Discord")
    say("DSiRPC shows your game on Discord through a \"Discord application\". Making one is "
        "free and takes a minute:")
    say("  1. Open https://discord.com/developers/applications and sign in.\n"
        "  2. Click \"New Application\" and give it the name Discord should show after "
        "\"Playing\", for example \"Pokémon Platinum\".\n"
        "  3. Copy its \"Application ID\" (a long number).")
    say()
    say("Paste the Application ID below (type - to remove one that's saved).")
    cfg.discord_client_id = _ask_id("Application ID for Pokémon Platinum", cfg.discord_client_id)
    say()
    say("For every other game, DSiRPC also sends the game's own name, which Discord shows "
        "instead where it can. You can use the same application for them, or make a second "
        "one (for example named \"Nintendo DS\").")
    default = cfg.discord_apps.get("DEFAULT", "")
    other = _ask_id("Application ID for other games (Enter: the same one)", default)
    if other:
        cfg.discord_apps["DEFAULT"] = other
    else:
        cfg.discord_apps.pop("DEFAULT", None)
    if not cfg.has_discord_id:
        say("No Application ID yet, so nothing will show on Discord (the overlay window and "
            "achievements still work). Run setup again once you have one.")


# -- 3. RetroAchievements ----------------------------------------------------

def _sign_in(cfg):
    from core.ra_api import RAClient, RAError, RANetworkError
    while True:
        username = ask("RetroAchievements username (Enter to skip)")
        if not username:
            return False
        try:
            password = getpass.getpass("  Password (it doesn't show while you type): ")
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if not password:
            return False
        try:
            user, token = RAClient().login(username, password)
        except RANetworkError as e:
            say(f"Couldn't reach RetroAchievements ({e}). Check your internet connection and "
                "try again, or press Enter to skip for now.")
            continue
        except RAError as e:
            say(f"RetroAchievements said: {e}")
            continue
        cfg.ra_username, cfg.ra_token = user, token
        say(f"Signed in as {user}. (Only the login token is saved, not your password.)")
        return True


def step_ra(cfg):
    heading(3, "RetroAchievements (optional)")
    say("DSiRPC checks your games' achievements while you play and tells you when you unlock "
        "one. Signing in to RetroAchievements lets it also:")
    say("  - download each game's achievements and rich presence by itself,\n"
        "  - show what you're playing on your RetroAchievements profile, and\n"
        "  - if you choose to, add your unlocks to your account.")
    say("Your password is only used right now, to get a login token from RetroAchievements. "
        "DSiRPC saves that token in dsirpc.cfg, never your password.")
    say()
    if cfg.ra_signed_in:
        say(f"You're signed in as {cfg.ra_username}.")
        answer = ask("Press Enter to stay signed in, type 'new' to sign in again or '-' to sign out")
        if answer == "-":
            cfg.ra_username = cfg.ra_token = ""
            say("Signed out.")
        elif answer.lower() == "new":
            _sign_in(cfg)
    else:
        _sign_in(cfg)
    if not cfg.ra_signed_in:
        say("Not signed in: achievements are only checked on this PC, with the sets you add "
            "yourself (step 5).")
        return
    say()
    cfg.ra_profile = yes("Show what you're playing on your RetroAchievements profile?", cfg.ra_profile)
    say()
    say("Sending unlocks. DSiRPC can add the achievements you unlock to your RetroAchievements "
        "account, as softcore unlocks. Please know before you turn this on:")
    say("  - DSiRPC looks at the game about once a second, not 60 times a second like an "
        "emulator. Most achievements don't mind, but ones about split-second moments can "
        "unlock late, not at all or, rarely, when they shouldn't.\n"
        "  - RetroAchievements doesn't officially support playing on a real DSi.")
    say("With this off, unlocks still pop up here (and are listed in logs\\achievements.log); "
        "they just aren't sent. You can change your mind any time by running setup again.")
    cfg.ra_submit = yes("Send your unlocks to RetroAchievements?", cfg.ra_submit)


# -- 4. game files -----------------------------------------------------------

def step_roms(cfg):
    from core.ra_hash import RomIndex, EXTENSIONS
    heading(4, "Your game files (optional)")
    if not cfg.ra_signed_in:
        say("Skipped: this is only used with a RetroAchievements account (step 3).")
        return
    say("RetroAchievements tells games apart by their files. If this PC has copies of the "
        "games you play on the DSi (say, the ones you play in RALibretro), DSiRPC can use "
        "them to tell RetroAchievements exactly which game and version you're playing. "
        "Without them, it goes by the game's title.")
    say("Subfolders are looked through too. Type - to forget a folder that's saved.")
    while True:
        path = ask("Folder with your .nds files (Enter to skip)", cfg.ra_roms)
        if path == "-":
            cfg.ra_roms = ""
            return
        if not path:
            return
        path = path.strip().strip('"')
        if not os.path.isdir(path):
            say(f"There's no folder called {path}.")
            continue
        index = RomIndex(path)
        files = list(index._files())
        if not files:
            say(f"No game files ({', '.join(EXTENSIONS)}) in {path}.")
            if not yes("Use it anyway?", False):
                continue
        else:
            say(f"Found {len(files)} game file{'s' if len(files) != 1 else ''}.")
        cfg.ra_roms = path
        return


# -- 5. sets -----------------------------------------------------------------

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
            say("Another DSiRPC tool is using the DSi's network port, so setup can't listen "
                "for it. Close that tool and try again.")
            return None
        if time.time() - state.get("time", 0) < 90 and state.get("online") and state.get("game"):
            return state["game"], state.get("header_title") or "", "DSiRPC (running in the tray)"
        say("DSiRPC is running in the tray, but it doesn't see a game right now.")
        return None
    try:
        say(f"Listening for the DSi for {wait:.0f} seconds... (if the game isn't running "
            "yet, start it now)")
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


class _SetPicker:
    """Offers sets for a game code, from RetroAchievements (signed in) and
    RALibretro's cache, and saves the one picked to ra/<code>.json."""

    def __init__(self, cfg, cache_sets):
        self.cfg = cfg
        self.cache_sets = cache_sets
        self.link = None
        if cfg.ra_signed_in:
            from core.ra_link import RALink
            self.link = RALink(cfg.ra_username, cfg.ra_token, cfg.ra_roms or None)

    def close(self):
        if self.link:
            self.link.stop()

    def _rom_choice(self, code):
        """(label, action) for the game file with this code, if there's one RA knows."""
        if not (self.link and self.cfg.ra_roms):
            return None
        from core.ra_api import RAError
        found = self.link._rom_hash(code)
        if not found:
            return None
        try:
            game_id = self.link.api.game_id_for_hash(found)
        except RAError as e:
            say(f"(Couldn't ask RetroAchievements about your {code} file: {e})")
            return None
        if not game_id:
            say(f"(RetroAchievements doesn't know your {code} file: a version it doesn't support?)")
            return None
        return (f"the one for your game file (RetroAchievements game {game_id})",
                lambda: self.link.download(game_id, found, code))

    def _ra_choices(self, header_title, query=None):
        from core import ra_cache
        from core.ra_api import RAError
        if not self.link:
            return []
        try:
            if query:
                q = ra_cache.normalize(query)
                games = []
                for console in (18, 78):
                    games += [g for g in self.link._title_list(console) if q in ra_cache.normalize(g.get("Title"))]
                games.sort(key=lambda g: g.get("Title", "").lower())
                found = [(g["ID"], g.get("Title", ""), g.get("NumAchievements", 0)) for g in games[:15]]
            elif header_title:
                ranked, _ = self.link.candidates(header_title)
                found = [(g.id, g.title, g.achievements) for _, g in ranked[:10]]
            else:
                found = []
        except RAError as e:
            say(f"(Couldn't get RetroAchievements' list of games: {e})")
            return []
        return [(f"{title} (RetroAchievements game {gid}, {n} achievement{'s' if n != 1 else ''})",
                 lambda gid=gid: self.link.download(gid, None, self.code))
                for gid, title, n in found]

    def _cache_choices(self, header_title, show_all=False):
        from core import ra_cache
        if not self.cache_sets:
            return []
        if header_title and not show_all:
            sets = [s for _, s in ra_cache.candidates(header_title, self.cache_sets)]
        else:
            sets = list(self.cache_sets)
        return [(f"{s.title} (from RALibretro's cache, RA game {s.id})",
                 lambda s=s: self._import(s)) for s in sets]

    def _import(self, s):
        from core import ra_cache, ra_set
        dest = ra_cache.import_set(s, self.code, force=True)
        return ra_set.load(dest)

    def pick(self, code, header_title=""):
        self.code = code
        choices = []
        rom = self._rom_choice(code)
        if rom:
            choices.append(rom)
        choices += self._ra_choices(header_title)
        choices += self._cache_choices(header_title)
        while True:
            if choices:
                say("Which set is it?")
                for i, (label, _) in enumerate(choices, 1):
                    print(f"    {i:>2}) {label}")
            else:
                say("No set's title matches this game.")
            how = ["Type a number to pick that set"] if choices else []
            if self.link:
                how.append("type part of the game's name to search RetroAchievements")
            if self.cache_sets:
                how.append("type 'all' to see every set in RALibretro's cache")
            if not how:
                return
            text = ", or ".join(how)
            say(text[0].upper() + text[1:] + ".")
            answer = ask("Your choice (Enter to skip this game)")
            if not answer:
                return
            if answer.isdigit() and choices and 1 <= int(answer) <= len(choices):
                from core.ra_api import RAError
                try:
                    s = choices[int(answer) - 1][1]()
                except (RAError, OSError) as e:
                    say(f"That didn't work: {e}")
                    continue
                n = len(s.playable_achievements)
                say(f"Saved \"{s.title}\" for {code} (ra/{code}.json, {n} achievement{'s' if n != 1 else ''}).")
                return
            if answer.lower() == "all" and self.cache_sets:
                choices = self._cache_choices(header_title, show_all=True)
            elif self.link and not answer.isdigit():
                choices = self._ra_choices(None, query=answer)
                if not choices:
                    say(f"RetroAchievements has no DS or DSi game with \"{answer}\" in its name.")
            else:
                say("Pick one of the numbers.")


def step_sets(cfg):
    from core import games, ra_cache
    heading(5, "Achievement sets")
    say("Each game's achievements and rich presence come in a \"set\" from RetroAchievements.")
    if cfg.ra_signed_in:
        say("Signed in, DSiRPC downloads a game's set by itself whenever it can tell which game "
            "it is. Here you can pick the set for a game it can't tell, or get one ahead of time.")
    else:
        say("Without a RetroAchievements account, DSiRPC can copy sets from RALibretro, which "
            "keeps the set of every game you've played in it (in its RACache folder).")
    while True:
        path = ask("RALibretro's folder (Enter to skip, - to forget it)", cfg.racache)
        if path == "-":
            cfg.racache = ""
            break
        if not path or ra_cache.data_dir(path):
            cfg.racache = (path or "").strip().strip('"')
            break
        say(f"There are no saved sets in {path} (it should have an RACache folder).")
    cache_sets = ra_cache.scan(cfg.racache) if cfg.racache else []
    if cfg.racache:
        say(f"RALibretro's cache has {len(cache_sets)} DS/DSi set{'s' if len(cache_sets) != 1 else ''}.")
        cfg.ra_auto_import = yes("When a game has no set yet, copy it from there by itself "
                                 "(only when exactly one clearly matches)?", cfg.ra_auto_import)
    if not cfg.ra_signed_in and not cache_sets:
        say("There are no sets to pick from, so that's it for now. (A set file can also be added "
            "by hand: python tools\\ra_tool.py add <file> --code <game code>)")
        return
    try:
        cfg.save()  # so a DSiRPC running in the tray picks the account and folders up now
    except OSError:
        pass
    picker = _SetPicker(cfg, cache_sets)
    try:
        have = _sets_in_ra()
        say()
        if yes("Is a game running on the DSi right now? Look up its set?"):
            found = detect_game()
            if not found:
                say("The DSi didn't answer. (Is the game running after the launcher's handoff?)")
            else:
                game, header_title, how = found
                code = game["code"]
                say(f"{how} says it's running {games.name(game)}"
                    + (f", whose title is \"{header_title}\"" if header_title else "") + ".")
                if code in have and not yes(f"It already has a set (RetroAchievements game "
                                            f"{have[code]}). Pick a different one?", False):
                    pass
                else:
                    picker.pick(code, header_title)
        say()
        say("You can also pick a set for any other game by its game code: 4 letters or digits, "
            "like AMCE in \"NTR-AMCE-USA\" on Mario Kart DS's cartridge label (DSiRPC's log "
            "shows it too while the game runs).")
        while True:
            code = ask("Game code (Enter when you're done)").upper()
            if not code:
                return
            if not re.fullmatch(r"[A-Z0-9]{4}", code):
                say("A game code is 4 letters or digits, like AMCE.")
                continue
            picker.pick(code)
    finally:
        picker.close()


# -- 6. startup --------------------------------------------------------------

def step_startup():
    from . import startup
    heading(6, "Start with Windows")
    if not startup.supported():
        say("Only on Windows; skipped.")
        return
    say("DSiRPC can start in the tray (by the clock) whenever you sign in to Windows, so it's "
        "always ready when you play.")
    on = startup.is_enabled()
    want = yes("Start DSiRPC with Windows?", on)
    if want != on or (want and startup.current() != startup.command()):
        try:
            startup.set_enabled(want)
            say("Done: it'll start with Windows." if want else "Done: it won't start with Windows.")
        except OSError as e:
            say(f"Couldn't change it: {e}")


def run_setup():
    sys.path.insert(0, ROOT)
    from utils.config import Config, OLD_CONFIG_NAME
    print("DSiRPC setup")
    print("============")
    say("This gets DSiRPC ready on this PC. For each question, the answer in [brackets] is what's "
        "saved now: press Enter to keep it. Run Setup.bat again any time to change an answer.")
    step_packages()
    cfg = Config()
    migrated = cfg.loaded_from and os.path.basename(cfg.loaded_from) == OLD_CONFIG_NAME
    step_discord(cfg)
    step_ra(cfg)
    step_roms(cfg)
    step_sets(cfg)
    step_startup()
    try:
        cfg.save()
        print()
        say("All saved, in:")
        print(f"    {cfg.path}")
        if migrated:
            say(f"(Your settings from {OLD_CONFIG_NAME} are in it now; the old file isn't used anymore.)")
    except OSError as e:
        print()
        say(f"Couldn't save {cfg.path}: {e}")
        return 1
    say()
    say("You're all set! Double-click DSiRPC.bat to start DSiRPC: it sits in the tray, by the "
        "clock (right-click its icon for the menu). If it never finds the DSi, allow Python "
        "through the Windows firewall for private networks.")
    if sys.stdin and sys.stdin.isatty():
        ask("Press Enter to close")
    return 0
