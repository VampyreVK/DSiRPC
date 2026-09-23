"""
dsi_status.py - read Pokemon Platinum's state and print it in plain English.

Reads from the real DSi over DSiRPC (the modified nds-bootstrap must be
running the game), or from a 4 MB RAM dump (e.g. from melonDS) with --file. Everything the
parser knows is printed, including values whose meaning is still a guess,
so it's easy to see what holds up while playing.

Usage:
  python dsi_status.py                       # read the DSi once
  python dsi_status.py --watch 5             # re-read every 5 seconds
  python dsi_status.py --file ram_dump.bin   # parse a RAM dump instead
  python dsi_status.py --json                # print the parsed data as JSON
  python dsi_status.py --dsi-ip 192.168.2.195 --port 4244

Don't run this at the same time as hello_listener.py or dsirpc_client.py:
they all listen on the same UDP port.
"""

import argparse
import json
import logging
import os
import sys
import time

from core.charmap import parse_charmap_txt
from core.parser import PlatinumParser

HERE = os.path.dirname(os.path.abspath(__file__))


def describe_mon(mon, with_item=True):
    name = mon['species']
    nick = mon['nickname']
    label = f"{nick} ({name})" if nick and nick.lower() != name.lower() else name
    parts = [label, f"Lv {mon['level']}", f"HP {mon['curr_hp']}/{mon['max_hp']}", mon['gender']]
    if mon.get('nature'):
        parts.append(mon['nature'])
    if mon.get('status'):
        parts.append(mon['status'])
    if mon.get('shiny'):
        parts.append('SHINY')
    if mon.get('egg'):
        parts.append('EGG')
    if with_item and mon.get('item') not in (None, '-'):
        parts.append(f"holding {mon['item']}")
    text = "  ".join(parts)
    if mon.get('moves'):
        text += "\n       moves: " + ", ".join(mon['moves'])
    if mon.get('checksum_ok') is False:
        text += "\n       (checksum mismatch: probably read while the game was changing it, try again)"
    return text


def print_report(d, source):
    pt = d['playtime']
    print(f"Trainer    {d['trainer_name']} ({d['character']})   ID {d['trainer_id']:05d}   "
          f"money {d['money']:,}   coins {d['coins']}   "
          f"playtime {pt['hours']}:{pt['minutes']:02d}:{pt['seconds']:02d}")
    badges = d['badges']
    print(f"Badges     {len(badges)}/8" + (f"   {', '.join(badges)}" if badges else ""))
    dex = d['pokedex']
    print(f"Pokedex    seen {dex['seen']}, caught {dex['caught']}" + ("" if dex['obtained'] else "   (no Pokedex yet)"))

    loc = d['location']
    where = loc['name'] if loc['area'] == loc['name'] else f"{loc['name']} - {loc['area']}"
    print(f"Location   {where}   (map {loc['map_id']}, weather {loc['weather']})")
    live = d['position_live']
    print(f"Position   saved x={loc['x']} z={loc['z']} facing {loc['facing']}   "
          f"live x={live['x']} z={live['z']} height={live['height']}   "
          f"stable x={live['stable_x']} z={live['stable_z']}")
    if d['direction_raw'] is not None:
        print(f"Direction  raw {d['direction_raw']:#06x}   (RA note, meaning not confirmed yet)")

    party = d['party']
    print(f"Party      {d['party_count']}/6")
    for mon in party:
        print(f"  {mon['slot']}. {describe_mon(mon)}")

    battle = d['battle']
    misc = d['misc']
    music = misc['music'] or 'unknown track'
    if battle['active']:
        kind = music if battle['music_says_battle'] else f"battle? music says: {music}"
        print(f"Battle     {kind}" + (f"   trainer: {battle['trainer']}" if misc['music_id'] != 0x45C else ""))
        for mon in battle['mons']:
            print(f"  {mon['side']:<12} {describe_mon(mon, with_item=False)}")
    else:
        extra = "   (music sounds like a battle though)" if battle['music_says_battle'] else ""
        print(f"Battle     none   (battle pointer {battle['pointer']}){extra}")

    print(f"Misc       music {misc['music_id']:#06x} ({music})   text box {'open' if misc['textbox_open'] else 'closed'}   "
          f"DS clock {misc['clock']}")
    print(f"Source     {source}")


def main():
    ap = argparse.ArgumentParser(description="Print Pokemon Platinum's state from the DSi or a RAM dump")
    ap.add_argument("--file", help="parse a 4 MB RAM dump (e.g. from melonDS) instead of reading the DSi")
    ap.add_argument("--dsi-ip", help="skip waiting for a hello packet")
    ap.add_argument("--port", type=int, default=4244, help="port= in RPCPROBE.CFG")
    ap.add_argument("--timeout", type=float, default=1.0, help="seconds to wait for each reply")
    ap.add_argument("--watch", type=float, metavar="SECONDS", help="keep re-reading at this interval")
    ap.add_argument("--json", action="store_true", help="print the parsed data as JSON")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    charmap = parse_charmap_txt(os.path.join(HERE, "PokeGen4Charmap.txt"))

    if args.file:
        with open(args.file, "rb") as f:
            ram = f.read()
        source_name = args.file
    else:
        from core.dsi_memory import DsiRam, connect
        print(f"Waiting for the DSi on UDP port {args.port}...")
        client = connect(port=args.port, dsi_ip=args.dsi_ip, timeout=args.timeout)
        if client is None:
            print("No hello from the DSi within 15 s - is the game running after the handoff?")
            sys.exit(1)
        ram = DsiRam(client)
        source_name = f"DSi at {client.dsi_ip}"

    while True:
        t0 = time.time()
        failed = False
        try:
            if hasattr(ram, "clear"):
                ram.clear()
            data = PlatinumParser(ram, charmap).parse()
        except (TimeoutError, RuntimeError) as e:
            print(f"Read failed: {e}")
            data, failed = None, True
        elapsed = time.time() - t0

        if data:
            if hasattr(ram, "bytes_fetched"):
                source = f"{source_name}, {ram.bytes_fetched:,} bytes in {elapsed:.1f} s"
            else:
                source = source_name
            print()
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                print_report(data, source)
        elif not failed:
            print("Couldn't find the save data. Is the game past the title screen?")

        if not args.watch:
            break
        try:
            time.sleep(max(0.0, args.watch - elapsed))
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
