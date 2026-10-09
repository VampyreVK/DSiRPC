"""
bw_presence.py - Pokemon Black and White's Discord Rich Presence, from the
parsed game state (core/bw_parser.py):

  in a battle:  "Competing", who you're battling (a Gym Leader, the Elite
                Four, Alder, a Battle Subway train, ...), the foe standing on
                the turf the overlay's battle view uses for the place as the
                big image, your Pokemon's back sprite as the small one, and
                "<yours> is fighting <foe>"
  otherwise:    "Playing", where you are, badges / Pokedex / season, your
                trainer walking the way you face on the place's turf as the
                big image (with the trainers beaten and items found here
                when the notes know them), your lead's overworld sprite as
                the small one, and the party fraction; in the Battle Subway,
                the Battle Institute and the Pokemon League their own lines
                (streak, rank, Elite Four beaten)

The big images come from Assets/Unova-Battle (and -Shiny) and
Assets/Unova-Trainer, made by Assets/Unova-Battle/process_unova.py. Only
Unova's own Pokemon (494-649) have Unova turfs; older ones use Platinum's
dioramas. The timer counts the save's playtime.
"""

from pypresence import ActivityType

from core import bw_data, games
from rpc import platinum_presence as platinum

SPRITES = platinum.SPRITES
UNOVA_DEX = range(494, 650)


def turf(d):
    """The battle platform for where you are (core/bw_data.terrain)."""
    return bw_data.terrain(d.get('location') or {}, d.get('season'))[1]


def foe_image(d, mon):
    sid, shiny = mon['species_id'], mon.get('shiny')
    if sid in UNOVA_DEX:
        folder = "Unova-Battle-Shiny" if shiny else "Unova-Battle"
        return f"{SPRITES}/{folder}/{turf(d)}/{sid}.gif?raw=true"
    return platinum.front_sprite(sid, shiny)


def trainer_image(d):
    character = d.get('character') if d.get('character') in ('Hilbert', 'Hilda') else 'Hilbert'
    facing = (d.get('location') or {}).get('facing')
    facing = facing if facing in ('up', 'down', 'left', 'right') else 'down'
    return f"{SPRITES}/Unova-Trainer/{turf(d)}/{character}-{facing.capitalize()}.gif?raw=true"


def game_name(d):
    return f"Pokémon {d.get('version') or 'Black'}"


def game_code(d):
    return ((d.get('game') or {}).get('code')
            or (games.WHITE_US if d.get('version') == 'White' else games.BLACK_US))


def mon_name(mon):
    return platinum.mon_name(mon)


def _hp(mon):
    return f"Lv {mon['level']}, {mon['curr_hp']}/{mon['max_hp']} HP"


