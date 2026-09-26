"""
app.py - the overlay window. Run it with dsirpc_overlay.py from the repo root.

It owns the state hub (so it's the one process talking to the DSi), draws the
256x192 canvas every frame and scales it up by a whole number, so the pixels
stay crisp for window capture in OBS or a Discord screen share. With
--discord it also runs the Rich Presence, since dsirpc.py can't run at the
same time (both need UDP port 4244).

Keys: N next demo scene, V switch view (auto / party / battle),
      1-6 window scale.
"""

import argparse
import logging
import os
import queue
import signal
import sys

import pygame

from core.charmap import parse_charmap_txt
from core.hub import DsiSource, FileSource, StateHub
from core.demo import DemoSource
from .scenes import Overlay, W, H
from .sprites import SpriteBank
from . import ui

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _color(text):
    text = text.lstrip('#')
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser(description="DSiRPC overlay window (pixel-art party and battle view)")
    ap.add_argument("--demo", action="store_true", help="play made-up scenes instead of reading the DSi")
    ap.add_argument("--file", help="use a 4 MB RAM dump instead of the DSi (with --demo: start the demo from it)")
    ap.add_argument("--name", help="with --demo: the trainer name to show")
    ap.add_argument("--dsi-ip", help="the IP the launcher shows; skips waiting for a hello packet")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (the DSi always uses 4244)")
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between reads of the DSi")
    ap.add_argument("--scale", type=int, default=3, help="window size as a multiple of 256x192")
    ap.add_argument("--chroma", metavar="RRGGBB", help="fill the background with this colour, for a chroma key in OBS")
    ap.add_argument("--discord", action="store_true", help="also run the Discord Rich Presence")
    ap.add_argument("--client-id", help="Discord application ID (default: discord_client_id in PokemonPlatinumRPC.cfg)")
    ap.add_argument("--fps", type=int, default=60)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    charmap = parse_charmap_txt(os.path.join(HERE, "PokeGen4Charmap.txt"))
    if args.chroma:
        ui.THEME['chroma'] = _color(args.chroma)

    if args.demo:
        base = FileSource(charmap, args.file).state if args.file else None
        source, interval = DemoSource(base, name=args.name), 0.5
    elif args.file:
        source, interval = FileSource(charmap, args.file), 1.0
    else:
        source, interval = DsiSource(charmap, port=args.port, dsi_ip=args.dsi_ip), args.interval
    hub = StateHub(source, interval=interval)

    events = queue.Queue()
    hub.add_listener(lambda snap, evs: [events.put(e) for e in evs])

    if args.discord:
        from rpc.presence_connector import DiscordConnector
        from utils.config import Config
        client_id = args.client_id or Config(os.path.join(HERE, "PokemonPlatinumRPC.cfg")).discord_client_id
        if not client_id:
            print("No Discord application ID: pass --client-id or set discord_client_id in PokemonPlatinumRPC.cfg")
            sys.exit(1)
        connector = DiscordConnector(client_id)
        hub.add_listener(connector.on_update)
        hub.add_closer(connector.close)

    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)

    pygame.init()
    scale = max(1, args.scale)
    window = pygame.display.set_mode((W * scale, H * scale))
    pygame.display.set_caption("DSiRPC")
    canvas = pygame.Surface((W, H)).convert()
    overlay = Overlay(SpriteBank(os.path.join(HERE, "Assets")))

    hub.start()
    clock = pygame.time.Clock()
    dt = 0
    try:
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_n and hasattr(source, 'next_scene'):
                        source.next_scene()
                    elif e.key == pygame.K_v:
                        overlay.view = {'auto': 'party', 'party': 'battle', 'battle': 'auto'}[overlay.view]
                        pygame.display.set_caption(f"DSiRPC ({overlay.view})")
                    elif pygame.K_1 <= e.key <= pygame.K_6:
                        scale = e.key - pygame.K_0
                        window = pygame.display.set_mode((W * scale, H * scale))

            t_ms = pygame.time.get_ticks()
            evs = []
            while not events.empty():
                evs.append(events.get_nowait())
            overlay.handle_events(evs, t_ms)
            overlay.draw(canvas, hub.snapshot(), t_ms, dt)
            pygame.transform.scale(canvas, window.get_size(), window)
            pygame.display.flip()
            dt = clock.tick(args.fps)
    except KeyboardInterrupt:
        pass
    finally:
        hub.stop()
        pygame.quit()
