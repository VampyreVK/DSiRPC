import configparser
import os
import logging

class Config:
    """Reads PokemonPlatinumRPC.cfg (see PokemonPlatinumRPC.cfg.sample)."""

    def __init__(self, config_file="PokemonPlatinumRPC.cfg"):
        self.config_file = config_file
        self.discord_client_id = ""

        self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            logging.warning(f"Config file {self.config_file} not found. Using defaults.")
            return

        parser = configparser.ConfigParser()
        parser.read(self.config_file)

        if "connection" in parser:
            self.discord_client_id = parser["connection"].get("discord_client_id", "").strip("'\" ")
