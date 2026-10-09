"""
presence_connector.py - the Discord Rich Presence, as a state hub listener
(core/hub.py). dsirpc.py runs it for every game:

  Pokemon Platinum   rpc/platinum_presence.py (party, battles, sprites)
  Black and White    rpc/bw_presence.py (the same on Unova's turfs, plus
                     the Battle Subway, Battle Institute and League)
  any other game     rpc/generic_presence.py (name, box art, and its
                     RetroAchievements rich presence if there's a set)

Discord is only connected while the game answers, updates are only sent when
the presence changes (and at most about every 5 s, Discord's limit), and the
presence is cleared when the DSi goes quiet, when it's switched off here
(enabled = False) and when the program stops. Each game can have its own
Discord application (client_id_for). Everything runs on the hub thread,
including close() (register it with StateHub.add_closer), because
pypresence's event loop belongs to the thread that created it.
"""

import logging
import time

from core.hub import is_bw, is_other
from rpc import bw_presence as bw
from rpc import generic_presence as generic
from rpc import platinum_presence as platinum

MIN_GAP_S = 4.75   # Discord takes about one update per 5 s; reads are ~5 s apart


class DiscordConnector:
    def __init__(self, client_id_for, dry_run=False, enabled=True, check_images=True):
        """client_id_for(game code, platinum) -> the Discord application ID
        to use (utils/config.Config.client_id_for)."""
        self.client_id_for = client_id_for
        self.dry_run = dry_run
        self.enabled = enabled
        self.check_images = check_images
        self.console = None   # (name, image URL): the small image for games without their own presence
        self.rpc = None
        self.start = None
        self.start_key = None
        self.last_sent = None
        self.last_time = 0.0
        self.status = "off" if not enabled else "waiting for the game"
        self._warned_no_id = False

    def _clear(self, why=None):
        if self.last_sent is not None and why:
            logging.info(f"{why}, presence cleared")
        if self.rpc:
            self.rpc.close()
            self.rpc = None
        self.last_sent, self.start, self.start_key = None, None, None

    def _presence(self, state):
        """(presence, game code, is Platinum) for a state."""
        if is_bw(state):
            playtime_start = bw.playtime_start(state)
            key = ('bw', state.get('version'))
            if self.start_key != key or abs(playtime_start - self.start) > 60:
                self.start, self.start_key = playtime_start, key
            presence = bw.build_presence(state)
            presence['start'] = self.start
            return presence, bw.game_code(state), False
        if is_other(state):
            started = state.get('started')
            presence = generic.from_state(state, check_images=self.check_images, console=self.console)
            key = ('other', (state.get('game') or {}).get('code'), started)
            if self.start_key != key:
                self.start, self.start_key = int(started or time.time()), key
            presence['start'] = self.start
            return presence, (state.get('game') or {}).get('code'), False
        playtime_start = platinum.playtime_start(state)
        # Set once so the timer doesn't jitter. A jump of more than a minute
        # means the game was reset or another save was loaded.
        if self.start_key != 'platinum' or abs(playtime_start - self.start) > 60:
            self.start, self.start_key = playtime_start, 'platinum'
        presence = platinum.build_presence(state)
        presence['start'] = self.start
        return presence, 'CPUE', True

    def on_update(self, snap, events):
        if not self.enabled:
            if self.rpc or self.last_sent is not None:
                self._clear()
            self.status = "off"
            return
        if not snap.online or not snap.state:
            self._clear("No data from the DSi")
            self.status = "waiting for the game"
            return

        presence, code, is_platinum = self._presence(snap.state)
        client_id = self.client_id_for(code, is_platinum)
        if not client_id and not self.dry_run:
            if not self._warned_no_id:
                logging.warning("No Discord application ID set: run 'dsirpc.py setup' (or pass --client-id)")
                self._warned_no_id = True
            self.status = "no Discord application ID (run setup)"
            return
        self._warned_no_id = False

        # Each game can have its own Discord application (its name is what
        # Discord shows after "Playing" if it doesn't take the game's name).
        if not self.dry_run and (self.rpc is None or self.rpc.client_id != client_id):
            from rpc.discord_client import DiscordRPC
            self._clear()
            self.rpc = DiscordRPC(client_id)  # connects only once there's something to show
        if presence == self.last_sent or time.time() - self.last_time < MIN_GAP_S:
            return
        sent = True
        if self.rpc:
            sent = (self.rpc.connected or self.rpc.connect()) and self.rpc.update(**presence)
        if sent:
            self.last_sent, self.last_time = presence, time.time()
            label = "would show" if self.dry_run else "showing"
            self.status = f"{label} {presence.get('name') or 'Pokemon Platinum'}"
            logging.info(f"Discord: {generic.shown(presence)}")
        else:
            self.status = "can't reach Discord (is it running?)"

    def set_enabled(self, on):
        """Takes effect at the next hub update (on the hub thread)."""
        self.enabled = bool(on)
        if self.enabled and self.status == "off":
            self.status = "waiting for the game"

    def close(self):
        self._clear()
