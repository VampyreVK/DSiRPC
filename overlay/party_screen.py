"""
party_screen.py - the party screen's shared parts (V in the overlay window):
six tall cards, three across, each a party panel over a tray with the
Pokemon's moves, nature and held item. overlay/scenes.py draws it for
Platinum and overlay/unova.py for Black and White, in their own looks.
"""

from core import bw_data

from . import ui

MOVE_INFO = bw_data.MOVE_INFO

# The party screen (V): six tall cards, three across, each a party panel over
# a tray with the moves, the nature and the held item.
CARD_W, CARD_TOP, CARD_TRAY, CARD_GAP = 84, 46, 40, 1
CARD_POS = [(1 + (i % 3) * (CARD_W + 1), 16 + (i // 3) * (CARD_TOP + CARD_GAP + CARD_TRAY + 1)) for i in range(6)]


def live_party(d):
    """The party, with your battlers' HP, status and PP from the battle
    (the game keeps them in its own copies until the battle ends): each
    battler matched to the first party Pokemon with its species, level
    and nickname."""
    party = [dict(m) for m in d.get('party') or []]
    used = set()
    for b in (d.get('battle') or {}).get('mons') or []:
        if not (d['battle'].get('active') and str(b.get('side', '')).startswith('yours')):
            continue
        for i, m in enumerate(party):
            if i in used or m.get('egg') or (m.get('species_id'), m.get('level'), m.get('nickname') or '') != \
                    (b.get('species_id'), b.get('level'), b.get('nickname') or ''):
                continue
            used.add(i)
            m.update(curr_hp=b.get('curr_hp', m.get('curr_hp')), max_hp=b.get('max_hp', m.get('max_hp')),
                     status=b.get('status', m.get('status')))
            if b.get('pp') and b.get('moves') == m.get('moves'):
                m['pp'] = list(b['pp'])
            break
    return party


def draw_tray(canvas, mini, x, y, w, mon, text, muted, warn=(248, 208, 72), empty=(232, 88, 72)):
    """A party card's tray (its top at y, CARD_TRAY high): the four moves
    (a stripe in the type's colour, the name, the PP when known: gold when
    low, red when out), then the nature and the held item."""
    if mon.get('egg'):
        mini.draw(canvas, "AN EGG", (x, y + 4), muted)
        mini.draw(canvas, "HATCHING SOON...", (x, y + 12), muted)
        return
    moves, pps = mon.get('moves') or [], mon.get('pp') or []
    for k in range(4):
        yy = y + 3 + k * 7
        if k >= len(moves):
            mini.draw(canvas, "-", (x + 5, yy), muted)
            continue
        mtype, _, base = MOVE_INFO.get(moves[k], ('Normal', 'Status', 0))
        canvas.fill(ui.darken(ui.TYPE_COLORS.get(mtype, (150, 150, 150)), 40), (x, yy - 1, 3, 7))
        canvas.fill(ui.TYPE_COLORS.get(mtype, (150, 150, 150)), (x, yy, 3, 5))
        pp = pps[k] if k < len(pps) else None
        tag = '' if pp is None else f"{pp}/{base}" if base and pp <= base else str(pp)
        tw = mini.width(tag) if tag else 0
        mini.draw(canvas, mini.fit(moves[k], w - 5 - tw - 3), (x + 5, yy), text)
        if tag:
            col = empty if pp == 0 else warn if base and pp * 4 <= base else muted
            mini.draw(canvas, tag, (x + w - tw, yy), col)
    nature = (mon.get('nature') or '').upper()
    item = mon.get('item') if mon.get('item') not in (None, 'None', '#0') else None
    mini.draw(canvas, nature, (x, y + 32), muted)
    if item:
        iw = min(mini.width(item), w - mini.width(nature) - 6)
        mini.draw(canvas, mini.fit(item, iw), (x + w - iw, y + 32), text)
