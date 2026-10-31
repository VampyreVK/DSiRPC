"""
config.py - DSiRPC's settings, in dsirpc.cfg at the repo root (gitignored;
see dsirpc.cfg.sample). 'dsirpc.py setup' writes it. Keep the file to
yourself: with RetroAchievements signed in, it holds your login token.

An older PokemonPlatinumRPC.cfg is still read when there's no dsirpc.cfg, and
its settings move to dsirpc.cfg the first time anything is saved.

A release download can also have a defaults.cfg next to it (written by
packaging/build_release.py): the Discord application it comes with, used
until dsirpc.cfg names another. It's replaced with each release, so its value
isn't copied into dsirpc.cfg.

There's one Discord application for every game: DSiRPC sends each game's
name, which Discord shows after "Playing". Files from when Platinum and the
other games each had one ([discord_apps]) still load: their Platinum
application is the one, or, without it, their other games' default.
"""

import configparser
import logging
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Where dsirpc.cfg is: the DSiRPC folder, or the macOS app's data folder (core/paths.py)
from core.paths import DATA  # noqa: E402
CONFIG_NAME = "dsirpc.cfg"
OLD_CONFIG_NAME = "PokemonPlatinumRPC.cfg"
DEFAULTS_NAME = "defaults.cfg"
# The overlay window's ambient music: the launcher's menu songs (overlay/music.py)
MUSIC_CHOICES = ("off", "bright", "subtle")


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
            self.path = os.path.join(DATA, CONFIG_NAME)
            old = os.path.join(DATA, OLD_CONFIG_NAME)
            if os.path.exists(self.path):
                self.loaded_from = self.path
            elif os.path.exists(old):
                self.loaded_from = old
            else:
                self.loaded_from = None
        self.config_file = self.loaded_from or self.path

        # [connection]: the Discord application DSiRPC shows every game through
        self.discord_client_id = ""
        # [app]: what's on when DSiRPC starts (the tray menu saves these)
        self.discord = True
        self.overlay = False
        self.overlay_scale = 3
        self.chroma = ""
        # The picture in Assets/Consoles shown as Discord's small image for
        # games without their own presence ('' for none)
        self.console_icon = "DSiXL"
        # Offer the launcher the console's files that came with this DSiRPC
        # when its own differ (core/console_update.py)
        self.console_updates = True
        # The launcher's menu song the overlay window plays while it's open
        # (MUSIC_CHOICES); off at first, as the window may be on a stream
        self.ambient_music = "off"
        # Look for a new DSiRPC release when it starts and once a day, and
        # say so (app/updates.py; the tray menu's "Check for updates..."
        # looks whatever this says)
        self.check_updates = True
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
        # [saves]: the launcher's save sync: where the PC keeps the console's
        # saves ('' for saves/ in DSiRPC's folder) and how many older
        # versions of each it keeps
        self.saves_folder = ""
        self.save_versions = 10

        # The Discord application a release comes with (defaults.cfg), if any
        self.release_client_id = ""
        self._load_defaults()
        self._load_config()

    @property
    def has_discord_id(self):
        return bool(self.discord_client_id)

    @staticmethod
    def _client_id(parser):
        """A file's Discord application: [connection]'s, or (a file from when
        other games had their own) [discord_apps]'s default."""
        if "connection" in parser:
            found = _clean(parser["connection"].get("discord_client_id", ""))
            if found:
                return found
        if "discord_apps" in parser:
            return _clean(parser["discord_apps"].get("default", ""))
        return ""

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
        self.release_client_id = self.discord_client_id = self._client_id(parser)

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

        # Empty means "the default" (defaults.cfg's, or none)
        self.discord_client_id = self._client_id(parser) or self.discord_client_id
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
            self.console_updates = _bool(a.get("console_updates"), self.console_updates)
            music = _clean(a.get("ambient_music", "")).lower()
            if music in MUSIC_CHOICES:
                self.ambient_music = music
            self.check_updates = _bool(a.get("check_updates"), self.check_updates)
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
        if "saves" in parser:
            v = parser["saves"]
            self.saves_folder = _clean(v.get("folder", ""))
            try:
                self.save_versions = max(1, min(999, int(_clean(v.get("versions", "")) or self.save_versions)))
            except ValueError:
                pass

    @property
    def saves_path(self):
        """Where the launcher's save sync keeps the console's saves."""
        return os.path.expanduser(self.saves_folder) if self.saves_folder else os.path.join(DATA, "saves")

    @property
    def ra_signed_in(self):
        return bool(self.ra_username and self.ra_token)

    def save(self):
        """Writes every setting to self.path (dsirpc.cfg), with comments."""
        def yn(v):
            return "yes" if v else "no"
        # The release's own application stays in defaults.cfg, so a newer
        # release can change it
        client_id = "" if self.discord_client_id == self.release_client_id else self.discord_client_id
        text = f"""# DSiRPC settings ('dsirpc.py setup' writes this file; see dsirpc.cfg.sample).
# Keep it to yourself: when you're signed in to RetroAchievements, it holds
# your login token.

[connection]
# The Discord application DSiRPC shows every game through. Discord shows the
# game's own name after "Playing" (the application's name only where it
# can't). Empty: the one this download came with (defaults.cfg), if any.
discord_client_id: {client_id}

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
# When the launcher's files on the SD card (the launcher and nds-bootstrap)
# differ from the ones that came with this DSiRPC, the launcher offers to
# update them from here (the tray menu's "Console updates")
console_updates: {yn(self.console_updates)}
# Music while the overlay window is open: the launcher's menu songs, off,
# bright or subtle (the tray menu's "Ambient music")
ambient_music: {self.ambient_music}
# Look for a new release of DSiRPC when it starts and once a day: the tray
# menu then offers it ("Update to ..."). Its "Check for updates..." looks
# whatever this says
check_updates: {yn(self.check_updates)}

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

[saves]
# The launcher's save sync (Y in the launcher): the folder the PC keeps the
# console's saves in (empty: saves/ in DSiRPC's folder; put it in a cloud
# drive's folder for an off-site copy too), and how many backups of each
# save it keeps for each console
folder: {self.saves_folder}
versions: {self.save_versions}
"""
        tmp = self.path + ".tmp"
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)   # the macOS app's data folder, the first time
        with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        os.replace(tmp, self.path)
        self.loaded_from = self.config_file = self.path
