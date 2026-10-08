"""
dsirpc.py - DSiRPC: Discord Rich Presence (and a stream overlay) for the game
running on a real, modded DSi.

The easy way, on Windows:
  Setup.bat          first-time setup (Python packages, Discord application,
                     RetroAchievements sets, start with Windows)
  DSiRPC.bat         starts DSiRPC in the tray, by the clock

The same from a console, from the repo root:
  python dsirpc.py setup                 # setup (run it again to change anything)
  python dsirpc.py tray                  # the tray icon
  python dsirpc.py                       # run here until Ctrl+C, logging what Discord shows
  python dsirpc.py --overlay             # ...with the overlay window (closing it stops DSiRPC)
  python dsirpc.py --dry-run             # read the DSi, but print instead of sending to Discord
  python dsirpc.py --overlay --no-discord --demo        # the overlay with made-up scenes
  python dsirpc.py --file ram_dump.bin --dry-run        # a RAM dump instead of the DSi
  python dsirpc.py --file dump.bin --game AMCE --dry-run   # a dump of another game

Debugging achievements (README.md's "Debugging options"; they combine):
  python dsirpc.py --dry-run             # send nothing; act as if nothing were unlocked
  python dsirpc.py --blank-ra            # act as if nothing were unlocked, still send unlocks
  python dsirpc.py --clear-ra            # wipe the console's waiting unlocks, resend its sets
  python dsirpc.py --blank-ra --clear-ra # start the console over with whole sets

Pokemon Platinum gets its own presence (rpc/platinum_presence.py): where you
are, your party, who you're battling, with sprites. Any other game gets its
name, box art and a picture of your console, plus its RetroAchievements rich
presence if there's a set for it (rpc/generic_presence.py).

RetroAchievements (core/ra_game.py, core/ra_link.py): every game's
achievements are checked while you play, and you're told when one unlocks.
Signed in (setup), DSiRPC also downloads each game's set, shows what you play
on your RA profile and, only if you chose that, sends your unlocks (always
softcore).

DSiRPC waits for the DSi, shows the presence only while the game answers, and
takes it down after about 30 s without data. Settings are in dsirpc.cfg
(written by setup), the log in logs/dsirpc.log. Turn off Vencord's CustomRPC
while it runs, or Discord shows two activities. Only one DSiRPC (or one of
the tools in tools/) can run at a time: they all need UDP port 4244.
"""

