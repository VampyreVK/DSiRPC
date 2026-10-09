"""
games.py - which game the DSi is running, and which per-game features apply.

rpcprobe's hellos say which game is running (gc= game code, v= ROM version,
hc= header CRC; see core/dsirpc_client.py, DSiClient.game). The Platinum
parser only makes sense for Platinum: on any other game its pointers read
garbage. Black and White (US) have their own parser, core/bw_parser.py. Builds of rpcprobe from before the hellos carried the game don't say,
and DSiRPC only supported Platinum then, so an unknown game counts as
Platinum.
"""

PLATINUM_US = "CPUE"
BLACK_US, WHITE_US = "IRBO", "IRAO"   # core/bw_parser.py reads these two

# Names for status lines. Anything missing shows as its game code.
NAMES = {
    "CPUE": "Pokemon Platinum",
    "IRBO": "Pokemon Black",
    "IRAO": "Pokemon White",
    "IREO": "Pokemon Black 2",
    "IRDO": "Pokemon White 2",
    "IPKE": "Pokemon HeartGold",
    "IPGE": "Pokemon SoulSilver",
}


def is_platinum(game):
    """True for Pokemon Platinum (US), and for an older rpcprobe build that
    doesn't report the game."""
    return game is None or game.get("code") == PLATINUM_US


def is_bw(game):
    """True for Pokemon Black or White (US)."""
    return bool(game) and game.get("code") in (BLACK_US, WHITE_US)


def bw_version(game):
    """'Black' or 'White'."""
    return "White" if (game or {}).get("code") == WHITE_US else "Black"


def name(game):
    """'Pokemon Black (IRBO)', or 'an unknown game' for older builds."""
    if not game:
        return "an unknown game"
    code = game.get("code", "????")
    return f"{NAMES[code]} ({code})" if code in NAMES else code
