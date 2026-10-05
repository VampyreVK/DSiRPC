"""
config.py - DSiRPC's settings, in dsirpc.cfg at the repo root (gitignored;
see dsirpc.cfg.sample). 'dsirpc.py setup' writes it.

An older PokemonPlatinumRPC.cfg is still read when there's no dsirpc.cfg, and
its settings move to dsirpc.cfg the first time anything is saved.
"""

import configparser
import logging
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_NAME = "dsirpc.cfg"
OLD_CONFIG_NAME = "PokemonPlatinumRPC.cfg"


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
        # [ra]: an RA emulator's folder (or its RACache), to find set files in
        self.racache = ""
        self.ra_auto_import = True

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
            self.discord_client_id = _clean(parser["connection"].get("discord_client_id", ""))
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
        if "ra" in parser:
            self.racache = _clean(parser["ra"].get("racache", ""))
            self.ra_auto_import = _bool(parser["ra"].get("auto_import"), self.ra_auto_import)

    def save(self):
        """Writes every setting to self.path (dsirpc.cfg), with comments."""
        def yn(v):
            return "yes" if v else "no"
        apps = "".join(f"{code}: {cid}\n" for code, cid in sorted(self.discord_apps.items())
                       if code != "DEFAULT")
        text = f"""# DSiRPC settings ('dsirpc.py setup' writes this file; see dsirpc.cfg.sample)

[connection]
# The Discord application for Pokemon Platinum, and for any game without its
# own below. Its name is what Discord shows after "Playing".
discord_client_id: {self.discord_client_id}

# Discord applications for other games, by game code (e.g. AMCE: 1234...).
# "default" is for every game without its own. DSiRPC also sends the game's
# name, which Discord shows instead of the application's where it can.
[discord_apps]
default: {self.discord_apps.get("DEFAULT", "")}
{apps}
[app]
# What's on when DSiRPC starts (the tray menu changes these)
discord: {yn(self.discord)}
overlay: {yn(self.overlay)}
# Overlay window size as a multiple of 256x192, and an optional chroma key
# colour (RRGGBB) for its background
overlay_scale: {self.overlay_scale}
chroma: {self.chroma}

[ra]
# An RA emulator's folder (e.g. RALibretro's), or its RACache folder. When a
# game has no set file in ra/, DSiRPC looks for its set there and copies it
# into ra/ if exactly one clearly matches (auto_import).
racache: {self.racache}
auto_import: {yn(self.ra_auto_import)}
"""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        os.replace(tmp, self.path)
        self.loaded_from = self.config_file = self.path
