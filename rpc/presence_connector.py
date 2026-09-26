"""
presence_connector.py - the Discord Rich Presence as a state hub listener, for
programs that own the hub (like the overlay window) and so can't also run
dsirpc.py, which needs the same UDP port.

It follows dsirpc.py's rules: the presence text comes from dsirpc.build_presence(),
Discord is only connected while the game answers, updates are only sent when
the presence changes (and at most every 5 s), and the presence is cleared
when the DSi goes quiet or the program stops. Everything runs on the hub
thread, including close() (register it with StateHub.add_closer), because
pypresence's event loop belongs to the thread that created it.
"""

import time

import dsirpc
from pypresence import ActivityType
from rpc.discord_client import DiscordRPC

MIN_GAP_S = 5.0


class DiscordConnector:
    def __init__(self, client_id):
        self.rpc = DiscordRPC(client_id)
        self.start = None
        self.last_sent = None
        self.last_time = 0.0

    def on_update(self, snap, events):
        if not snap.online:
            if self.last_sent is not None:
                print(time.strftime("%H:%M:%S"), "No data from the DSi, presence cleared")
            self.rpc.close()
            self.last_sent, self.start = None, None
            return

        d = snap.state
        pt = d['playtime']
        playtime_start = int(time.time()) - (pt['hours'] * 3600 + pt['minutes'] * 60 + pt['seconds'])
        if self.start is None or abs(playtime_start - self.start) > 60:
            self.start = playtime_start
        presence = dsirpc.build_presence(d)
        presence['start'] = self.start
        if presence == self.last_sent or time.time() - self.last_time < MIN_GAP_S:
            return
        if (self.rpc.connected or self.rpc.connect()) and self.rpc.update(**presence):
            self.last_sent, self.last_time = presence, time.time()
            shown = {k: (v.name if isinstance(v, ActivityType) else v) for k, v in presence.items() if k != 'start'}
            print(time.strftime("%H:%M:%S"), shown)

    def close(self):
        self.rpc.close()
