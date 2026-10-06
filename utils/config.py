"""
config.py - DSiRPC's settings, in dsirpc.cfg at the repo root (gitignored;
see dsirpc.cfg.sample). 'dsirpc.py setup' writes it. Keep the file to
yourself: with RetroAchievements signed in, it holds your login token.

An older PokemonPlatinumRPC.cfg is still read when there's no dsirpc.cfg, and
its settings move to dsirpc.cfg the first time anything is saved.

A release download can also have a defaults.cfg next to it (written by
packaging/build_release.py): the Discord applications it comes with, used
until dsirpc.cfg names others. It's replaced with each release, so its values
aren't copied into dsirpc.cfg.
"""

import configparser
import logging
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_NAME = "dsirpc.cfg"
OLD_CONFIG_NAME = "PokemonPlatinumRPC.cfg"
DEFAULTS_NAME = "defaults.cfg"


def _bool(text, default):
    text = (text or "").strip().lower()
    if text in ("1", "yes", "true", "on"):
        return True
    if text in ("0", "no", "false", "off"):
        return False
    return default


def _clean(text):
    return (text or "").strip().strip("'\" ")


class Config:
    def __init__(self, config_file=None):
        """config_file: a specific file to read (and save to); default
        dsirpc.cfg, or PokemonPlatinumRPC.cfg if only that exists."""
        if config_file:
            self.path = config_file
            self.loaded_from = config_file if os.path.exists(config_file) else None
        else:
            self.path = os.path.join(ROOT, CONFIG_NAME)
            old = os.path.join(ROOT, OLD_CONFIG_NAME)
            if os.path.exists(self.path):
                self.loaded_from = self.path
            elif os.path.exists(old):
                self.loaded_from = old
            else:
                self.loaded_from = None
        self.config_file = self.loaded_from or self.path

        # [connection]: the Discord application for Pokemon Platinum (and the
        # fallback for every other game)
        self.discord_client_id = ""
        # [discord_apps]: Discord application IDs for other games, by game
        # code, plus "default" for any game without its own.
        self.discord_apps = {}
        # [app]: what's on when DSiRPC starts (the tray menu saves these)
        self.discord = True
        self.overlay = False
        self.overlay_scale = 3
        self.chroma = ""
        # The picture in Assets/Consoles shown as Discord's small image for
        # games without their own presence ('' for none)
        self.console_icon = "DSiXL"
        # [ra]: an RA emulator's folder (or its RACache), to find set files in
        self.racache = ""
        self.ra_auto_import = True
        # RetroAchievements account: the token from signing in (never the password)
        self.ra_username = ""
        self.ra_token = ""
        # A folder of your game files (.nds), to tell RetroAchievements
        # exactly which game and version you play
        self.ra_roms = ""
        self.ra_profile = True         # what you play shows on your RA profile
        self.ra_achievements = True    # check achievements
        self.ra_submit = False         # send unlocks to RetroAchievements (softcore)
        self.ra_interval = 1.0         # seconds between achievement checks

        # The Discord applications a release comes with (defaults.cfg), if any
        self.release_client_id = ""
        self.release_default_app = ""
        self._load_defaults()
        self._load_config()

    def client_id_for(self, game_code, platinum=False):
        """The Discord application to use for a game: its own from
        [discord_apps], else (for games other than Platinum) the [discord_apps]
        default, else discord_client_id."""
        code = (game_code or "").upper()
        if code in self.discord_apps:
            return self.discord_apps[code]
        if not platinum and self.discord_apps.get("DEFAULT"):
            return self.discord_apps["DEFAULT"]
        return self.discord_client_id

    @property
    def has_discord_id(self):
        return bool(self.discord_client_id or any(self.discord_apps.values()))

    def _load_defaults(self):
        path = os.path.join(ROOT, DEFAULTS_NAME)
        if not os.path.exists(path):
            return
        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError) as e:
            logging.warning(f"Can't read {path}: {e}")
            return
        if "connection" in parser:
            self.release_client_id = _clean(parser["connection"].get("discord_client_id", ""))
        if "discord_apps" in parser:
            self.release_default_app = _clean(parser["discord_apps"].get("default", ""))
        self.discord_client_id = self.release_client_id
        if self.release_default_app:
            self.discord_apps["DEFAULT"] = self.release_default_app

    def _load_config(self):
        if not self.loaded_from:
            logging.debug(f"No {CONFIG_NAME} yet, using defaults (run 'dsirpc.py setup')")
            return

        parser = configparser.ConfigParser()
        try:
            parser.read(self.loaded_from, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError) as e:
            logging.warning(f"Can't read {self.loaded_from}: {e}; using defaults")
            return

        if "connection" in parser:
            # Empty means "the default" (defaults.cfg's, or none)
            self.discord_client_id = _clean(parser["connection"].get("discord_client_id", "")) or \
                self.discord_client_id
        if "discord_apps" in parser:
            for key, value in parser["discord_apps"].items():
                value = _clean(value)
                if value:
                    self.discord_apps[key.upper()] = value
        if "app" in parser:
            a = parser["app"]
            self.discord = _bool(a.get("discord"), self.discord)
            self.overlay = _bool(a.get("overlay"), self.overlay)
            try:
                self.overlay_scale = max(1, min(6, int(_clean(a.get("overlay_scale", "")) or self.overlay_scale)))
            except ValueError:
                pass
            self.chroma = _clean(a.get("chroma", ""))
            if "console_icon" in a:
                self.console_icon = _clean(a.get("console_icon", ""))
        if "ra" in parser:
            r = parser["ra"]
            self.racache = _clean(r.get("racache", ""))
            self.ra_auto_import = _bool(r.get("auto_import"), self.ra_auto_import)
            self.ra_username = _clean(r.get("username", ""))
            self.ra_token = _clean(r.get("token", ""))
            self.ra_roms = _clean(r.get("roms", ""))
            self.ra_profile = _bool(r.get("profile"), self.ra_profile)
            self.ra_achievements = _bool(r.get("achievements"), self.ra_achievements)
            self.ra_submit = _bool(r.get("submit_unlocks"), self.ra_submit)
            try:
                self.ra_interval = max(0.25, min(10.0, float(_clean(r.get("interval", "")) or self.ra_interval)))
            except ValueError:
                pass

    @property
    def ra_signed_in(self):
        return bool(self.ra_username and self.ra_token)

    def save(self):
        """Writes every setting to self.path (dsirpc.cfg), with comments."""
        def yn(v):
            return "yes" if v else "no"
        apps = "".join(f"{code}: {cid}\n" for code, cid in sorted(self.discord_apps.items())
                       if code != "DEFAULT")
        # The release's own applications stay in defaults.cfg, so a newer
        # release can change them
        client_id = "" if self.discord_client_id == self.release_client_id else self.discord_client_id
        default_app = self.discord_apps.get("DEFAULT", "")
        if default_app == self.release_default_app:
            default_app = ""
        text = f"""# DSiRPC settings ('dsirpc.py setup' writes this file; see dsirpc.cfg.sample).
# Keep it to yourself: when you're signed in to RetroAchievements, it holds
# your login token.

[connection]
# The Discord application for Pokemon Platinum, and for any game without its
# own below. Its name is what Discord shows after "Playing". Empty: the one
# this download came with (defaults.cfg), if any.
discord_client_id: {client_id}

# Discord applications for other games, by game code (e.g. AMCE: 1234...).
# "default" is for every game without its own. DSiRPC also sends the game's
# name, which Discord shows instead of the application's where it can.
[discord_apps]
default: {default_app}
{apps}
[app]
# What's on when DSiRPC starts (the tray menu changes these)
discord: {yn(self.discord)}
overlay: {yn(self.overlay)}
# Overlay window size as a multiple of 256x192, and an optional chroma key
# colour (RRGGBB) for its background
overlay_scale: {self.overlay_scale}
chroma: {self.chroma}
# The picture from Assets/Consoles that Discord shows as the small image for
# games without their own presence (file name without the extension; empty
# for none). The tray menu's "Console icon" changes it.
console_icon: {self.console_icon}

[ra]
# Your RetroAchievements account. Setup signs in with your password once and
# keeps only the token RetroAchievements gives back.
username: {self.ra_username}
token: {self.ra_token}
# A folder with your game files (.nds), e.g. RALibretro's games folder: the
# file with the same game code tells RetroAchievements exactly which game
# and version you play. Optional.
roms: {self.ra_roms}
# Show what you play (and its rich presence) on your RetroAchievements profile
profile: {yn(self.ra_profile)}
# Check achievements while you play, and say when one unlocks
achievements: {yn(self.ra_achievements)}
# Send unlocks to RetroAchievements (always softcore). Off: they only show here.
submit_unlocks: {yn(self.ra_submit)}
# Seconds between achievement checks
interval: {self.ra_interval:g}
# An RA emulator's folder (e.g. RALibretro's), or its RACache folder. When a
# game has no set file in ra/ (and RetroAchievements can't send one), DSiRPC
# looks for its set there and copies it into ra/ if exactly one clearly
# matches (auto_import).
racache: {self.racache}
auto_import: {yn(self.ra_auto_import)}
"""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        os.replace(tmp, self.path)
        self.loaded_from = self.config_file = self.path
