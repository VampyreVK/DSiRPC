"""
dsi_battle_rpc.py - test Discord Rich Presence driven by the real DSi.

Reads the game every few seconds (same parser as dsi_status.py) and shows:
  in a battle:  "Competing in Pokémon Platinum", the foe's sprite as the big
                image, your Pokémon's back sprite as the small one, and
                "<yours> is fighting <foe>"
  otherwise:    "Playing", where you are, badges / Pokédex, the party
                fraction (Pokémon still standing out of party size), your
                trainer walking in the direction you face as the big image
                and your lead Pokémon's overworld sprite as the small one

Sprites come from the Assets folders on GitHub Pages, by national dex number.

Usage:
  python dsi_battle_rpc.py                         # client ID from PokemonPlatinumRPC.cfg
  python dsi_battle_rpc.py --client-id 1502029609045069985
  python dsi_battle_rpc.py --dry-run               # read the DSi, print instead of sending
  python dsi_battle_rpc.py --file ram_dump.bin --dry-run

Turn off Vencord's CustomRPC while this runs, or Discord shows two activities.
Don't run it together with dsi_status.py / hello_listener.py (same UDP port).
"""

import argparse
import logging
import os
import sys
import time

from pypresence import ActivityType

from core import platinum_data as pdata
from core.charmap import parse_charmap_txt
from core.parser import PlatinumParser
from utils.config import Config

HERE = os.path.dirname(os.path.abspath(__file__))
SPRITES = "https://vampyrevk.github.io/melonDS-RPC-Suite/Assets"

WILD, GYM, TRAINER, CHAMPION, RIVAL, ELITE_FOUR = 0x45C, 0x45D, 0x45F, 0x462, 0x464, 0x470


def front_sprite(species_id, shiny=False):
    folder = "Shiny-Battle-NormalLarge" if shiny else "Pokemon-Battle-NormalLarge"
    return f"{SPRITES}/{folder}/{species_id}.gif?raw=true"


def back_sprite(species_id, shiny=False):
    folder = "Shiny-Battle-BackSmall" if shiny else "Pokemon-Battle-BackSmall"
    return f"{SPRITES}/{folder}/{species_id}.gif?raw=true"


def overworld_sprite(species_id, shiny=False):
    folder = "Shiny-Pokemon-Overworld" if shiny else "Pokemon-Overworld"
    return f"{SPRITES}/{folder}/{species_id}.gif?raw=true"


def trainer_sprite(character, facing):
    # Trainer-Overworld/<Lucas|Dawn>-<Down|Left|Right|Up>.gif, made by process_trainer.py
    return f"{SPRITES}/Trainer-Overworld/{character}-{facing.capitalize()}.gif?raw=true"


def player_facing(d):
    """'up', 'down', 'left' or 'right'. Prefers the live value from the RA
    note (low byte, same 0-3 order as the saved one), then the saved facing."""
    raw = d.get('direction_raw')
    if raw is not None and (raw & 0xFF) < 4:
        return pdata.DIRECTIONS[raw & 0xFF]
    facing = d['location']['facing']
    return facing if isinstance(facing, str) else 'down'


def mon_name(mon):
    nick = mon.get('nickname') or ''
    return nick if nick and not mon.get('egg') else mon['species']


def battle_presence(d):
    battle = d['battle']
    mons = {m['side']: m for m in battle['mons']}
    mine, foe = mons['yours'], mons['foe']
    foe2 = mons.get('foe (2nd)')
    music = d['misc']['music_id']
    trainer = battle['trainer'] if battle['trainer'] and not battle['trainer'].startswith('sprite') else None

    if music == WILD:
        details = "Encountering a wild Pokémon"
        owner = "A wild"
    elif music == GYM:
        details = f"Battling Gym Leader {trainer}" if trainer else "Battling a Gym Leader"
        owner = f"{trainer}'s" if trainer else "The Gym Leader's"
    elif music == RIVAL:
        details = f"Battling rival {trainer}" if trainer else "Battling a rival"
        owner = f"{trainer}'s" if trainer else "The rival's"
    elif music == CHAMPION:
        details = "Battling Champion Cynthia"
        owner = "Cynthia's"
    elif music == ELITE_FOUR:
        details = f"Battling Elite Four {trainer}" if trainer else "Battling the Elite Four"
        owner = f"{trainer}'s" if trainer else "The Elite Four's"
    elif music == TRAINER:
        details = "In a trainer battle"
        owner = "The trainer's"
    else:
        details = "In a battle"
        owner = "The foe's"

    state = f"{mon_name(mine)} is fighting {foe['species']}"
    if foe2:
        state += f" and {foe2['species']}"

    return {
        'activity_type': ActivityType.COMPETING,
        'details': details,
        'state': state,
        'large_image': front_sprite(foe['species_id'], foe.get('shiny')),
        'large_text': f"{owner} {foe['species']} (Lv {foe['level']}, {foe['curr_hp']}/{foe['max_hp']} HP)",
        'small_image': back_sprite(mine['species_id'], mine.get('shiny')),
        'small_text': f"{d['trainer_name']}'s {mon_name(mine)} (Lv {mine['level']}, {mine['curr_hp']}/{mine['max_hp']} HP)",
    }


