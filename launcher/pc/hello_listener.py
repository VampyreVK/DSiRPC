#!/usr/bin/env python3
"""
hello_listener.py - prints the "DSiRPC hello #N" packets that nds-bootstrap's
in-game side sends once a second after a DSi-mode handoff.

The packets go to pc_ip= and port= from /RPCPROBE.CFG (4244 by default), with
the same port as the source. If packets arrive, the connection the launcher
made survived into gameplay.

Usage:
  python hello_listener.py
  python hello_listener.py --port 4244
"""

import argparse
import socket
import time


def main():
    ap = argparse.ArgumentParser(description="DSiRPC handoff hello listener")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (port= in RPCPROBE.CFG)")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(10.0)

    print(f"Listening on UDP {args.port}. Waiting for hello packets from the DSi...")
    count = 0
    last = None
    while True:
        try:
            data, (ip, port) = sock.recvfrom(2048)
        except socket.timeout:
            if last is None:
                print("  (nothing yet)")
            else:
                print(f"  (no packet for {time.time() - last:.0f}s)")
            continue
        count += 1
        last = time.time()
        text = data.decode(errors="replace")
        print(f"[{time.strftime('%H:%M:%S')}] #{count} from {ip}:{port}: {text}")


if __name__ == "__main__":
    main()
