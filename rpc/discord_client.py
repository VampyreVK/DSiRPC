from pypresence import Presence
import logging
import time

class DiscordRPC:
    def __init__(self, client_id):
        self.client_id = client_id
        self.rpc = None
        self.connected = False

    def connect(self):
        if not self.client_id:
            logging.warning("Discord client ID missing. Skipping RPC connect.")
            return False

        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            logging.info("Connected to Discord RPC.")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Discord RPC: {e}")
            self.connected = False
            return False

    def update(self, state=None, details=None, large_image=None, large_text=None, small_image=None, small_text=None, start=None,
               activity_type=None, party_size=None):
        if not self.connected:
            return
        
        try:
            self.rpc.update(
                state=state,
                details=details,
                large_image=large_image,
                large_text=large_text,
                small_image=small_image,
                small_text=small_text,
                start=start,
                activity_type=activity_type,  # pypresence.ActivityType, e.g. COMPETING for battles
                party_size=party_size         # [current, max]
            )
        except Exception as e:
            logging.error(f"Error updating Discord RPC: {e}")
            self.connected = False

    def close(self):
        if self.connected and self.rpc:
            self.rpc.close()
            self.connected = False
            logging.info("Disconnected from Discord RPC.")