def overworld_presence(d):
    loc = d['location']
    party = [m for m in d['party'] if not m.get('egg')]
    alive = sum(1 for m in party if m['curr_hp'] > 0)
    presence = {
        'activity_type': ActivityType.PLAYING,
        'details': f"Exploring {loc['name']}",
        'state': f"Badges: {len(d['badges'])} | Pokédex: {d['pokedex']['caught']}",
    }
    presence['large_image'] = trainer_sprite(d['character'], player_facing(d))
    presence['large_text'] = f"{d['trainer_name']} in {loc['area']}"
    if party:
        lead = party[0]
        species = '' if mon_name(lead) == lead['species'] else f" ({lead['species']})"
        presence['small_image'] = overworld_sprite(lead['species_id'], lead.get('shiny'))
        presence['small_text'] = f"Lead: {mon_name(lead)}{species}, Lv {lead['level']}, {lead['curr_hp']}/{lead['max_hp']} HP"
        presence['party_size'] = [alive, len(party)]
    return presence


def build_presence(d):
    return battle_presence(d) if d['battle']['active'] else overworld_presence(d)


def main():
    ap = argparse.ArgumentParser(description="Test Discord Rich Presence from the DSi")
    ap.add_argument("--client-id", help="Discord application ID (default: discord_client_id in PokemonPlatinumRPC.cfg)")
    ap.add_argument("--file", help="use this melonDS RAM dump instead of the DSi")
    ap.add_argument("--dsi-ip", help="skip waiting for a hello packet")
    ap.add_argument("--port", type=int, default=4244, help="port= in RPCPROBE.CFG")
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between reads (Discord allows about one update per 5 s)")
    ap.add_argument("--dry-run", action="store_true", help="print the presence instead of sending it to Discord")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    charmap = parse_charmap_txt(os.path.join(HERE, "PokeGen4Charmap.txt"))

    rpc = None
    if not args.dry_run:
        from rpc.discord_client import DiscordRPC
        client_id = args.client_id or Config(os.path.join(HERE, "PokemonPlatinumRPC.cfg")).discord_client_id
        if not client_id:
            print("No Discord application ID: pass --client-id or set discord_client_id in PokemonPlatinumRPC.cfg")
            sys.exit(1)
        rpc = DiscordRPC(client_id)
        if not rpc.connect():
            print("Couldn't connect to Discord - is the desktop app running?")
            sys.exit(1)

    if args.file:
        with open(args.file, "rb") as f:
            ram = f.read()
    else:
        from core.dsi_memory import DsiRam, connect
        print(f"Waiting for the DSi on UDP port {args.port}...")
        client = connect(port=args.port, dsi_ip=args.dsi_ip)
        if client is None:
            print("No hello from the DSi within 15 s - is the game running after the handoff?")
            sys.exit(1)
        ram = DsiRam(client)

    start = None          # playtime-based, so Discord's timer shows the save's playtime
    last_sent = None
    failures = 0
    cleared = False

    try:
        while True:
            t0 = time.time()
            data = None
            try:
                if hasattr(ram, "clear"):
                    ram.clear()
                data = PlatinumParser(ram, charmap).parse()
            except (TimeoutError, RuntimeError) as e:
                logging.warning(f"Read failed: {e}")

            if data:
                failures = 0
                if start is None:
                    pt = data['playtime']
                    start = int(time.time()) - (pt['hours'] * 3600 + pt['minutes'] * 60 + pt['seconds'])
                presence = build_presence(data)
                presence['start'] = start
                if presence != last_sent or cleared:
                    if rpc:
                        if not rpc.connected:
                            rpc.connect()
                        rpc.update(**presence)
                    shown = {k: (v.name if isinstance(v, ActivityType) else v) for k, v in presence.items() if k != 'start'}
                    print(time.strftime("%H:%M:%S"), shown)
                    last_sent, cleared = presence, False
            else:
                failures += 1
                # About 30 s without data: take the presence down until the DSi answers again.
                if failures * args.interval >= 30 and not cleared:
                    print(time.strftime("%H:%M:%S"), "no data from the DSi, clearing the presence")
                    if rpc and rpc.connected:
                        try:
                            rpc.rpc.clear()
                        except Exception as e:
                            logging.error(f"Couldn't clear the presence: {e}")
                    cleared = True

            if args.file and args.dry_run:
                break
            time.sleep(max(0.0, args.interval - (time.time() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        if rpc:
            rpc.close()


if __name__ == "__main__":
    main()