import argparse
import os
import signal
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def _quiet_streams():
    """pythonw (the tray) has no console: give stray prints somewhere to go."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog="dsirpc.py",
        description="DSiRPC: Discord Rich Presence and a stream overlay from a real DSi",
        epilog="Settings are in dsirpc.cfg ('dsirpc.py setup' writes it).")
    ap.add_argument("mode", nargs="?", choices=["run", "tray", "setup"], default="run",
                    help="run here (default), as a tray icon, or first-time setup")
    ap.add_argument("--overlay", action="store_true", help="also open the overlay window (run mode)")
    ap.add_argument("--no-discord", action="store_true", help="don't show anything on Discord")
    ap.add_argument("--no-ra", action="store_true",
                    help="no RetroAchievements: no achievements, no downloads, nothing sent")
    ap.add_argument("--dry-run", action="store_true",
                    help="log the presence instead of sending it to Discord, send nothing to RetroAchievements, "
                         "act as if nothing were unlocked (like --blank-ra) and leave the console's unlocks on it")
    ap.add_argument("--blank-ra", action="store_true",
                    help="act as if your RetroAchievements account had nothing unlocked: every achievement is "
                         "checked, the console gets whole sets, and unlocks are still sent")
    ap.add_argument("--clear-ra", action="store_true",
                    help="at the console's first sync, throw away the unlocks waiting on it (nothing sent) "
                         "and send it every set again")
    ap.add_argument("--client-id", help="Discord application ID for every game (instead of dsirpc.cfg's)")
    ap.add_argument("--file", help="use a 4 MB RAM dump (e.g. from melonDS) instead of the DSi")
    ap.add_argument("--game", metavar="CODE", help="with --file: the dump's game code, if it isn't Platinum (e.g. AMCE)")
    ap.add_argument("--demo", action="store_true", help="made-up Platinum scenes instead of the DSi (implies --no-discord)")
    ap.add_argument("--name", help="with --demo: the trainer name to show")
    ap.add_argument("--dsi-ip", help="the IP the launcher shows; skips waiting for a hello packet")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (the DSi always uses 4244)")
    ap.add_argument("--interval", type=float,
                    help="seconds between reads (default: 5, or 2 while the overlay is open)")
    ap.add_argument("--scale", type=int, help="overlay window size as a multiple of 256x192 (keys 1-6 too)")
    ap.add_argument("--chroma", metavar="RRGGBB", help="overlay background colour, for a chroma key in OBS")
    ap.add_argument("-v", "--verbose", action="store_true", help="more detail in the log")
    return ap.parse_args(argv)


def _engine_args(args):
    return dict(file=args.file, game=args.game, demo=args.demo, demo_name=args.name,
                dsi_ip=args.dsi_ip, port=args.port, interval=args.interval,
                client_id=args.client_id, dry_run=args.dry_run, ra=not args.no_ra,
                blank_ra=args.blank_ra, clear_ra=args.clear_ra)


def _missing_packages(e):
    print(f"A package DSiRPC needs isn't installed ({e}).")
    print("Run Setup.bat (or 'python dsirpc.py setup') to install it.")
    return 1


def run(args, cfg):
    import logging
    from app.engine import Engine, PortInUse, LOG_FILE

    discord = not (args.no_discord or args.demo)
    if not cfg.loaded_from:
        print("No dsirpc.cfg yet: run Setup.bat (or 'python dsirpc.py setup') to make one.")
    if discord and not args.dry_run and not args.client_id and not cfg.has_discord_id:
        print("No Discord application ID: run setup, or pass --client-id (or --no-discord).")
        return 1
    try:
        engine = Engine(cfg, discord=discord, **_engine_args(args))
    except PortInUse:
        print(f"UDP port {args.port} is in use: DSiRPC (maybe in the tray) or one of its tools is already running.")
        return 1

    # A service manager stopping the process gets the same clean shutdown as
    # Ctrl+C, so the presence doesn't linger in Discord.
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)

    if args.file and args.dry_run and not args.overlay:
        engine.once()
        return 0

    engine.start()
    logging.info(f"DSiRPC is running (Ctrl+C to stop; log: {LOG_FILE})")
    try:
        if args.overlay:
            engine.run_overlay_here()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("Stopping.")
        engine.stop()
    return 0


def main(argv=None):
    _quiet_streams()
    args = parse_args(argv)
    sys.path.insert(0, ROOT)

    if args.mode == "setup":
        from app.setup_wizard import run_setup
        return run_setup()

    from app.engine import setup_logging
    from utils.config import Config
    setup_logging(console=args.mode == "run", verbose=args.verbose)
    cfg = Config()
    if args.scale:
        cfg.overlay_scale = max(1, min(6, args.scale))
    if args.chroma:
        cfg.chroma = args.chroma
    try:
        if args.mode == "tray":
            import logging
            from app.tray import run_tray

            def log_crash(kind, value, tb):
                logging.critical("DSiRPC crashed", exc_info=(kind, value, tb))
            sys.excepthook = log_crash
            return run_tray(cfg, **_engine_args(args))
        return run(args, cfg)
    except ImportError as e:
        if args.mode == "tray":
            from app.tray import message_box
            message_box(f"A package DSiRPC needs isn't installed ({e}). Run Setup.bat to install it.")
            return 1
        return _missing_packages(e)


if __name__ == "__main__":
    sys.exit(main())
