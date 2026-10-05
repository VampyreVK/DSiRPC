from pypresence import Presence
import logging
import sys

class DiscordRPC:
    def __init__(self, client_id):
        self.client_id = client_id
        self.rpc = None
        self.connected = False
        self._last_error = None  # the same error over and over is only logged once

    def _log_error(self, msg):
        if msg != self._last_error:
            logging.error(msg)
            self._last_error = msg

    def connect(self):
        if not self.client_id:
            logging.warning("Discord client ID missing. Skipping RPC connect.")
            return False

        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            self._last_error = None
            logging.info("Connected to Discord RPC.")
            return True
        except Exception as e:
            self._log_error(f"Failed to connect to Discord RPC (is Discord running?): {e}")
            self._drop()
            return False

    def update(self, state=None, details=None, large_image=None, large_text=None, small_image=None, small_text=None, start=None,
               activity_type=None, party_size=None, name=None):
        """Returns True if Discord accepted the update. `name` replaces the
        application's name in "Playing ..." (pypresence 4.6 and later; older
        versions leave it out)."""
        if not self.connected:
            return False

        args = dict(
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
        if name:
            args['name'] = name
        try:
            try:
                self.rpc.update(**args)
            except TypeError:
                if 'name' not in args:
                    raise
                del args['name']  # pypresence older than 4.6
                self.rpc.update(**args)
            return True
        except Exception as e:
            self._log_error(f"Error updating Discord RPC: {e}")
            self._drop()
            return False

    def close(self):
        """Clears the activity and disconnects, so Discord shows nothing."""
        if self.rpc is None:
            return
        was_connected = self.connected
        if was_connected:
            try:
                self.rpc.clear()
            except Exception:
                pass
            try:
                self.rpc.close()
                self.rpc = None
            except Exception:
                pass
        self._drop()
        if was_connected:
            logging.info("Disconnected from Discord RPC.")

    def _drop(self):
        """Forgets the connection, closing whatever pypresence left open (for
        example after Discord was closed), so the next connect() starts clean."""
        if self.rpc is not None:
            try:
                self.rpc.loop.close()
                if sys.platform == "win32" and getattr(self.rpc, "sock_writer", None) is not None:
                    self.rpc.sock_writer._call_connection_lost(None)
            except Exception:
                pass
        self.rpc = None
        self.connected = False
