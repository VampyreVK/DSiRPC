import configparser
import os
import logging

class Config:
    def __init__(self, config_file="PokemonPlatinumRPC.cfg"):
        self.config_file = config_file
        self.host_url = "127.0.0.1"
        self.port = 8090
        self.discord_client_id = ""

        self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            logging.warning(f"Config file {self.config_file} not found. Using defaults.")
            return

        parser = configparser.ConfigParser()
        parser.read(self.config_file)

        if "connection" in parser:
            host_raw = parser["connection"].get("host_url", "http://127.0.0.1").strip("'\" ")
            host = host_raw.replace("http://", "").replace("https://", "")
            if ":" in host:
                self.host_url, port_str = host.split(":")
                self.port = int(port_str)
            else:
                self.host_url = host
            self.discord_client_id = parser["connection"].get("discord_client_id", "").strip("'\" ")
