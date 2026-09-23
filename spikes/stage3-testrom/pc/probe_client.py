#!/usr/bin/env python3
"""
probe_client.py - PC-side client for the stage 3 rpcprobe wire protocol.

Speaks the exact protocol implemented in
retail/cardenginei/arm7/source/rpcprobe/probe_net.c:

  Request  (PC -> DSi): 'Q' (1) | address (u32 BE) | length (u16 BE)   = 7 bytes
  Response (DSi -> PC): 'A' (1) | address (u32 BE) | length (u16 BE) | data

Both ends use the same UDP port for source and destination (set in
RPCPROBE.CFG as `port=`). The DSi never sends anything unprompted - every
response is a reply to a request we sent, unlike stage1/2's plaintext
scripts (which also used a different port and had no request framing at
all - they won't talk to this build).

Default read target (0x02000000, 16 bytes) is the start of Main RAM, where
the ROM header gets copied at boot - for Platinum this should read back
starting with ASCII "POKEMON PL". That's a good first smoke test: it needs
no game-specific knowledge, it just confirms real bytes are coming back
from real game memory. A timeout here means the DSi never associated/
completed the WPA2 handshake; a response with garbage instead of the
expected ASCII means association+handshake worked but something's wrong
in the CCMP decrypt path (see INTEGRATION.md's AAD note) - those are two
different failure modes and this tells you which one you're looking at.

Usage:
  python probe_client.py                              # one read, default addr/len
  python probe_client.py --addr 0x02000000 --len 16
  python probe_client.py --addr 0x02000000 --len 16 --repeat 10 --interval 1
"""

import argparse
import socket
import struct
import sys
import time

MAX_PAYLOAD = 64  # PROBE_NET_MAX_PAYLOAD in probe_net.h


def build_request(address, length):
    return struct.pack(">BIH", ord("Q"), address, length)


def parse_response(data, expect_addr, expect_len):
    if len(data) < 7:
        raise ValueError(f"response too short ({len(data)} bytes)")
    if data[0:1] != b"A":
        raise ValueError(f"bad magic {data[0:1]!r} (expected b'A')")
    addr, length = struct.unpack(">IH", data[1:7])
    payload = data[7:7 + length]
    if addr != expect_addr:
        print(f"  [warn] response address 0x{addr:08X} != requested 0x{expect_addr:08X}")
    if length != expect_len:
        print(f"  [warn] response length {length} != requested {expect_len}")
    if len(payload) != length:
        raise ValueError(f"payload short: got {len(payload)}, header says {length}")
    return addr, payload


def hexdump(addr, data):
    hexpart = " ".join(f"{b:02X}" for b in data)
    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    print(f"  0x{addr:08X}: {hexpart}")
    print(f"  {'':10s}  {ascii_part}")


def main():
    ap = argparse.ArgumentParser(description="rpcprobe PC-side test client")
    ap.add_argument("--dsi-ip", default="192.168.2.195", help="DSi IP (dsi_ip in RPCPROBE.CFG)")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (port in RPCPROBE.CFG)")
    ap.add_argument("--addr", type=lambda x: int(x, 0), default=0x02000000,
                     help="Main RAM address to read (hex ok, e.g. 0x02000000)")
    ap.add_argument("--len", type=int, default=16, help=f"bytes to read (max {MAX_PAYLOAD})")
    ap.add_argument("--repeat", type=int, default=1, help="number of reads to perform")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between repeated reads")
    ap.add_argument("--timeout", type=float, default=3.0, help="seconds to wait for each response")
    args = ap.parse_args()

    if args.len > MAX_PAYLOAD:
        print(f"--len capped to {MAX_PAYLOAD} (PROBE_NET_MAX_PAYLOAD)")
        args.len = MAX_PAYLOAD

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(args.timeout)

    print(f"Reading {args.len} bytes from 0x{args.addr:08X} on {args.dsi_ip}:{args.port}")
    if args.addr == 0x02000000:
        print("(default address = start of Main RAM / ROM header copy - expect ASCII game title in the dump)")
    print()

    ok = 0
    fail = 0
    for i in range(args.repeat):
        req = build_request(args.addr, args.len)
        try:
            sock.sendto(req, (args.dsi_ip, args.port))
            data, src = sock.recvfrom(2048)
            addr, payload = parse_response(data, args.addr, args.len)
            hexdump(addr, payload)
            ok += 1
        except socket.timeout:
            print("  [timeout] no response - DSi never associated or the handshake never completed")
            fail += 1
        except (ValueError, OSError) as e:
            print(f"  [error] {e}")
            fail += 1

        if args.repeat > 1 and i < args.repeat - 1:
            time.sleep(args.interval)

    print()
    print(f"{ok} ok, {fail} failed" + (f" out of {args.repeat}" if args.repeat > 1 else ""))
    sock.close()
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
