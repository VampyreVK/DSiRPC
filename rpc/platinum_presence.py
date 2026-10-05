"""
platinum_presence.py - Pokemon Platinum's Discord Rich Presence, from the
parsed game state (core/parser.py):

  in a battle:  "Competing in Pokémon Platinum", the foe's sprite as the big
                image, your Pokémon's back sprite as the small one, and
                "<yours> is fighting <foe>"
  otherwise:    "Playing", where you are, badges / Pokédex, the party
                fraction (Pokémon still standing out of party size), your
                trainer walking in the direction you face as the big image
                and your lead Pokémon's overworld sprite as the small one

Sprites come from the Assets folders on GitHub Pages, by national dex number.
"""

import time

from pypresence import ActivityType

from core import platinum_data as pdata

SPRITES = "https://vampyrevk.github.io/DSiRPC/Assets"

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
    mine2, foe2 = mons.get('yours (2nd)'), mons.get('foe (2nd)')
    music = d['misc']['music_id']
    trainer = battle['trainer'] if battle['trainer'] and not battle['trainer'].startswith('sprite') else None

    # The parser's wild flag (the foe has your trainer ID) is more reliable
    # than the music, which can still be the encounter jingle at the start.
    if battle.get('wild', music == WILD):
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

    if mine2:
        state = f"{mon_name(mine)} and {mon_name(mine2)} are fighting {foe['species']}"
    else:
        state = f"{mon_name(mine)} is fighting {foe['species']}"
    if foe2:
        state += f" and {foe2['species']}"
    small_text = f"{d['trainer_name']}'s {mon_name(mine)} (Lv {mine['level']}, {mine['curr_hp']}/{mine['max_hp']} HP)"
    if mine2:
        small_text += f" and {mon_name(mine2)} (Lv {mine2['level']}, {mine2['curr_hp']}/{mine2['max_hp']} HP)"

    return {
        'activity_type': ActivityType.COMPETING,
        'details': details,
        'state': state[:128],
        'large_image': front_sprite(foe['species_id'], foe.get('shiny')),
        'large_text': f"{owner} {foe['species']} (Lv {foe['level']}, {foe['curr_hp']}/{foe['max_hp']} HP)",
        'small_image': back_sprite(mine['species_id'], mine.get('shiny')),
        'small_text': small_text[:128],  # Discord's limit
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


def playtime_start(d):
    """The time the save's playtime started, so Discord's timer shows the
    playtime."""
    pt = d['playtime']
    return int(time.time()) - (pt['hours'] * 3600 + pt['minutes'] * 60 + pt['seconds'])