def battle_presence(d):
    battle = d['battle']
    mons = {m['side']: m for m in battle['mons']}
    mine, foe = mons['yours'], mons['foe']
    mine2, foe2 = mons.get('yours (2nd)'), mons.get('foe (2nd)')
    kind, name = battle.get('kind'), battle.get('trainer')
    subway, institute = d.get('subway'), d.get('institute')

    if battle.get('wild'):
        details = "Encountering a shiny Pokémon!" if foe.get('shiny') else "Encountering a wild Pokémon"
        owner = "A wild"
    elif kind == 'gym':
        details = f"Battling Gym Leader {name}" if name else "Battling a Gym Leader"
        owner = f"{name}'s" if name else "The Gym Leader's"
    elif kind == 'elite':
        details = f"Battling Elite Four {name}" if name else "Battling the Elite Four"
        owner = f"{name}'s" if name else "The Elite Four's"
    elif kind == 'champion':
        details = f"Battling Champion {name or bw_data.CHAMPION}"
        owner = f"{name or bw_data.CHAMPION}'s"
    elif subway:
        train = f"{subway['train']} Train" if subway.get('train') else "the Battle Subway"
        details = f"Battle Subway: {train}, battle {(subway.get('streak') or 0) + 1}"
        owner = "The subway trainer's"
    elif institute:
        details = f"Battle Institute test ({institute.get('rank') or 'Beginner'} rank)"
        owner = "The trainer's"
    else:
        details = "In a trainer battle"
        owner = "The trainer's"

    state = f"{mon_name(mine)} and {mon_name(mine2)} are fighting " if mine2 else f"{mon_name(mine)} is fighting "
    state += foe['species'] + (f" and {foe2['species']}" if foe2 else "")
    small_text = f"{d.get('trainer_name') or 'Your'}'s {mon_name(mine)} ({_hp(mine)})"
    if mine2:
        small_text += f" and {mon_name(mine2)} ({_hp(mine2)})"
    caught = " (caught before)" if foe.get('owned') else ""
    return {
        'name': game_name(d),
        'activity_type': ActivityType.COMPETING,
        'details': details[:128],
        'state': state[:128],
        'large_image': foe_image(d, foe),
        'large_text': f"{owner} {foe['species']} ({_hp(foe)}){caught}"[:128],
        'small_image': platinum.back_sprite(mine['species_id'], mine.get('shiny')),
        'small_text': small_text[:128],  # Discord's limit
    }


def overworld_presence(d):
    loc = d.get('location') or {}
    place = loc.get('name') or loc.get('area') or "Unova"
    party = [m for m in d.get('party') or [] if not m.get('egg')]
    alive = sum(1 for m in party if m['curr_hp'] > 0)
    season = (d.get('season') or '').capitalize()
    subway, institute, league = d.get('subway'), d.get('institute'), d.get('league')

    details = f"Exploring {place}"
    bits = [f"Badges: {len(d.get('badges') or [])}", f"Pokédex: {(d.get('pokedex') or {}).get('caught', 0)}"]
    if subway:
        details = f"Riding the {subway['train']} Train" if subway.get('train') else "At the Battle Subway"
        bits = [f"Streak: {subway.get('streak', 0)}", f"Record: {subway.get('record', 0)}", f"{subway.get('bp', 0)} BP"]
    elif institute:
        details = "At the Battle Institute"
        bits = [f"Rank: {institute.get('rank') or 'Beginner'}", f"{institute.get('points', 0)} points"]
    elif league:
        details = "Challenging the Pokémon League"
        bits = [f"Elite Four beaten: {len(league.get('beaten') or [])}/4"] + bits[1:]
    elif season:
        bits.append(season)
    progress = d.get('progress')
    if progress and progress[1]:
        bits.append(f"Achievements: {progress[0]}/{progress[1]}")

    big = f"{d.get('trainer_name') or 'You'} in {place}"
    route = d.get('route') or {}
    extras = []
    if 'trainers' in route:
        extras.append("trainers beaten: {}/{}".format(*route['trainers']))
    if 'items' in route:
        extras.append("items found: {}/{}".format(*route['items']))
    if d.get('repel'):
        extras.append(f"Repel: {d['repel']} steps")
    if extras:
        big += " (" + ", ".join(extras) + ")"

    presence = {
        'name': game_name(d),
        'activity_type': ActivityType.PLAYING,
        'details': details[:128],
        'state': " | ".join(bits)[:128],
        'large_image': trainer_image(d),
        'large_text': big[:128],
    }
    if party:
        lead = party[0]
        species = '' if mon_name(lead) == lead['species'] else f" ({lead['species']})"
        presence['small_image'] = platinum.overworld_sprite(lead['species_id'], lead.get('shiny'))
        presence['small_text'] = f"Lead: {mon_name(lead)}{species}, {_hp(lead)}"[:128]
        presence['party_size'] = [alive, len(party)]
    return presence


def build_presence(d):
    return battle_presence(d) if d['battle']['active'] else overworld_presence(d)


def playtime_start(d):
    return platinum.playtime_start(d)
