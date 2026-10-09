"""
effects.py - short move animations for the battle view, drawn with plain
pixel shapes (no image files).

The move picks a flavour from its name (MOVE_STYLE, then KEYWORDS: a punch
throws a fist, a fang move bites, a beam is a beam), drawn in the move's
type colour, and most flavours finish with a burst in the type's own style
(_type_burst: flames rise for Fire, shards fly for Ice, sparks crackle for
Electric, ...), so Fire Punch, Ice Punch and Thunder Punch share a fist but
not a finish. Moves without a flavour fall back on their type:

    flame    Fire, Dragon                  flames fly over, then flare up
    bubbles  Water, Poison                 wobbling bubbles fly over and pop
    leaves   Grass                         spinning leaves fly over
    swarm    Bug                           a cloud of specks buzzes over
    bolt     Electric                      lightning strikes from above
    shards   Ice                           ice shards close in from all sides
    rocks    Rock, Ground                  rocks drop onto the target
    rings    Psychic, special Normal moves rings ripple out
    wisps    Ghost, special Dark moves     wisps circle the target
    claw     Flying, Steel, physical Dark  claw streaks
    impact   Normal, Fighting              a hit spark
    aura     any other status move         sparkles rise around the user

The flavours: punch, kick, bite, claw, blade (one or two crossing cuts), jab,
volley (rapid-fire needles and seeds), whip, tackle (speed lines and a big
hit), spin, vortex (Fire Spin, Whirlpool, ...), beam, orb (Shadow Ball, Aura
Sphere, ...), stream (Flamethrower, Hydro Pump, ...), gas, wave (Surf),
shimmer (Heat Wave, Icy Wind), pulse (Discharge, Lava Plume, ...), quake,
erupt (Stone Edge, Earth Power), meteor (Rock Slide, Draco Meteor, ...),
storm (Blizzard), sound (with notes for songs), gust, drain (Giga Drain and
friends; Drain Punch and Horn Leech drain after their hit too), explode, and
for status moves buff, debuff, heal, shield, hex, hearts, powder, web,
weather, hazard and room.

Effects know the battlers only by key ('you0', 'foe0', ...). The scene
passes in where each sprite is drawn this frame, so an effect follows its
Pokemon (and is skipped if one isn't on screen). shake() is how far the
scene should shake the screen for it (quakes, explosions, heavy hits).
"""

import math
import random

import pygame

from . import ui

STYLE_BY_TYPE = {
    'Fire': 'flame', 'Dragon': 'flame', 'Water': 'bubbles', 'Poison': 'bubbles',
    'Grass': 'leaves', 'Bug': 'swarm', 'Electric': 'bolt', 'Ice': 'shards',
    'Rock': 'rocks', 'Ground': 'rocks', 'Psychic': 'rings', 'Ghost': 'wisps',
    'Flying': 'claw', 'Steel': 'claw', 'Normal': 'impact', 'Fighting': 'impact',
}


def _group(style, names):
    return {n: style for n in names.split(', ')}


# Moves whose name alone doesn't say what they look like (and the ones a
# keyword below would get wrong).
MOVE_STYLE = {
    **_group('buff', "Swords Dance, Dragon Dance, Quiver Dance, Bulk Up, Calm Mind, Nasty Plot, Agility, "
                     "Work Up, Hone Claws, Coil, Shell Smash, Iron Defense, Harden, Defense Curl, Withdraw, "
                     "Amnesia, Barrier, Acid Armor, Growth, Rock Polish, Autotomize, Shift Gear, Cotton Guard, "
                     "Cosmic Power, Stockpile, Meditate, Sharpen, Howl, Focus Energy, Charge, Belly Drum, "
                     "Tail Glow, Double Team, Minimize, Defend Order, Magnet Rise, Acupressure, Power Trick, "
                     "Psych Up, Stored Power"),
    **_group('heal', "Recover, Roost, Synthesis, Moonlight, Morning Sun, Softboiled, Milk Drink, Slack Off, "
                     "Rest, Heal Order, Wish, Aqua Ring, Ingrain, Heal Pulse, Heal Bell, Aromatherapy, Refresh, "
                     "Swallow, Lunar Dance, Healing Wish, Pain Split"),
    **_group('shield', "Protect, Detect, Reflect, Light Screen, Safeguard, Mist, Wide Guard, Quick Guard, "
                       "Endure, Substitute, Magic Coat, Lucky Chant, Follow Me, Snatch, Mirror Coat"),
    **_group('debuff', "Leer, Tail Whip, Scary Face, Fake Tears, Feather Dance, Tickle, Flash, Kinesis, "
                       "Memento, Charm, Captivate"),
    **_group('hearts', "Attract, Sweet Kiss, Lovely Kiss"),
    **_group('powder', "Sleep Powder, Stun Spore, Poison Powder, Spore, Cotton Spore, Rage Powder, Sweet Scent"),
    **_group('web', "String Shot, Spider Web, Electroweb"),
    **_group('gas', "Smog, Clear Smog, Poison Gas, Smoke Screen, Sand Attack, Haze, Mud Sport"),
    **_group('weather', "Sunny Day, Rain Dance, Sandstorm, Hail, Tailwind, Water Sport"),
    **_group('hazard', "Spikes, Toxic Spikes, Stealth Rock"),
    **_group('room', "Trick Room, Wonder Room, Magic Room, Gravity"),
    **_group('wisps', "Will-O-Wisp, Night Shade, Ominous Wind, Hex, Lick, Astonish, Shadow Sneak, Curse, "
                      "Nightmare, Grudge, Spite, Destiny Bond"),
    **_group('sound', "Growl, Roar, Screech, Metal Sound, Supersonic, Sing, Perish Song, Grass Whistle, "
                      "Snore, Uproar, Hyper Voice, Bug Buzz, Snarl, Chatter, Round, Echoed Voice, Relic Song, "
                      "Sonic Boom"),
    **_group('gust', "Gust, Air Cutter, Air Slash, Razor Wind, Silver Wind, Whirlwind, Wing Attack, Steel Wing, "
                     "Acrobatics, Fly, Bounce, Sky Drop, Pluck, Defog"),
    **_group('vortex', "Fire Spin, Whirlpool, Sand Tomb, Magma Storm, Leaf Tornado, Twister, Hurricane, "
                       "Leaf Storm, Petal Dance"),
    **_group('volley', "Pin Missile, Twineedle, Spike Cannon, Bullet Seed, Icicle Spear, Rock Blast, Ice Shard, "
                       "Barrage, Swift, Magical Leaf, Razor Leaf, Present, Pay Day"),
    **_group('wave', "Surf, Muddy Water, Sludge Wave, Water Pledge, Brine"),
    **_group('shimmer', "Heat Wave, Icy Wind, Powder Snow, Frost Breath"),
    **_group('pulse', "Discharge, Lava Plume, Eruption, Water Spout, Synchronoise, Night Daze, Dark Pulse, "
                      "Water Pulse, Dragon Pulse, Vacuum Wave, Shock Wave, Psywave, Extrasensory, Metal Burst"),
    **_group('quake', "Earthquake, Magnitude, Bulldoze, Fissure"),
    **_group('erupt', "Earth Power, Stone Edge, Rock Climb, Seed Flare"),
    **_group('meteor', "Rock Slide, Draco Meteor, Icicle Crash, Avalanche, Rock Wrecker, Sky Attack, Future Sight, "
                       "Doom Desire"),
    **_group('storm', "Blizzard, Sheer Cold, Glaciate"),
    **_group('drain', "Absorb, Mega Drain, Giga Drain, Leech Life, Dream Eater, Leech Seed"),
    **_group('explode', "Explosion, Selfdestruct, Final Gambit"),
    **_group('tackle', "Body Slam, Heavy Slam, Heat Crash, Steamroller, Rock Smash, Strength, Return, Frustration, "
                       "Facade, Struggle, Quick Attack, Extreme Speed, Aqua Jet, Flare Blitz, Brave Bird, "
                       "Volt Tackle, Wild Charge, Flame Charge, Giga Impact, Outrage, Thrash, Retaliate, "
                       "Last Resort, Superpower, Close Combat, Reversal, Flail, Endeavor, Covet, Feint, Fake Out, "
                       "Pursuit, Payback, Revenge, U-turn, Dig, Dive, Shadow Force, Spark, Chip Away, Trump Card, "
                       "Submission, Counter, Bide, Rage, Skull Bash, Double Hit, Beat Up, Dragon Rush, "
                       "Sucker Punch, Foul Play, Assurance, Knock Off, Thief, Secret Power, Smack Down, "
                       "Seismic Toss, Vital Throw, Storm Throw, Circle Throw, Fling, Natural Gift, Bolt Strike, "
                       "Fusion Bolt, V-create, Head Charge, Waterfall, Wood Hammer, Faint Attack, Punishment"),
    **_group('beam', "Charge Beam, Flash Cannon, Hydro Cannon, Luster Purge, Mirror Shot, Power Gem, Roar Of Time, "
                     "Aeroblast, Psystrike, Psycho Boost, Judgment, Techno Blast, Tri Attack, Spacial Rend, "
                     "Signal Beam, Blast Burn, Frenzy Plant, Psybeam, Aurora Beam, Solar Beam, Hyper Beam, "
                     "Ice Beam, Bubble Beam, Dragon Rage, Freeze Shock, Ice Burn"),
    **_group('orb', "Zap Cannon, Octazooka, Gunk Shot, Mud Shot, Searing Shot, Flame Burst, Fusion Flare, "
                    "Acid Spray, Ancient Power, Fire Blast, Electro Ball, Weather Ball, Energy Ball, Shadow Ball, "
                    "Aura Sphere, Focus Blast, Mist Ball, Sludge Bomb, Seed Bomb, Egg Bomb, Mud Bomb, "
                    "Magnet Bomb, Volt Switch, Hidden Power, Venoshock, Spit Up"),
    **_group('stream', "Flamethrower, Hydro Pump, Water Gun, Scald, Ember, Bubble, Sludge, Acid, Mud-Slap, "
                       "Dragon Breath, Incinerate, Inferno, Sacred Fire, Blue Flare, Overheat, Fire Pledge, "
                       "Grass Pledge, Fiery Dance"),
    **_group('hex', "Toxic, Thunder Wave, Hypnosis, Confuse Ray, Glare, Swagger, Flatter, Yawn, Taunt, Torment, "
                    "Encore, Disable, Embargo, Dark Void, Mean Look, Block, Heal Block, Gastro Acid, Worry Seed, "
                    "Soak, Simple Beam, Entrainment, Telekinesis, Quash, Imprison, Teeter Dance, Psycho Shift, "
                    "Trick, Switcheroo, Skill Swap, Role Play, Transform, Mimic, Sketch, Foresight, Odor Sleuth, "
                    "Miracle Eye, Lock-On, Mind Reader, Bestow, Reflect Type, Power Swap, Guard Swap, "
                    "Heart Swap, Guard Split, Power Split, Ally Switch, After You, Conversion, Conversion 2, "
                    "Camouflage, Baton Pass, Helping Hand, Metronome, Mirror Move, Copycat, Me First, Assist, "
                    "Sleep Talk, Nature Power, Recycle"),
    'Crush Grip': 'claw', 'Wring Out': 'whip', 'Grass Knot': 'whip', 'Rock Throw': 'rocks', 'Rock Tomb': 'rocks',
    'Bone Club': 'impact', 'Bonemerang': 'spin', 'Bone Rush': 'spin', 'Heart Stamp': 'punch',
    'Psychic': 'rings', 'Confusion': 'rings', 'Psyshock': 'rings', 'Thunder': 'bolt',
    'Thunderbolt': 'bolt', 'ThunderShock': 'bolt',
}

# Damaging moves by a word in their name, first match wins.
KEYWORDS = [
    ('punch', ('punch', 'uppercut', 'hammer arm', 'arm thrust', 'force palm', 'brick break', 'meteor mash',
               'smelling salt', 'wake-up slap')),
    ('kick', ('kick', 'stomp', 'low sweep')),
    ('bite', ('bite', 'fang', 'crunch')),
    ('drain', ('drain', 'leech')),
    ('claw', ('claw', 'scratch', 'fury swipes', 'vice grip', 'guillotine', 'crabhammer')),
    ('blade', ('slash', 'blade', 'cut', 'sword', 'chop', 'scissor', 'razor shell', 'aerial ace', 'false swipe',
               'cross poison')),
    ('jab', ('peck', 'horn', 'jab', 'sting', 'drill', 'needle arm', 'fury attack', 'smart strike')),
    ('whip', ('whip', 'tail', 'slam', 'wrap', 'bind', 'constrict', 'clamp')),
    ('tackle', ('tackle', 'take down', 'double-edge', 'head', 'charge', 'throw', 'toss', 'impact')),
    ('spin', ('rapid spin', 'gyro ball', 'rollout', 'ice ball', 'wheel', 'gear grind')),
    ('beam', ('beam', 'cannon')),
    ('orb', ('ball', 'bomb', 'sphere', 'blast', 'shot')),
    ('stream', ('thrower', 'pump', 'gun', 'breath', 'pledge')),
]

# Moves that heal the user from the damage they do: the life flows back.
DRAINING = {'Absorb', 'Mega Drain', 'Giga Drain', 'Leech Life', 'Drain Punch', 'Horn Leech', 'Dream Eater'}
SONGS = {'Sing', 'Perish Song', 'Grass Whistle', 'Round', 'Relic Song', 'Chatter', 'Echoed Voice'}
CROSSED = {'X-Scissor', 'Cross Chop', 'Cross Poison', 'Dual Chop', 'Secret Sword', 'Sacred Sword'}
POWDER_COLORS = {'Sleep Powder': (120, 168, 248), 'Stun Spore': (248, 216, 72), 'Poison Powder': (184, 96, 200),
                 'Spore': (168, 208, 96), 'Cotton Spore': (240, 240, 240), 'Rage Powder': (240, 96, 64),
                 'Sweet Scent': (248, 160, 200)}

# Ones aimed at the user themselves (no target needed).
SELF_STYLES = {'aura', 'buff', 'heal', 'shield', 'weather', 'room', 'explode'}

# style -> (duration ms, fraction of it at which the move reaches the target)
TIMING = {
    'flame': (900, 0.55), 'bubbles': (950, 0.6), 'leaves': (850, 0.6), 'swarm': (900, 0.6),
    'bolt': (650, 0.3), 'shards': (700, 0.5), 'rocks': (800, 0.55), 'rings': (750, 0.3),
    'wisps': (850, 0.5), 'claw': (480, 0.3), 'impact': (420, 0.15), 'aura': (900, 0.5),
    'punch': (700, 0.45), 'kick': (650, 0.45), 'bite': (650, 0.45), 'blade': (520, 0.35),
    'jab': (560, 0.3), 'volley': (900, 0.45), 'whip': (600, 0.45), 'tackle': (520, 0.25),
    'spin': (800, 0.55), 'vortex': (1050, 0.3), 'beam': (900, 0.3), 'orb': (850, 0.55),
    'stream': (950, 0.35), 'gas': (1000, 0.55), 'wave': (1150, 0.5), 'shimmer': (1000, 0.4),
    'pulse': (900, 0.3), 'quake': (1000, 0.2), 'erupt': (850, 0.4), 'meteor': (1000, 0.55),
    'storm': (1100, 0.4), 'sound': (850, 0.4), 'gust': (800, 0.55), 'drain': (1250, 0.25),
    'explode': (1100, 0.1), 'buff': (900, 0.5), 'debuff': (850, 0.5), 'heal': (1050, 0.5),
    'shield': (800, 0.4), 'hex': (950, 0.6), 'hearts': (950, 0.6), 'powder': (1000, 0.5),
    'web': (800, 0.5), 'weather': (1400, 0.5), 'hazard': (850, 0.6), 'room': (1000, 0.5),
}

WHITE = (248, 248, 248)
STAT_UP = (248, 128, 72)     # the games' colours for stats going up and down
STAT_DOWN = (96, 144, 248)
HEAL_GREEN = (120, 232, 144)
SHIELD_CYAN = (96, 216, 200)


def style_for(mtype, category, move=None):
    """The animation for a move: its flavour by name, else by type."""
    if move in MOVE_STYLE:
        return MOVE_STYLE[move]
    if category != 'Status' and move:
        name = move.lower()
        for style, words in KEYWORDS:
            if any(w in name for w in words):
                return style
    if category == 'Status':
        return 'aura'
    if mtype == 'Dark':
        return 'claw' if category == 'Physical' else 'wisps'
    if mtype == 'Normal' and category == 'Special':
        return 'rings'
    return STYLE_BY_TYPE.get(mtype, 'impact')


def _lerp(a, b, k):
    return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k


def _pt(p):
    return int(round(p[0])), int(round(p[1]))


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _blob(surf, pos, r, fill, core, edge):
    """A round flame/energy blob: dark rim, fill, bright core."""
    x, y = _pt(pos)
    pygame.draw.circle(surf, edge, (x, y), r + 1)
    pygame.draw.circle(surf, fill, (x, y), r)
    pygame.draw.circle(surf, core, (x, y + 1), max(1, r - 2))


_GLOWS = {}


def _glow(surf, pos, r, color, strength=1.0):
    """A soft light added over whatever's there (skipped over a chroma key,
    which it would tint)."""
    if ui.THEME['chroma'] or r < 2 or strength <= 0:
        return
    level = max(1, min(8, int(round(strength * 8))))
    key = (int(r), color, level)
    g = _GLOWS.get(key)
    if g is None:
        r = int(r)
        g = pygame.Surface((2 * r, 2 * r))
        for k in range(r, 0, -1):
            a = (1 - k / r) ** 1.6 * level / 8 * 0.75
            pygame.draw.circle(g, tuple(int(v * a) for v in color), (r, r), k)
        if len(_GLOWS) > 300:
            _GLOWS.clear()
        _GLOWS[key] = g
    x, y = _pt(pos)
    surf.blit(g, (x - g.get_width() // 2, y - g.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)


def _flash(surf, color, alpha):
    """The whole screen lit up for a moment."""
    if ui.THEME['chroma'] or alpha <= 0:
        return
    f = pygame.Surface(surf.get_size())
    f.fill(color)
    f.set_alpha(int(alpha))
    surf.blit(f, (0, 0))


def _star(surf, center, r, color):
    """A four-pointed hit star: coloured rim, white middle."""
    cx, cy = center
    if r < 2:
        return
    for rr, c in ((r + 1, ui.darken(color, 70)), (r, color), (max(1, r * 6 // 10), WHITE)):
        w = max(1, rr // 3)
        pts = [(cx, cy - rr), (cx + w, cy - w), (cx + rr, cy), (cx + w, cy + w),
               (cx, cy + rr), (cx - w, cy + w), (cx - rr, cy), (cx - w, cy - w)]
        pygame.draw.polygon(surf, c, [_pt(q) for q in pts])


def _ring(surf, center, r, color, width=1, squash=0.6):
    r = int(r)
    if r < 1:
        return
    h = max(2, int(r * 2 * squash))
    pygame.draw.ellipse(surf, color, (int(center[0]) - r, int(center[1]) - h // 2, 2 * r, h), width)


def _chevron(surf, x, y, up, color, size=4):
    """A stat arrow (^ or v), outlined."""
    d = -1 if up else 1
    pts = [(x - size, y - d * size // 2), (x, y + d * size // 2), (x + size, y - d * size // 2)]
    pts = [_pt(q) for q in pts]
    pygame.draw.lines(surf, ui.darken(color, 90), False, [(px, py + 1) for px, py in pts], 3)
    pygame.draw.lines(surf, color, False, pts, 2)


def _heart(surf, center, s, color):
    cx, cy = _pt(center)
    edge = ui.darken(color, 90)
    for c, grow in ((edge, 1), (color, 0)):
        r = max(1, s // 2 + grow)
        pygame.draw.circle(surf, c, (cx - s // 2, cy), r)
        pygame.draw.circle(surf, c, (cx + s // 2, cy), r)
        pygame.draw.polygon(surf, c, [(cx - s - grow, cy + 1), (cx + s + grow, cy + 1), (cx, cy + s + 2 + grow)])
    surf.fill(WHITE, (cx - s // 2 - 1, cy - 1, 1, 1))


def _note(surf, center, color):
    """An eighth note."""
    x, y = _pt(center)
    edge = ui.darken(color, 100)
    pygame.draw.ellipse(surf, edge, (x - 3, y, 6, 5))
    pygame.draw.ellipse(surf, color, (x - 2, y + 1, 4, 3))
    pygame.draw.line(surf, edge, (x + 2, y + 2), (x + 2, y - 7), 2)
    pygame.draw.line(surf, edge, (x + 2, y - 7), (x + 5, y - 4), 2)


def _plus(surf, center, s, color):
    x, y = _pt(center)
    edge = ui.darken(color, 100)
    pygame.draw.rect(surf, edge, (x - s - 1, y - 2, 2 * s + 3, 5))
    pygame.draw.rect(surf, edge, (x - 2, y - s - 1, 5, 2 * s + 3))
    pygame.draw.rect(surf, color, (x - s, y - 1, 2 * s + 1, 3))
    pygame.draw.rect(surf, color, (x - 1, y - s, 3, 2 * s + 1))


def _shard(surf, tip, back, half, fill, edge):
    """A long thin triangle from back (width 2*half) to tip."""
    ux, uy = back[0] - tip[0], back[1] - tip[1]
    n = math.hypot(ux, uy) or 1
    side = (-uy / n * half, ux / n * half)
    pts = [_pt(tip), _pt((back[0] + side[0], back[1] + side[1])), _pt((back[0] - side[0], back[1] - side[1]))]
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, edge, pts, 1)


class Effect:
    def __init__(self, mtype, category, src, dst, start, move=None):
        """src, dst: battler keys (user and target). start: when it begins
        (ms). move: its name, for the flavour."""
        self.move = move or ''
        self.mtype = mtype
        self.style = style_for(mtype, category, move)
        self.color = ui.TYPE_COLORS.get(mtype, (200, 200, 200))
        self.src, self.dst = src, dst
        self.start = start
        self.duration, lands = TIMING[self.style]
        self.impact = start + int(self.duration * lands)   # when it reaches the target
        self.lands = lands
        self.drains = self.move in DRAINING and self.style != 'drain'
        rng = random.Random(start)
        self.rng = rng
        self.parts = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random()) for _ in range(12)]
        self._layer = None
        self._cracks = None

    def draw(self, surf, t_ms, boxes):
        """boxes: key -> pygame.Rect of each battler's sprite this frame.
        Returns False once the effect is over."""
        p = (t_ms - self.start) / self.duration
        if p >= 1:
            return False
        src, dst = boxes.get(self.src), boxes.get(self.dst)
        if self.style in SELF_STYLES:
            dst = dst or src
        if p < 0 or src is None or dst is None:
            return True
        getattr(self, '_' + self.style)(surf, p, t_ms, src, dst)
        if self.drains and p >= self.lands:
            self._drain_orbs(surf, (p - self.lands) / (1 - self.lands), t_ms, src, dst)
        return True

    def shake(self, t_ms):
        """How far (dx, dy) the scene shakes for this effect right now."""
        p = (t_ms - self.start) / self.duration
        if not 0 <= p < 1:
            return 0, 0
        q = (p - self.lands) / (1 - self.lands)
        amp = 0
        if self.style == 'quake' and q >= 0:
            amp = 3 * (1 - q)
        elif self.style == 'explode':
            amp = 4 * (1 - p)
        elif self.style in ('tackle', 'meteor', 'erupt', 'punch', 'kick') and 0 <= q < 0.25:
            amp = 2 if self.style in ('meteor', 'erupt') else 1
        if amp < 0.5:
            return 0, 0
        ph = t_ms / 28.0
        return int(round(math.sin(ph * 1.7) * amp)), int(round(math.cos(ph * 2.3) * amp * 0.6))

    # Each style gets p (0..1 through the effect), the time, and the user's
    # and target's sprite boxes.

    def _after(self, p):
        """How far (0..1) through the part after it lands; -1 before."""
        return -1.0 if p < self.lands else (p - self.lands) / (1 - self.lands)

    def _travel(self, p, src, dst, i, stagger, arc=10):
        """Where particle i is on its way from src to dst (None if not
        launched yet or already there)."""
        k = (p / self.lands - i * stagger) / (1 - stagger * 3)
        if not 0 <= k <= 1:
            return None
        x, y = _lerp(src.center, dst.center, k)
        return x, y - math.sin(math.pi * k) * arc, k

    def _dir(self, src, dst):
        return 1 if dst.centerx >= src.centerx else -1

    # -- the type's own finish ------------------------------------------------

    def _type_burst(self, surf, center, q, reach=16, n=6):
        """A burst in the type's own style at center (q: 0..1 through it)."""
        if not 0 <= q < 1:
            return
        cx, cy = center
        c = self.color
        t = self.mtype
        parts = self.parts[:n]
        if t in ('Fire', 'Dragon'):
            hot, edge = ui.lighten(c, 110), ui.darken(c, 90)
            for dx, dy, s in parts:
                x, y = cx + dx * reach, cy + dy * reach * 0.4 - q * (10 + s * 14)
                _blob(surf, (x, y), max(1, int((1 - q) * (3 + s * 3))), c, hot, edge)
            _glow(surf, center, reach + 6, c, 1 - q)
        elif t == 'Ice':
            ice, edge = ui.lighten(c, 40), ui.darken(c, 110)
            for i, (dx, dy, s) in enumerate(parts):
                a = i * 2 * math.pi / n + dx
                r0, r1 = reach * q * 0.8, reach * (0.4 + q)
                tip = (cx + math.cos(a) * r1, cy + math.sin(a) * r1)
                back = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
                _shard(surf, tip, back, 2, ice, edge)
        elif t == 'Electric':
            for i, (dx, dy, s) in enumerate(parts):
                if (i + int(q * 10)) % 2:
                    continue
                a = i * 2 * math.pi / n + q * 3
                r = reach * (0.5 + q * 0.6)
                x0, y0 = cx + math.cos(a) * r * 0.4, cy + math.sin(a) * r * 0.4
                x1, y1 = cx + math.cos(a) * r, cy + math.sin(a) * r
                mid = ((x0 + x1) / 2 + dy * 4, (y0 + y1) / 2 + dx * 4)
                pts = [_pt((x0, y0)), _pt(mid), _pt((x1, y1))]
                pygame.draw.lines(surf, c, False, pts, 2)
                pygame.draw.lines(surf, WHITE, False, pts, 1)
            _glow(surf, center, reach + 4, c, 0.8 * (1 - q))
        elif t in ('Water', 'Poison'):
            rim, fill = ui.darken(c, 50), ui.lighten(c, 50)
            for dx, dy, s in parts:
                x = cx + dx * reach * (0.4 + q)
                y = cy - 4 + dy * 4 - math.sin(math.pi * min(1.0, q * 1.2)) * (8 + s * 8) + q * 6
                r = max(1, int(2 + s * 2 - q * 2))
                pygame.draw.circle(surf, fill, _pt((x, y)), r)
                pygame.draw.circle(surf, rim, _pt((x, y)), r, 1)
        elif t == 'Grass':
            vein = ui.darken(c, 80)
            for i, (dx, dy, s) in enumerate(parts):
                x, y = cx + dx * reach * (0.4 + q), cy + dy * reach * 0.5 + q * 6
                a = q * 6 + i
                ux, uy = math.cos(a) * 3, math.sin(a) * 3
                pts = [_pt((x + ux, y + uy)), _pt((x - uy * 0.5, y + ux * 0.5)), _pt((x - ux, y - uy)),
                       _pt((x + uy * 0.5, y - ux * 0.5))]
                pygame.draw.polygon(surf, c, pts)
                pygame.draw.polygon(surf, vein, pts, 1)
        elif t in ('Ghost', 'Dark'):
            pale = ui.lighten(c, 90)
            for i, (dx, dy, s) in enumerate(parts):
                a = i * 2 * math.pi / n + q * 4
                r = reach * (0.3 + q * 0.7)
                x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.6 - q * 8
                size = max(1, int(4 * (1 - q)))
                pygame.draw.rect(surf, ui.darken(c, 60), (int(x) - 1, int(y) - 1, size + 2, size + 2))
                pygame.draw.rect(surf, pale, (int(x), int(y), size, size))
        elif t in ('Rock', 'Ground'):
            dust = (200, 190, 170) if t == 'Ground' else ui.lighten(c, 30)
            for dx, dy, s in parts:
                x = cx + dx * reach * (0.3 + q)
                y = cy - math.sin(math.pi * q) * (8 + s * 8) + q * 8
                size = max(1, int(2 + s * 3 - q * 2))
                pygame.draw.rect(surf, ui.darken(c, 70), (int(x) - 1, int(y) - 1, size + 2, size + 2))
                pygame.draw.rect(surf, dust, (int(x), int(y), size, size))
        elif t == 'Psychic':
            for i in range(2):
                k = q * 1.4 - i * 0.3
                if 0 <= k < 1:
                    _ring(surf, center, 3 + reach * k, ui.lighten(c, 40) if i else c)
        elif t == 'Bug':
            for i, (dx, dy, s) in enumerate(parts):
                x = cx + dx * reach * (0.4 + q) + math.sin(q * 20 + i) * 2
                y = cy + dy * reach * 0.6 + math.cos(q * 17 + i) * 2
                pygame.draw.rect(surf, ui.darken(c, 70), (int(x) - 1, int(y) - 1, 4, 4))
                pygame.draw.rect(surf, ui.lighten(c, 30), (int(x), int(y), 2, 2))
        elif t in ('Steel', 'Flying', 'Normal'):
            for i, (dx, dy, s) in enumerate(parts[:4]):
                ui.sparkle(surf, int(cx + dx * reach), int(cy + dy * reach * 0.6), int(q * 900) + i * 150,
                           ui.lighten(c, 40))
            self._burst(surf, center, q, ui.darken(c, 30), reach)
        else:
            self._burst(surf, center, q, ui.darken(c, 40), reach, width=2)

    def _burst(self, surf, center, q, color, reach, width=1):
        """Eight short rays flying out from center (q: 0..1 through it)."""
        if not 0 <= q < 1:
            return
        cx, cy = center
        inner, outer = reach * q * 0.6, reach * (0.3 + q * 0.7)
        for i in range(8):
            a = i * math.pi / 4 + 0.2
            ux, uy = math.cos(a), math.sin(a)
            length = outer if i % 2 == 0 else outer * 0.7
            s = _pt((cx + ux * inner, cy + uy * inner))
            e = _pt((cx + ux * length, cy + uy * length))
            pygame.draw.line(surf, color, s, e, width + 1 if i % 2 == 0 else width)
            pygame.draw.line(surf, WHITE, s, e, 1)

    def _hit(self, surf, center, q, reach=18):
        """The moment of contact: a star and a ring, then the type's burst."""
        if not 0 <= q < 1:
            return
        if q < 0.35:
            k = q / 0.35
            _star(surf, _pt(center), int(4 + 8 * math.sin(math.pi * k)), self.color)
            _glow(surf, center, 16, WHITE, 1 - k)
        _ring(surf, center, 4 + reach * q, ui.lighten(self.color, 60) if q < 0.5 else self.color)
        self._type_burst(surf, center, q, reach)

    def _drain_orbs(self, surf, q, t_ms, src, dst, n=7):
        """Life flowing back from the target to the user."""
        c = ui.lighten(HEAL_GREEN if self.mtype in ('Grass', 'Bug', 'Normal', 'Fighting') else self.color, 30)
        edge = ui.darken(c, 90)
        for i in range(n):
            k = (q * 1.5 - i * 0.07)
            if not 0 <= k < 1:
                continue
            k = ui.ease_out(k)
            dx, dy, s = self.parts[i % 12]
            mid = ((src.centerx + dst.centerx) / 2 + dy * 20, (src.centery + dst.centery) / 2 - 24 + dx * 12)
            a, b = _lerp(dst.center, mid, k), _lerp(mid, src.center, k)
            pos = _lerp(a, b, k)
            pygame.draw.circle(surf, edge, _pt(pos), 3)
            pygame.draw.circle(surf, c, _pt(pos), 2)
            surf.fill(WHITE, (int(pos[0]), int(pos[1]) - 1, 1, 1))
        if q > 0.45:
            _glow(surf, src.center, 22, c, min(1.0, (q - 0.45) * 3) * (1 - q) * 2)
            for i, (dx, dy, s) in enumerate(self.parts[:3]):
                ui.sparkle(surf, int(src.centerx + dx * 14), int(src.centery + dy * 12), t_ms + i * 120, c)

    # -- by type ----------------------------------------------------------------

    def _flame(self, surf, p, t_ms, src, dst):
        c, hot, edge = self.color, ui.lighten(self.color, 110), ui.darken(self.color, 90)
        flick = (t_ms // 60) % 2
        if p < self.lands:
            for i in range(3):
                pos = self._travel(p, src, dst, i, 0.12, arc=14)
                if pos:
                    _glow(surf, pos[:2], 12, c, 0.7)
                    _blob(surf, pos[:2], 6 - i * 2 + flick, c, hot, edge)
            return
        q = self._after(p)
        _glow(surf, (dst.centerx, dst.bottom - 10), 26, c, 1 - q)
        for dx, dy, s in self.parts[:6]:
            rise = q * (16 + s * 14)
            x, y = dst.centerx + dx * 16, dst.bottom - 6 - rise + dy * 3
            _blob(surf, (x, y), max(1, int((1 - q) * (5 + s * 3))) + flick, c, hot, edge)

    def _bubbles(self, surf, p, t_ms, src, dst):
        rim = ui.darken(self.color, 50)
        fill = ui.lighten(self.color, 50)
        for i in range(6):
            pos = self._travel(p, src, dst, i, 0.09, arc=8)
            if pos:
                x, y, k = pos
                y += math.sin(k * 12 + i) * 4
                r = 3 + (i % 2) * 2
                pygame.draw.circle(surf, fill, _pt((x, y)), r)
                pygame.draw.circle(surf, rim, _pt((x, y)), r, 1)
                pygame.draw.rect(surf, WHITE, (int(x) - r // 2, int(y) - r // 2, 2, 2))
        if p >= self.lands:
            q = self._after(p)
            if q < 0.7:
                for dx, dy, s in self.parts[:5]:
                    x, y = dst.centerx + dx * 14, dst.centery + dy * 12
                    a, b = 2 + q * 4, 4 + q * 7
                    for ux, uy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        pygame.draw.line(surf, rim, _pt((x + ux * a, y + uy * a)), _pt((x + ux * b, y + uy * b)))

    def _leaves(self, surf, p, t_ms, src, dst):
        c, vein = self.color, ui.darken(self.color, 80)
        for i in range(4):
            pos = self._travel(p, src, dst, i, 0.1, arc=18 - i * 4)
            if not pos:
                continue
            x, y, k = pos
            a = k * 4 * math.pi + i
            ux, uy = math.cos(a), math.sin(a)
            pts = [_pt(q) for q in ((x + ux * 6, y + uy * 6), (x - uy * 3, y + ux * 3),
                                    (x - ux * 6, y - uy * 6), (x + uy * 3, y - ux * 3))]
            pygame.draw.polygon(surf, c, pts)
            pygame.draw.polygon(surf, vein, pts, 1)
            pygame.draw.line(surf, vein, pts[0], pts[2])
        if p >= self.lands:
            self._burst(surf, dst.center, self._after(p), ui.lighten(c, 60), 16)

    def _swarm(self, surf, p, t_ms, src, dst):
        c = ui.darken(self.color, 40)
        for i, (dx, dy, s) in enumerate(self.parts):
            k = min(1.0, max(0.0, p / self.lands - s * 0.3) / 0.7)
            if k <= 0:
                continue
            x, y = _lerp(src.center, dst.center, k)
            buzz = t_ms / 45 + i * 2
            x += dx * 10 + math.sin(buzz) * 3
            y += dy * 10 + math.cos(buzz * 1.3) * 3
            size = 3 if i % 3 else 2
            pygame.draw.rect(surf, ui.darken(c, 60), (int(x) - 1, int(y) - 1, size + 2, size + 2))
            pygame.draw.rect(surf, ui.lighten(c, 40) if i % 2 else c, (int(x), int(y), size, size))

    def _bolt(self, surf, p, t_ms, src, dst):
        big = self.move == 'Thunder'
        if p < 0.7 and (t_ms // 50) % 3:
            rng = random.Random(t_ms // 70)
            x, y = dst.centerx + rng.randint(-4, 4), max(0, dst.top - (90 if big else 60))
            pts = [(x, y)]
            steps = 7 if big else 6
            for j in range(1, steps + 1):
                ty = y + (dst.centery - y) * j / steps
                tx = dst.centerx + (rng.randint(-8, 8) if j < steps else 0)
                pts.append((tx, ty))
            pts = [_pt(q) for q in pts]
            _glow(surf, dst.center, 24 if big else 16, self.color, 0.9)
            pygame.draw.lines(surf, self.color, False, pts, 5 if big else 3)
            pygame.draw.lines(surf, WHITE, False, pts, 2 if big else 1)
            if big and p < 0.35:
                _flash(surf, (255, 250, 210), 90 * (1 - p / 0.35))
        if p >= self.lands:
            q = self._after(p)
            self._burst(surf, dst.center, q, ui.darken(self.color, 40), 18, width=2)
            self._type_burst(surf, dst.center, q, 14)

    def _shards(self, surf, p, t_ms, src, dst):
        ice, edge = ui.lighten(self.color, 30), ui.darken(self.color, 110)
        cx, cy = dst.center
        if p < self.lands:
            k = p / self.lands
            r = 38 * (1 - ui.ease_out(k)) + 4
            for i in range(6):
                a = i * math.pi / 3 + 0.3
                ux, uy = math.cos(a), math.sin(a)
                tip = (cx + ux * r, cy + uy * r)
                back = (cx + ux * (r + 11), cy + uy * (r + 11))
                _shard(surf, tip, back, 3, ice, edge)
                surf.set_at(_pt(_lerp(tip, back, 0.35)), WHITE)
        else:
            q = self._after(p)
            _glow(surf, (cx, cy), 20, ice, 1 - q)
            self._burst(surf, (cx, cy), q, edge, 20, width=2)

    def _rocks(self, surf, p, t_ms, src, dst):
        c = ui.darken(self.color, 30)
        hi, dust = ui.lighten(self.color, 40), (200, 190, 170)
        for i, (dx, dy, s) in enumerate(self.parts[:4]):
            k = (p - i * 0.08) / self.lands
            x = dst.centerx + dx * 14
            ground = dst.bottom - 4 + dy * 2
            if 0 <= k < 1:
                y = dst.top - 40 + (ground - dst.top + 40) * k * k
                size = 6 + int(s * 4)
                rx, ry = int(x) - size // 2, int(y) - size // 2
                pygame.draw.rect(surf, ui.darken(c, 70), (rx - 1, ry - 1, size + 2, size + 2))
                pygame.draw.rect(surf, c, (rx, ry, size, size))
                pygame.draw.line(surf, hi, (rx, ry), (rx + size - 2, ry))
                pygame.draw.line(surf, hi, (rx, ry), (rx, ry + size - 2))
            elif k >= 1:
                q = (p - i * 0.08 - self.lands) / 0.25   # dust puffs for a quarter of the effect
                if q < 1:
                    for side in (-1, 1):
                        pygame.draw.circle(surf, dust, (int(x + side * (3 + q * 8)), int(ground - q * 3)),
                                           max(1, int(3 * (1 - q))))

    def _rings(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        _glow(surf, (cx, cy), 22, self.color, 0.8 * math.sin(math.pi * p))
        for i in range(3):
            k = (p - i * 0.18) / 0.6
            if 0 <= k < 1:
                r = 4 + 28 * k
                c = ui.lighten(self.color, 40) if i % 2 else self.color
                wob = math.sin(t_ms / 50 + i) * 2
                pygame.draw.ellipse(surf, c, (int(cx - r - wob), int(cy - r * 2 / 3), int(2 * r + 2 * wob),
                                              int(r * 4 / 3)), 2 if k < 0.5 else 1)

    def _wisps(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        c, pale, dark = self.color, ui.lighten(self.color, 90), ui.darken(self.color, 60)
        if self.mtype == 'Fire':
            c, pale, dark = (96, 120, 248), (200, 220, 255), (40, 48, 120)   # Will-O-Wisp burns blue
        _glow(surf, (cx, cy), 24, c, 0.6 * math.sin(math.pi * p))
        for i in range(5):
            a = i * 2 * math.pi / 5 + p * 3 * math.pi
            r = 28 * (1 - p * 0.7)
            for trail in range(4):
                b = a - trail * 0.22
                x, y = cx + math.cos(b) * r, cy + math.sin(b) * r * 0.6
                size = 5 - trail
                if trail == 0:
                    pygame.draw.rect(surf, dark, (int(x) - 1, int(y) - 1, size + 2, size + 2))
                pygame.draw.rect(surf, pale if trail == 0 else c, (int(x), int(y), size, size))

    def _claw(self, surf, p, t_ms, src, dst):
        """Three raking streaks, tapered, leaving a glowing scar."""
        cx, cy = dst.center
        edge = ui.darken(self.color, 40) if sum(self.color) > 480 else ui.lighten(self.color, 30)
        d = self._dir(src, dst)
        for i in range(3):
            k = (p - i * 0.12) / 0.55
            if not 0 <= k < 1.4:
                continue
            ox = (i - 1) * 9
            a = (cx + ox - 14 * d, cy - 18)
            b = (cx + ox + 10 * d, cy + 16)
            if k >= 1:   # the scar fades
                fade = (k - 1) / 0.4
                pygame.draw.line(surf, ui.lighten(edge, int(60 * (1 - fade))), _pt(a), _pt(b), 1)
                continue
            head = min(1.0, k * 2)
            tail = max(0.0, k * 2 - 1)
            n = 6
            for j in range(n):
                u0 = tail + (head - tail) * j / n
                u1 = tail + (head - tail) * (j + 1) / n
                w = 1 + int(2 * math.sin(math.pi * (j + 0.5) / n))
                s, e = _pt(_lerp(a, b, u0)), _pt(_lerp(a, b, u1))
                s, e = (s[0] + int(math.sin(u0 * 3) * 2), s[1]), (e[0] + int(math.sin(u1 * 3) * 2), e[1])
                pygame.draw.line(surf, edge, s, e, w + 2)
                pygame.draw.line(surf, WHITE, s, e, w)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 14, 4)

    def _impact(self, surf, p, t_ms, src, dst):
        cx, cy = dst.center
        cx += int(self.parts[0][0] * 6)
        cy += int(self.parts[0][1] * 6)
        self._burst(surf, (cx, cy), p, ui.darken(self.color, 40), 20, width=2)
        if p < 0.5:
            r = 2 + int(4 * math.sin(math.pi * p * 2))
            _glow(surf, (cx, cy), 14, WHITE, 1 - p * 2)
            pygame.draw.circle(surf, ui.darken(self.color, 60), (cx, cy), r + 1)
            pygame.draw.circle(surf, WHITE, (cx, cy), r)

    def _aura(self, surf, p, t_ms, src, dst):
        cx, bottom = src.centerx, src.bottom
        c = ui.lighten(self.color, 50)
        r = int(6 + 20 * p)
        _glow(surf, src.center, 22, c, 0.6 * math.sin(math.pi * p))
        if p < 0.8:
            pygame.draw.ellipse(surf, c, (cx - r, bottom - 4 - r // 4, 2 * r, r // 2), 1)
        for i, (dx, dy, s) in enumerate(self.parts[:6]):
            k = (p * 1.3 - s * 0.3)
            if 0 <= k < 1:
                ui.sparkle(surf, int(cx + dx * 16), int(bottom - 6 - k * (src.height * 0.8)), t_ms + i * 90, c)

    # -- contact ----------------------------------------------------------------

    def _punch(self, surf, p, t_ms, src, dst):
        """A fist flies in, growing, and lands with a star."""
        c = ui.lighten(self.color, 30)
        edge = ui.darken(self.color, 100)
        if p < self.lands:
            k = ui.ease_out(p / self.lands)
            pos = _lerp(_lerp(src.center, dst.center, 0.45), dst.center, k)
            s = int(5 + 11 * k)
        else:
            q = self._after(p)
            if q > 0.4:
                self._hit(surf, dst.center, q)
                return
            pos = (dst.centerx + math.sin(q * 40) * 2, dst.centery)
            s = 16
            self._hit(surf, dst.center, q)
        x, y = _pt(pos)
        w, h = s, max(3, s * 8 // 10)
        r = pygame.Rect(0, 0, w, h)
        r.center = (x, y)
        rad = max(1, s // 4)
        if self.mtype in ('Fire', 'Electric', 'Ice', 'Fighting', 'Ghost', 'Dark', 'Psychic'):
            _glow(surf, r.center, s + 4, self.color, 0.8)
        pygame.draw.rect(surf, edge, r.inflate(2, 2), border_radius=rad)
        pygame.draw.rect(surf, c, r, border_radius=rad)
        for k in range(1, 4):
            kx = r.left + w * k // 4
            pygame.draw.line(surf, edge, (kx, r.top + 1), (kx, r.top + h // 2))
        pygame.draw.line(surf, ui.lighten(c, 70), (r.left + 2, r.top + 1), (r.right - 3, r.top + 1))
        thumb = pygame.Rect(r.left, r.top + h * 55 // 100, max(2, w * 7 // 10), max(2, h // 4))
        pygame.draw.rect(surf, edge, thumb.inflate(2, 2), border_radius=max(1, h // 8))
        pygame.draw.rect(surf, ui.lighten(c, 20), thumb, border_radius=max(1, h // 8))

    def _kick(self, surf, p, t_ms, src, dst):
        """A foot swings in on an arc with a trail, then a star."""
        d = self._dir(src, dst)
        c, edge = ui.lighten(self.color, 20), ui.darken(self.color, 100)
        pivot = (dst.centerx - d * 10, dst.top - 26)
        reach = math.hypot(dst.centerx - pivot[0], dst.centery - pivot[1])
        end = math.atan2(dst.centery - pivot[1], dst.centerx - pivot[0])
        k = ui.ease_out(min(1.0, p / self.lands))
        for ghost in (3, 2, 1, 0):
            kk = max(0.0, k - ghost * 0.12)
            a = end + d * (1.6 * (1 - kk))   # swung in from the user's side
            fx, fy = pivot[0] + math.cos(a) * reach, pivot[1] + math.sin(a) * reach
            if ghost:
                if p < self.lands:
                    pygame.draw.circle(surf, ui.lighten(self.color, 40 + ghost * 30), _pt((fx, fy)), 5 - ghost)
                continue
            if p >= self.lands and self._after(p) > 0.35:
                break
            foot = pygame.Rect(0, 0, 13, 6)
            foot.center = (int(fx) + d * 2, int(fy) + 3)
            leg = pygame.Rect(0, 0, 6, 10)
            leg.midbottom = (int(fx) - d * 2, int(fy) + 2)
            for rct in (leg, foot):
                pygame.draw.rect(surf, edge, rct.inflate(2, 2), border_radius=2)
            for rct in (leg, foot):
                pygame.draw.rect(surf, c, rct, border_radius=2)
            pygame.draw.line(surf, WHITE, (foot.left + 2, foot.top), (foot.right - 3, foot.top))
        if p >= self.lands:
            self._hit(surf, dst.center, self._after(p))

    def _bite(self, surf, p, t_ms, src, dst):
        """Two rows of teeth snap shut on the target."""
        cx, cy = dst.center
        fangs = 'fang' in self.move.lower() or self.move == 'Crunch'
        tooth = WHITE if self.mtype in ('Normal', 'Dark', 'Bug') else ui.lighten(self.color, 90)
        edge = (40, 32, 48)
        if p < self.lands:
            k = ui.ease_out(p / self.lands)
            gap, alpha_q = 20 * (1 - k) + 2, 0.0
        else:
            q = self._after(p)
            if q > 0.45:
                self._type_burst(surf, (cx, cy), q, 18)
                return
            gap, alpha_q = 2 + math.sin(q * 30) * 1, q
            self._type_burst(surf, (cx, cy), q, 18)
        width, n = 34, 6
        for down in (True, False):
            base = cy - gap if down else cy + gap
            for i in range(n):
                u = (i + 0.5) / n
                tx = cx - width / 2 + u * width
                curve = (u - 0.5) ** 2 * 14
                by = base - curve if down else base + curve
                size = 9 if fangs and i in (1, n - 2) else 6
                tip = (tx, by + size if down else by - size)
                half = width / n / 2
                pts = [_pt((tx - half, by)), _pt((tx + half, by)), _pt(tip)]
                pygame.draw.polygon(surf, tooth, pts)
                pygame.draw.polygon(surf, edge, pts, 1)
            gum = [(cx - width / 2 + u * width, (base - (u - 0.5) ** 2 * 14) if down else (base + (u - 0.5) ** 2 * 14))
                   for u in (0, 0.25, 0.5, 0.75, 1)]
            pygame.draw.lines(surf, ui.darken(self.color, 40), False, [_pt(g) for g in gum], 2)
        if alpha_q and alpha_q < 0.3:
            _glow(surf, (cx, cy), 18, self.color, 1 - alpha_q / 0.3)

    def _blade(self, surf, p, t_ms, src, dst):
        """A curved cut through the target (two crossing for X moves)."""
        cx, cy = dst.center
        edge = ui.darken(self.color, 30) if sum(self.color) > 480 else ui.lighten(self.color, 20)
        d = self._dir(src, dst)
        cuts = ((-1, 0.0), (1, 0.16)) if self.move in CROSSED else ((d, 0.0),)
        for side, delay in cuts:
            k = (p - delay) / 0.6
            if not 0 <= k < 1:
                continue
            head, tail = min(1.0, k * 1.8), max(0.0, k * 1.8 - 0.8)
            a, b = (cx - 18 * side, cy - 17), (cx + 18 * side, cy + 15)
            bend = (cx + 7 * side, cy - 7)   # bowed up and out, like a sword's sweep
            n, pts = 10, []
            for j in range(n + 1):
                u = tail + (head - tail) * j / n
                pts.append(_lerp(_lerp(a, bend, u), _lerp(bend, b, u), u))
            for j in range(n):
                w = 1 + int(3 * math.sin(math.pi * (j + 0.5) / n))
                pygame.draw.line(surf, ui.darken(edge, 60), _pt(pts[j]), _pt(pts[j + 1]), w + 2)
            for j in range(n):
                w = 1 + int(2 * math.sin(math.pi * (j + 0.5) / n))
                pygame.draw.line(surf, edge, _pt(pts[j]), _pt(pts[j + 1]), w + 1)
                pygame.draw.line(surf, WHITE, _pt(pts[j]), _pt(pts[j + 1]), max(1, w - 1))
        if p >= self.lands:
            q = self._after(p)
            if q < 0.4:
                _glow(surf, (cx, cy), 18, ui.lighten(self.color, 40), 1 - q / 0.4)
            self._type_burst(surf, (cx, cy), q, 14, 5)

    def _jab(self, surf, p, t_ms, src, dst):
        """Quick thrusts from a few angles, a spark at each tip."""
        cx, cy = dst.center
        d = self._dir(src, dst)
        fill, edge = ui.lighten(self.color, 50), ui.darken(self.color, 90)
        drill = 'drill' in self.move.lower()
        for i in range(3):
            k = (p - i * 0.16) / 0.4
            if not 0 <= k < 1:
                continue
            ang = math.pi + (i - 1) * 0.45 if d > 0 else (i - 1) * 0.45
            ux, uy = math.cos(ang), math.sin(ang)
            stab = math.sin(math.pi * min(1.0, k * 1.3))
            tip = (cx + ux * (14 - 12 * stab), cy + uy * (14 - 12 * stab))
            back = (tip[0] + ux * 16, tip[1] + uy * 16)
            _shard(surf, tip, back, 3, fill, edge)
            if drill:
                for j in range(3):
                    m = _lerp(tip, back, (j + 1) / 4 + (t_ms / 80 % 1) / 4)
                    pygame.draw.line(surf, edge, _pt((m[0] - uy * 2, m[1] + ux * 2)), _pt((m[0] + uy * 2, m[1] - ux * 2)))
            if k > 0.5:
                _star(surf, _pt(_lerp(tip, (cx, cy), 0.4)), int(5 * (1 - k)), self.color)
        if p >= self.lands:
            self._type_burst(surf, (cx, cy), self._after(p), 12, 4)

    def _volley(self, surf, p, t_ms, src, dst):
        """Rapid fire: needles, seeds, stars, leaves or coins, a spark per hit."""
        c, edge, hot = self.color, ui.darken(self.color, 90), ui.lighten(self.color, 70)
        move = self.move
        ang = math.atan2(dst.centery - src.centery, dst.centerx - src.centerx)
        ux, uy = math.cos(ang), math.sin(ang)
        for i in range(6):
            k = (p - i * 0.09) / 0.36
            dx, dy, s = self.parts[i]
            end = (dst.centerx + dx * 10, dst.centery + dy * 10)
            if 0 <= k < 1:
                x, y = _lerp(src.center, end, k)
                y -= math.sin(math.pi * k) * (4 + s * 6)
                if move in ('Swift',):
                    _star(surf, _pt((x, y)), 4, (248, 224, 96))
                elif move == 'Pay Day':
                    pygame.draw.circle(surf, (120, 88, 24), _pt((x, y)), 4)
                    pygame.draw.circle(surf, (248, 208, 72), _pt((x, y)), 3)
                    surf.fill(WHITE, (int(x) - 1, int(y) - 2, 1, 1))
                elif move == 'Present':
                    pygame.draw.rect(surf, edge, (int(x) - 4, int(y) - 4, 9, 9))
                    pygame.draw.rect(surf, (248, 120, 120), (int(x) - 3, int(y) - 3, 7, 7))
                    pygame.draw.line(surf, (248, 224, 96), (int(x), int(y) - 3), (int(x), int(y) + 3))
                elif move in ('Bullet Seed', 'Barrage'):
                    pygame.draw.ellipse(surf, edge, (int(x) - 3, int(y) - 2, 7, 5))
                    pygame.draw.ellipse(surf, hot if move == 'Barrage' else c, (int(x) - 2, int(y) - 1, 5, 3))
                elif move in ('Magical Leaf', 'Razor Leaf'):
                    a = k * 10 + i
                    lx, ly = math.cos(a) * 4, math.sin(a) * 4
                    pts = [_pt((x + lx, y + ly)), _pt((x - ly / 2, y + lx / 2)), _pt((x - lx, y - ly)),
                           _pt((x + ly / 2, y - lx / 2))]
                    pygame.draw.polygon(surf, (248, 160, 220) if move == 'Magical Leaf' else c, pts)
                    pygame.draw.polygon(surf, edge, pts, 1)
                elif move == 'Rock Blast':
                    pygame.draw.rect(surf, edge, (int(x) - 3, int(y) - 3, 7, 7))
                    pygame.draw.rect(surf, c, (int(x) - 2, int(y) - 2, 5, 5))
                else:   # needles and shards
                    _shard(surf, (x + ux * 5, y + uy * 5), (x - ux * 6, y - uy * 6), 2, hot, edge)
            elif 1 <= k < 1.5:
                _star(surf, _pt(end), int(5 * (1.5 - k) * 2), c)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 12, 4)

    def _whip(self, surf, p, t_ms, src, dst):
        """A lash curls in and cracks at its tip."""
        d = self._dir(src, dst)
        base = (dst.centerx - d * 44, dst.centery + 14)
        tipx = dst.centerx + d * 4
        c, edge = self.color, ui.darken(self.color, 90)
        k = min(1.0, p / self.lands)
        reach = ui.ease_out(k)
        pts = []
        n = 14
        for j in range(n + 1):
            u = j / n * reach
            x = base[0] + (tipx - base[0]) * u
            y = base[1] + (dst.centery - 6 - base[1]) * u - math.sin(u * math.pi) * 14
            y += math.sin(u * 9 - p * 20) * 4 * u
            pts.append(_pt((x, y)))
        if p < self.lands + (1 - self.lands) * 0.5 and len(pts) > 1:
            pygame.draw.lines(surf, edge, False, pts, 4)
            pygame.draw.lines(surf, c, False, pts, 2)
            pygame.draw.lines(surf, ui.lighten(c, 70), False, pts[::3], 1)
        if p >= self.lands:
            q = self._after(p)
            self._hit(surf, pts[-1], q, 14)

    def _tackle(self, surf, p, t_ms, src, dst):
        """Speed lines rush in, then a big hit and dust."""
        cx, cy = dst.center
        if p < self.lands:
            k = p / self.lands
            # the user's charge, glowing in the type for the elemental ones
            if self.mtype not in ('Normal', 'Fighting'):
                _glow(surf, src.center, 22, self.color, 0.9)
                self._type_burst(surf, src.center, k * 0.8, 10, 4)
            for i in range(10):
                a = i * 2 * math.pi / 10 + self.parts[i][0] * 0.2
                r1 = 46 - 30 * k
                r0 = r1 + 10 + self.parts[i][2] * 10
                s = (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.7)
                e = (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.7)
                pygame.draw.line(surf, ui.lighten(self.color, 50), _pt(s), _pt(e), 1)
            return
        q = self._after(p)
        if q < 0.3:
            _star(surf, (cx, cy), int(14 * math.sin(math.pi * q / 0.3)) + 3, self.color)
            _glow(surf, (cx, cy), 26, WHITE, 1 - q / 0.3)
        _ring(surf, (cx, cy), 6 + 26 * q, ui.lighten(self.color, 50), 2 if q < 0.5 else 1)
        self._type_burst(surf, (cx, cy), q, 20)
        dust = (210, 200, 180)
        for side in (-1, 1):
            if q < 0.6:
                pygame.draw.circle(surf, dust, (int(cx + side * (8 + q * 20)), int(dst.bottom - 4 - q * 4)),
                                   max(1, int(4 * (1 - q / 0.6))))

    def _spin(self, surf, p, t_ms, src, dst):
        """A spinning wheel rolls in and strikes."""
        c, edge = self.color, ui.darken(self.color, 90)
        if p < self.lands:
            k = ui.ease_out(p / self.lands)
            start = (src.centerx, src.bottom - 8)
            x, y = _lerp(start, dst.center, k)
            y -= math.sin(math.pi * k) * 10
            a = t_ms / 40
            for ghost in (2, 1):
                gx, gy = _lerp(start, dst.center, max(0.0, k - ghost * 0.08))
                pygame.draw.circle(surf, ui.lighten(c, 30 + ghost * 25), _pt((gx, gy - math.sin(math.pi * k) * 10)), 7, 1)
            _glow(surf, (x, y), 14, c, 0.6)
            pygame.draw.circle(surf, edge, _pt((x, y)), 8)
            pygame.draw.circle(surf, c, _pt((x, y)), 7)
            for j in range(4):
                b = a + j * math.pi / 2
                pygame.draw.line(surf, WHITE, _pt((x, y)), _pt((x + math.cos(b) * 6, y + math.sin(b) * 6)), 1)
            pygame.draw.circle(surf, ui.lighten(c, 80), _pt((x, y)), 2)
            return
        q = self._after(p)
        self._hit(surf, dst.center, q, 18)
        for j in range(2):
            a = q * 8 + j * math.pi
            pygame.draw.arc(surf, ui.lighten(c, 50), (dst.centerx - 18, dst.centery - 10, 36, 20), a, a + 1.6, 1)

    def _vortex(self, surf, p, t_ms, src, dst):
        """A spiral of the type's stuff whirls around the target, rising."""
        cx, bottom = dst.centerx, dst.bottom
        c = self.color
        grow = _clamp(p / 0.2) * _clamp((1 - p) / 0.2)
        if self.move == 'Hurricane' or self.mtype == 'Flying' or self.move == 'Twister':
            c = (220, 236, 248) if self.mtype == 'Flying' else c
        edge, hot = ui.darken(c, 80), ui.lighten(c, 80)
        _glow(surf, (cx, bottom - dst.height // 2), 24, c, 0.5 * grow)
        for layer in range(5):
            ly = bottom - 4 - layer * (dst.height / 5) - p * 4
            rx = (12 + layer * 3) * grow
            for j in range(5):
                a = t_ms / 90.0 + j * 2 * math.pi / 5 + layer * 0.7
                x, y = cx + math.cos(a) * rx, ly + math.sin(a) * rx * 0.3
                front = math.sin(a) > 0
                if self.mtype == 'Fire':
                    _blob(surf, (x, y), 2 + front, c if front else ui.darken(c, 40), hot, edge)
                elif self.mtype == 'Grass':
                    pygame.draw.polygon(surf, c if front else ui.darken(c, 40),
                                        [_pt((x - 3, y)), _pt((x, y - 2)), _pt((x + 3, y)), _pt((x, y + 2))])
                else:
                    size = 3 if front else 2
                    pygame.draw.rect(surf, edge, (int(x) - 1, int(y) - 1, size + 2, size + 2))
                    pygame.draw.rect(surf, hot if front else c, (int(x), int(y), size, size))
        if self.mtype in ('Flying', 'Dragon') or self.move in ('Twister', 'Hurricane'):
            for j in range(3):
                a = t_ms / 70.0 + j * 2.1
                r = pygame.Rect(0, 0, int(30 * grow) + 2, int(10 * grow) + 2)
                r.center = (cx, bottom - 8 - j * 12)
                pygame.draw.arc(surf, WHITE, r, a, a + 2.2, 1)

    # -- ranged -----------------------------------------------------------------

    def _beam(self, surf, p, t_ms, src, dst):
        """A charge, then a beam from the user to the target."""
        charge = 0.3 if self.move in ('Solar Beam', 'Hyper Beam', 'Giga Impact', 'Psystrike') else 0.15
        sx, sy = src.center
        tx, ty = dst.center
        c = self.color
        if p < charge:
            k = p / charge
            _glow(surf, (sx, sy), 6 + 14 * k, c, k)
            for i, (dx, dy, s) in enumerate(self.parts[:8]):
                r = 26 * (1 - k) + 2
                a = i * math.pi / 4 + k * 2
                surf.fill(ui.lighten(c, 70), (int(sx + math.cos(a) * r), int(sy + math.sin(a) * r * 0.7), 2, 2))
            pygame.draw.circle(surf, WHITE, (sx, sy), max(1, int(4 * k)))
            return
        k = (p - charge) / (1 - charge)
        width = 9 * math.sin(math.pi * min(1.0, k * 1.15)) + 1
        reach = min(1.0, k * 4)
        ex, ey = sx + (tx - sx) * reach, sy + (ty - sy) * reach
        if self.move == 'Aurora Beam':
            hue = (t_ms // 60) % 6
            c = [(248, 96, 96), (248, 200, 72), (120, 232, 120), (96, 200, 248), (160, 120, 248), (248, 120, 200)][hue]
        layers = ((width + 2, ui.darken(c, 60)), (width, c), (width * 0.55, ui.lighten(c, 80)), (width * 0.25, WHITE))
        for w, col in layers:
            if w >= 1:
                pygame.draw.line(surf, col, (sx, sy), _pt((ex, ey)), max(1, int(w)))
        _glow(surf, (sx, sy), 10 + width, c, 0.8)
        if self.move in ('Psybeam', 'Signal Beam', 'Bubble Beam'):
            for j in range(5):
                u = ((t_ms / 300.0) + j / 5) % 1 * reach
                mx, my = sx + (tx - sx) * u, sy + (ty - sy) * u
                if self.move == 'Bubble Beam':
                    pygame.draw.circle(surf, ui.lighten(c, 60), _pt((mx, my - 4)), 3, 1)
                else:
                    _ring(surf, (mx, my), 5, ui.lighten(c, 60) if j % 2 else WHITE, 1, 1.0)
        elif self.mtype == 'Ice':
            for j in range(4):
                u = ((t_ms / 400.0) + j / 4) % 1 * reach
                mx, my = sx + (tx - sx) * u, sy + (ty - sy) * u
                _star(surf, _pt((mx, my - 5)), 3, c)
        if reach >= 1:
            _glow(surf, (tx, ty), 14 + width * 1.5, c, 1.0)
            _ring(surf, (tx, ty), 6 + width * 1.5 + math.sin(t_ms / 40) * 2, ui.lighten(c, 60))
            if k > 0.7:
                self._type_burst(surf, (tx, ty), (k - 0.7) / 0.3, 18)
        if self.move in ('Hyper Beam', 'Psystrike', 'Roar Of Time') and 0.2 < k < 0.4:
            _flash(surf, ui.lighten(c, 80), 70)

    def _orb(self, surf, p, t_ms, src, dst):
        """A big orb flies over (motes circling it) and bursts."""
        c = (96, 152, 248) if self.move == 'Aura Sphere' else self.color
        edge, hot = ui.darken(c, 90), ui.lighten(c, 80)
        big = self.move in ('Aura Sphere', 'Focus Blast', 'Shadow Ball', 'Zap Cannon', 'Fire Blast', 'Energy Ball',
                            'Fusion Flare', 'Searing Shot', 'Sludge Bomb', 'Gunk Shot')
        r = 7 if big else 5
        if p < self.lands:
            k = p / self.lands
            if k < 0.25:   # it forms in front of the user
                pos = src.center
                r = max(1, int(r * k / 0.25))
            else:
                kk = ui.ease_out((k - 0.25) / 0.75)
                x, y = _lerp(src.center, dst.center, kk)
                pos = (x, y - math.sin(math.pi * kk) * 12)
                for ghost in (3, 2, 1):
                    gk = max(0.0, kk - ghost * 0.06)
                    gx, gy = _lerp(src.center, dst.center, gk)
                    pygame.draw.circle(surf, ui.lighten(c, 20 * ghost), _pt((gx, gy - math.sin(math.pi * gk) * 12)),
                                       max(1, r - ghost))
            _glow(surf, pos, r * 3, c, 0.9)
            pygame.draw.circle(surf, edge, _pt(pos), r + 1)
            pygame.draw.circle(surf, c, _pt(pos), r)
            a = t_ms / 70.0
            pygame.draw.arc(surf, hot, (int(pos[0]) - r + 1, int(pos[1]) - r + 1, 2 * r - 2, 2 * r - 2), a, a + 2.2, 2)
            surf.fill(WHITE, (int(pos[0]) - r // 3, int(pos[1]) - r // 3, 2, 2))
            for j in range(3):
                b = -a * 1.3 + j * 2.1
                surf.fill(hot, (int(pos[0] + math.cos(b) * (r + 4)), int(pos[1] + math.sin(b) * (r + 4) * 0.6), 2, 2))
            return
        q = self._after(p)
        cx, cy = dst.center
        if q < 0.5:
            rr = int(6 + 18 * q / 0.5)
            _glow(surf, (cx, cy), rr + 10, c, 1 - q / 0.5)
            pygame.draw.circle(surf, c, (cx, cy), rr, 3)
            pygame.draw.circle(surf, hot, (cx, cy), max(1, rr - 4), 1)
        self._type_burst(surf, (cx, cy), q, 22, 8)
        if q < 0.2:
            _flash(surf, hot, 50 * (1 - q / 0.2))

    def _stream(self, surf, p, t_ms, src, dst):
        """A steady jet from the user to the target, splashing on it."""
        c, edge, hot = self.color, ui.darken(self.color, 90), ui.lighten(self.color, 100)
        head = _clamp(p / self.lands)
        tail = _clamp((p - 0.75) / 0.2)
        n = 14
        sx, sy = src.center
        tx, ty = dst.center
        nx, ny = -(ty - sy), tx - sx
        nl = math.hypot(nx, ny) or 1
        nx, ny = nx / nl, ny / nl
        flick = (t_ms // 60) % 2
        for j in range(n):
            u = ((t_ms / 420.0) + j / n) % 1
            if not tail <= u <= head:
                continue
            x, y = sx + (tx - sx) * u, sy + (ty - sy) * u - math.sin(math.pi * u) * 6
            wob = math.sin(u * 14 + t_ms / 70 + j) * (1 + 3 * u)
            x, y = x + nx * wob, y + ny * wob
            r = int(2 + 3 * u)
            if self.mtype in ('Fire', 'Dragon'):
                _blob(surf, (x, y), r + flick, c, hot, edge)
            elif self.mtype in ('Water', 'Ice'):
                pygame.draw.circle(surf, edge, _pt((x, y)), r + 1)
                pygame.draw.circle(surf, ui.lighten(c, 30), _pt((x, y)), r)
                surf.fill(WHITE, (int(x) - 1, int(y) - 1, 1, 1))
            else:
                pygame.draw.circle(surf, edge, _pt((x, y)), r + 1)
                pygame.draw.circle(surf, c, _pt((x, y)), r)
                pygame.draw.circle(surf, ui.lighten(c, 50), _pt((x - 1, y - 1)), max(1, r - 2))
        _glow(surf, (sx, sy), 12, c, 0.7 * (1 - tail))
        if p >= self.lands:
            q = (p - self.lands) / (1 - self.lands)
            _glow(surf, (tx, ty), 20, c, 0.8 * (1 - q))
            self._type_burst(surf, (tx, ty), (q * 2.5) % 1, 16, 5)

    def _gas(self, surf, p, t_ms, src, dst):
        """Billowing puffs drift over and hang around the target."""
        c = self.color
        if self.move == 'Sand Attack':
            c = (216, 192, 128)
        elif self.move in ('Smoke Screen', 'Haze'):
            c = (120, 120, 132)
        fill, edge = ui.lighten(c, 40), ui.darken(c, 50)
        for i, (dx, dy, s) in enumerate(self.parts[:8]):
            k = _clamp((p - i * 0.04) / self.lands)
            if k <= 0:
                continue
            x, y = _lerp(src.center, dst.center, ui.ease_out(k))
            x += dx * 14 * k + math.sin(t_ms / 200 + i) * 2
            y += dy * 10 * k - math.sin(math.pi * k) * 8
            r = int(3 + 6 * k * (0.6 + s * 0.6))
            if p > 0.8:
                r = int(r * (1 - (p - 0.8) / 0.2))
            if r >= 1:
                pygame.draw.circle(surf, edge, _pt((x, y)), r + 1)
                pygame.draw.circle(surf, fill, _pt((x, y)), r)
                pygame.draw.circle(surf, ui.lighten(fill, 30), _pt((x - r / 3, y - r / 3)), max(1, r // 2))

    def _wave(self, surf, p, t_ms, src, dst):
        """A great wave rolls across the field."""
        w, h = surf.get_size()
        if self._layer is None or self._layer.get_size() != (w, h):
            self._layer = pygame.Surface((w, h), pygame.SRCALPHA)
        layer = self._layer
        layer.fill((0, 0, 0, 0))
        d = self._dir(src, dst)
        c = self.color
        X = -40 + p * (w + 120)
        if d < 0:
            X = w - X
        top = dst.top - 12
        low = h - 14   # the water behind the crest, sloping down to here
        back = 220

        def fx(b):   # b pixels behind the crest, as x
            return X - d * b

        pts = [(fx(back + 400), h), (fx(back + 400), low)]
        for j in range(21):
            b = back * (1 - j / 20)
            y = top + (low - top) * (b / back) ** 0.75 + math.sin(b / 9 + t_ms / 110) * 2
            pts.append((fx(b), y))
        # the lip curling over, then the face dropping away in front
        pts += [(fx(-8), top + 4), (fx(-10), top + 10), (fx(-5), top + 13), (fx(-9), top + 28), (fx(-22), h)]
        pygame.draw.polygon(layer, (*c, 135), [_pt(q) for q in pts])
        crest = [_pt(q) for q in pts[14:-3]]
        pygame.draw.lines(layer, (*ui.lighten(c, 80), 230), False, crest, 3)
        for j in range(5):   # streaks in the body
            b = (j * 37 + t_ms / 8) % back
            y = top + (low - top) * (b / back) ** 0.75 + 8 + j * 6
            layer.fill((*ui.lighten(c, 60), 110), (int(fx(b)) - 8, int(y), 16, 1))
        for j in range(8):   # foam riding the crest
            b = (j / 8 + t_ms / 900) % 1 * 36
            fy = top + (low - top) * (b / back) ** 0.75 - 1
            layer.fill((255, 255, 255, 230), (int(fx(b)), int(fy), 2, 2))
        for dx, dy, s in self.parts[:6]:   # spray off the lip
            sx = fx(-(6 + s * 14))
            sy = top - 4 - abs(dy) * 10 + math.sin(t_ms / 80 + dx) * 2
            layer.fill((255, 255, 255, 200), (int(sx), int(sy), 2, 2))
        surf.blit(layer, (0, 0))
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 16, 6)

    def _shimmer(self, surf, p, t_ms, src, dst):
        """Wavy bands of heat (or cold) sweep across the field."""
        w, h = surf.get_size()
        d = self._dir(src, dst)
        c = ui.lighten(self.color, 50)
        fade = _clamp(p / 0.15) * _clamp((1 - p) / 0.2)
        for band in range(6):
            y0 = dst.top - 10 + band * (dst.height + 30) / 6
            front = (p * 1.6 - band * 0.05) * (w + 40)
            pts = []
            for j in range(0, 60, 4):
                x = (front - j * 3) if d > 0 else (w - front + j * 3)
                pts.append(_pt((x, y0 + math.sin(j / 6 + t_ms / 90 + band) * 3)))
            if fade > 0.2:
                pygame.draw.lines(surf, c if band % 2 else WHITE, False, pts, 1)
        _glow(surf, dst.center, 26, self.color, 0.7 * fade)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 18, 6)

    def _pulse(self, surf, p, t_ms, src, dst):
        """Rings of power rush out from the user."""
        sx, sy = src.center
        c = self.color
        reach = math.hypot(dst.centerx - sx, dst.centery - sy) + 30
        _glow(surf, (sx, sy), 20, c, 0.9 * (1 - p))
        for i in range(4):
            k = (p - i * 0.12) / 0.6
            if not 0 <= k < 1:
                continue
            r = 6 + reach * k
            col = WHITE if i % 2 else ui.lighten(c, 40)
            _ring(surf, (sx, sy), r, ui.darken(c, 50), 3, 0.7)
            _ring(surf, (sx, sy), r, col, 1, 0.7)
            if self.mtype == 'Electric' and i == 0:
                for j in range(6):
                    a = j * math.pi / 3 + t_ms / 200
                    x, y = sx + math.cos(a) * r, sy + math.sin(a) * r * 0.7
                    pygame.draw.lines(surf, c, False, [_pt((x - 3, y - 2)), _pt((x, y + 1)), _pt((x + 3, y - 2))], 1)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 16, 6)

    # -- ground and sky ----------------------------------------------------------

    def _quake(self, surf, p, t_ms, src, dst):
        """The ground cracks under the target; dust everywhere."""
        if self._cracks is None:
            rng = random.Random(self.start + 7)
            self._cracks = []
            for i in range(5):
                x, y = 0.0, 0.0
                side = -1 if i % 2 else 1
                pts = [(x, y)]
                for _ in range(6):
                    x += side * rng.uniform(3, 7)
                    y += rng.uniform(-2, 2)
                    pts.append((x, y))
                self._cracks.append(pts)
        q = self._after(p)
        gx, gy = dst.centerx, dst.bottom - 2
        dark = (40, 30, 24)
        grow = _clamp((p / self.lands) if q < 0 else 1)
        fade = 1 - _clamp((p - 0.8) / 0.2)
        if fade > 0:
            for pts in self._cracks:
                n = max(2, int(len(pts) * grow))
                seg = [_pt((gx + x * (1.4 if self.move == 'Fissure' else 1), gy + y)) for x, y in pts[:n]]
                pygame.draw.lines(surf, dark, False, seg, 3 if self.move == 'Fissure' else 2)
                pygame.draw.lines(surf, (150, 120, 90), False, [(sx, sy - 1) for sx, sy in seg], 1)
        dust = (214, 196, 160)
        for i, (dx, dy, s) in enumerate(self.parts[:8]):
            k = (p * 1.2 - s * 0.3)
            if 0 <= k < 1:
                x = gx + dx * 34
                y = gy - k * (10 + s * 10)
                pygame.draw.circle(surf, dust, _pt((x, y)), max(1, int(4 * (1 - k))))
        if q >= 0 and q < 0.6:
            for dx, dy, s in self.parts[8:12]:
                x = gx + dx * 20
                y = gy - math.sin(math.pi * q / 0.6) * (12 + s * 10)
                pygame.draw.rect(surf, (120, 96, 64), (int(x), int(y), 3, 3))

    def _erupt(self, surf, p, t_ms, src, dst):
        """Spikes of stone (or a pillar of light) burst up under the target."""
        gx, gy = dst.centerx, dst.bottom - 2
        c, edge = self.color, ui.darken(self.color, 90)
        if self.mtype == 'Rock' or self.move == 'Stone Edge':
            for i, (dx, dy, s) in enumerate(self.parts[:5]):
                k = (p - i * 0.06) / 0.35
                if k <= 0:
                    continue
                hgt = (14 + s * 16) * ui.ease_out(min(1.0, k)) * (1 - _clamp((p - 0.8) / 0.2))
                x = gx + (i - 2) * 9 + dx * 3
                if hgt >= 1:
                    pts = [_pt((x - 4, gy)), _pt((x + 1, gy - hgt)), _pt((x + 4, gy))]
                    pygame.draw.polygon(surf, ui.lighten(c, 20), pts)
                    pygame.draw.polygon(surf, edge, pts, 1)
                    pygame.draw.line(surf, ui.lighten(c, 70), pts[0], pts[1])
        else:
            k = _clamp(p / self.lands)
            fade = 1 - _clamp((p - 0.6) / 0.4)
            hgt = int((dst.height + 20) * ui.ease_out(k))
            col = pygame.Rect(0, 0, int(16 * fade) + 2, hgt)
            col.midbottom = (gx, gy)
            _glow(surf, (gx, gy - hgt // 2), max(4, hgt // 2), c, fade)
            pygame.draw.rect(surf, ui.lighten(c, 30), col)
            pygame.draw.rect(surf, WHITE, col.inflate(-col.width * 2 // 3, 0))
            for dx, dy, s in self.parts[:6]:
                y = gy - k * (dst.height + 30) * s
                pygame.draw.rect(surf, edge, (int(gx + dx * 14), int(y), 3, 3))
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 16, 5)

    def _meteor(self, surf, p, t_ms, src, dst):
        """Things fall on the target from the sky, trailing."""
        d = self._dir(src, dst)
        c, edge, hot = self.color, ui.darken(self.color, 90), ui.lighten(self.color, 90)
        for i, (dx, dy, s) in enumerate(self.parts[:5]):
            k = (p - i * 0.07) / self.lands
            end = (dst.centerx + dx * 16, dst.centery + dy * 10)
            start = (end[0] + d * 50, -16)
            if 0 <= k < 1:
                k = k * k
                x, y = _lerp(start, end, k)
                tx, ty = _lerp(start, end, max(0.0, k - 0.18))
                pygame.draw.line(surf, ui.lighten(c, 40), _pt((tx, ty)), _pt((x, y)), 3)
                pygame.draw.line(surf, WHITE, _pt(_lerp((tx, ty), (x, y), 0.5)), _pt((x, y)), 1)
                if self.mtype == 'Ice':
                    _shard(surf, (x, y + 6), (x + d * 4, y - 8), 3, hot, edge)
                elif self.mtype in ('Rock', 'Ground'):
                    size = 6 + int(s * 4)
                    pygame.draw.rect(surf, edge, (int(x) - size // 2 - 1, int(y) - size // 2 - 1, size + 2, size + 2))
                    pygame.draw.rect(surf, c, (int(x) - size // 2, int(y) - size // 2, size, size))
                else:
                    _glow(surf, (x, y), 10, c, 0.8)
                    _blob(surf, (x, y), 4, c, hot, edge)
            elif k >= 1:
                q = (p - i * 0.07 - self.lands) / 0.3
                if q < 1:
                    _star(surf, _pt(end), int(6 * (1 - q)) + 1, c)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 20, 8)

    def _storm(self, surf, p, t_ms, src, dst):
        """A screen-wide blizzard, the target caught in the middle."""
        w, h = surf.get_size()
        d = self._dir(src, dst)
        fade = _clamp(p / 0.15) * _clamp((1 - p) / 0.2)
        rng = random.Random(self.start)
        c = ui.lighten(self.color, 60)
        for i in range(46):
            sx, sy, sp = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.7, 1.3)
            x = (sx + d * t_ms * 0.25 * sp) % (w + 20) - 10
            y = (sy + t_ms * 0.12 * sp) % (h + 20) - 10
            if rng.random() < fade:
                pygame.draw.line(surf, c if i % 3 else WHITE, (int(x), int(y)), (int(x - d * 4), int(y - 2)), 1)
                surf.fill(WHITE, (int(x), int(y), 2, 2))
        _flash(surf, (230, 244, 255), 60 * fade)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 20, 8)

    def _sound(self, surf, p, t_ms, src, dst):
        """Sound waves (or notes, for songs) carry over to the target."""
        sx, sy = src.center
        tx, ty = dst.center
        dist = math.hypot(tx - sx, ty - sy)
        aim = math.atan2(ty - sy, tx - sx)
        c = ui.lighten(self.color, 60)
        if self.move in SONGS:
            for i in range(4):
                k = (p - i * 0.12) / 0.7
                if not 0 <= k < 1:
                    continue
                x, y = _lerp((sx, sy), (tx, ty), k)
                y += math.sin(k * 10 + i) * 6 - math.sin(math.pi * k) * 10
                _note(surf, (x, y), (248, 176, 224) if i % 2 else c)
            if p >= self.lands:
                for i, (dx, dy, s) in enumerate(self.parts[:4]):
                    ui.sparkle(surf, int(tx + dx * 16), int(ty + dy * 12), t_ms + i * 110, c)
            return
        jag = self.move in ('Screech', 'Metal Sound', 'Bug Buzz', 'Snarl', 'Sonic Boom')
        for i in range(5):
            k = (p - i * 0.1) / 0.6
            if not 0 <= k < 1:
                continue
            r = 8 + dist * k
            rect = pygame.Rect(0, 0, int(2 * r), int(2 * r))
            rect.center = (sx, sy)
            # pygame's arcs run counter-clockwise with y up
            a0, a1 = -aim - 0.45, -aim + 0.45
            if jag:
                pts = []
                for j in range(9):
                    a = aim - 0.45 + 0.9 * j / 8
                    rr = r + (3 if j % 2 else -3)
                    pts.append(_pt((sx + math.cos(a) * rr, sy + math.sin(a) * rr)))
                pygame.draw.lines(surf, ui.darken(c, 80), False, pts, 3)
                pygame.draw.lines(surf, c if i % 2 else WHITE, False, pts, 1)
            else:
                pygame.draw.arc(surf, ui.darken(c, 80), rect, a0, a1, 3)
                pygame.draw.arc(surf, c if i % 2 else WHITE, rect, a0, a1, 1)
        if p >= self.lands:
            self._type_burst(surf, dst.center, self._after(p), 14, 4)

    def _gust(self, surf, p, t_ms, src, dst):
        """Crescents of wind slice over, then swirl around the target."""
        c = (232, 244, 248) if self.mtype in ('Flying', 'Normal') else ui.lighten(self.color, 70)
        edge = ui.darken(self.color, 40)
        for i in range(3):
            pos = self._travel(p, src, dst, i, 0.1, arc=6 + i * 6)
            if not pos:
                continue
            x, y, k = pos
            y += math.sin(k * 8 + i * 2) * 5
            ang = math.atan2(dst.centery - src.centery, dst.centerx - src.centerx)
            r = pygame.Rect(0, 0, 14, 14)
            r.center = (int(x), int(y))
            pygame.draw.arc(surf, edge, r.move(1, 1), -ang - 1.3, -ang + 1.3, 3)
            pygame.draw.arc(surf, c, r, -ang - 1.3, -ang + 1.3, 2)
        if p >= self.lands:
            q = self._after(p)
            for j in range(3):
                a = q * 10 + j * 2.1
                rr = pygame.Rect(0, 0, int(36 - 14 * q), int(16 - 6 * q))
                rr.center = (dst.centerx, dst.centery + (j - 1) * 8)
                pygame.draw.arc(surf, c, rr, a, a + 2.4, 1)
            self._type_burst(surf, dst.center, q, 14, 4)

    def _drain(self, surf, p, t_ms, src, dst):
        """The target glows and its life flows back to the user."""
        k = _clamp(p / self.lands)
        c = HEAL_GREEN if self.mtype in ('Grass', 'Bug') else self.color
        if p < self.lands + 0.1:
            _glow(surf, dst.center, 22, c, math.sin(math.pi * k))
            if self.move == 'Leech Seed':
                x, y = _lerp(src.center, dst.center, k)
                pygame.draw.ellipse(surf, (96, 72, 40), (int(x) - 3, int(y - math.sin(math.pi * k) * 14) - 2, 6, 5))
            else:
                _ring(surf, dst.center, 20 * (1 - k) + 3, ui.lighten(c, 40))
        self._drain_orbs(surf, max(0.0, self._after(p)), t_ms, src, dst, n=9)

    def _explode(self, surf, p, t_ms, src, dst):
        """The user blows up: a flash, a fireball, smoke and debris."""
        cx, cy = src.center
        if p < 0.18:
            _flash(surf, WHITE, 210 * (1 - p / 0.18))
        k = ui.ease_out(min(1.0, p / 0.6))
        fade = 1 - _clamp((p - 0.5) / 0.5)
        _glow(surf, (cx, cy), 40 + 30 * k, (255, 170, 80), fade)
        for r, col in ((46, (240, 96, 40)), (34, (248, 176, 64)), (22, (255, 240, 160)), (10, WHITE)):
            rr = int(r * k * fade)
            if rr > 0:
                pygame.draw.circle(surf, col, (cx, cy), rr)
        smoke = (110, 104, 100)
        for i, (dx, dy, s) in enumerate(self.parts):
            q = _clamp((p - 0.25) / 0.75)
            if q <= 0:
                continue
            x, y = cx + dx * (20 + 30 * q), cy + dy * (14 + 20 * q) - q * 16
            r = int((4 + s * 5) * (1 - q * 0.6))
            pygame.draw.circle(surf, smoke, _pt((x, y)), max(1, r))
            if i < 6:
                bx, by = cx + dx * 70 * q, cy + dy * 40 * q + q * q * 30
                pygame.draw.rect(surf, (60, 48, 40), (int(bx), int(by), 3, 3))

    # -- status -------------------------------------------------------------------

    def _buff(self, surf, p, t_ms, src, dst):
        """Stat-up arrows rise around the user over a glowing ring."""
        cx, bottom = src.centerx, src.bottom
        c = self.color
        fade = math.sin(math.pi * p)
        _glow(surf, src.center, 26, STAT_UP if self.mtype in ('Normal', 'Fighting') else c, 0.7 * fade)
        r = int(10 + 18 * p)
        pygame.draw.ellipse(surf, ui.lighten(c, 50), (cx - r, bottom - 4 - r // 4, 2 * r, r // 2), 1)
        if self.move == 'Swords Dance':
            for j in range(3):
                a = p * 7 + j * 2 * math.pi / 3
                x, y = cx + math.cos(a) * 18, src.centery - 6 + math.sin(a) * 6
                pygame.draw.line(surf, (60, 60, 80), _pt((x, y + 6)), _pt((x, y - 9)), 3)
                pygame.draw.line(surf, (230, 236, 248), _pt((x, y + 6)), _pt((x, y - 9)), 1)
                pygame.draw.line(surf, (232, 184, 72), _pt((x - 3, y + 6)), _pt((x + 3, y + 6)), 2)
        for i, (dx, dy, s) in enumerate(self.parts[:6]):
            k = (p * 1.3 - s * 0.3)
            if 0 <= k < 1:
                _chevron(surf, int(cx + dx * 18), int(bottom - 6 - k * (src.height + 6)), True, STAT_UP)

    def _debuff(self, surf, p, t_ms, src, dst):
        """Stat-down arrows sink around the target."""
        cx, top = dst.centerx, dst.top
        fade = math.sin(math.pi * p)
        if self.move in ('Leer', 'Scary Face', 'Glare'):
            for side in (-1, 1):
                ex = src.centerx + side * 5
                surf.fill((248, 64, 64) if (t_ms // 80) % 2 else WHITE, (ex - 1, src.centery - 8, 3, 2))
        _glow(surf, dst.center, 24, STAT_DOWN, 0.6 * fade)
        for i, (dx, dy, s) in enumerate(self.parts[:6]):
            k = (p * 1.3 - s * 0.3)
            if 0 <= k < 1:
                _chevron(surf, int(cx + dx * 18), int(top + 2 + k * (dst.height - 4)), False, STAT_DOWN)
        if self.move in ('Charm', 'Captivate'):
            self._hearts(surf, p, t_ms, src, dst)

    def _heal(self, surf, p, t_ms, src, dst):
        """A soft green glow, plus signs and sparkles rise."""
        cx, bottom = src.centerx, src.bottom
        fade = math.sin(math.pi * p)
        _glow(surf, src.center, 30, HEAL_GREEN, fade)
        if self.move == 'Wish':
            k = _clamp(p / 0.5)
            sx, sy = cx + 30 * (1 - k), src.top - 50 + 50 * k
            _star(surf, _pt((sx, sy)), 5, (248, 224, 96))
        col = pygame.Rect(0, 0, int(src.width * 0.7 * fade) + 2, src.height + 10)
        col.midbottom = (cx, bottom)
        for j in range(0, col.width, 4):
            x = col.left + j
            y = col.bottom - ((t_ms / 6 + j * 7) % col.height)
            surf.fill(ui.lighten(HEAL_GREEN, 60), (x, int(y), 1, 3))
        for i, (dx, dy, s) in enumerate(self.parts[:5]):
            k = (p * 1.3 - s * 0.3)
            if 0 <= k < 1:
                _plus(surf, (cx + dx * 16, bottom - 6 - k * (src.height + 4)), 3, HEAL_GREEN)
        for i, (dx, dy, s) in enumerate(self.parts[5:8]):
            ui.sparkle(surf, int(cx + dx * 18), int(src.centery + dy * 14), t_ms + i * 130, ui.lighten(HEAL_GREEN, 40))

    def _shield(self, surf, p, t_ms, src, dst):
        """A shimmering hexagonal barrier in front of the user."""
        c = SHIELD_CYAN if self.mtype == 'Normal' else self.color
        grow = ui.ease_out(_clamp(p / 0.3))
        fade = 1 - _clamp((p - 0.75) / 0.25)
        r = 22 * grow
        cx, cy = src.center
        pts = [_pt((cx + math.cos(a) * r, cy + math.sin(a) * r * 1.1)) for a in
               (math.pi / 6 + j * math.pi / 3 for j in range(6))]
        if r < 2 or fade <= 0:
            return
        w, h = surf.get_size()
        if self._layer is None or self._layer.get_size() != (w, h):
            self._layer = pygame.Surface((w, h), pygame.SRCALPHA)
        self._layer.fill((0, 0, 0, 0))
        pygame.draw.polygon(self._layer, (*c, int(70 * fade)), pts)
        pygame.draw.polygon(self._layer, (*ui.lighten(c, 70), int(230 * fade)), pts, 2)
        sweep = (p * 2.2 % 1) * 2 * r - r
        pygame.draw.line(self._layer, (255, 255, 255, int(180 * fade)), _pt((cx + sweep - 6, cy - r)),
                         _pt((cx + sweep + 6, cy + r)), 2)
        self._layer.set_clip(pygame.Rect(cx - r, cy - r * 1.1, 2 * r, 2.2 * r))
        surf.blit(self._layer, (0, 0))
        self._layer.set_clip(None)
        _glow(surf, (cx, cy), 26, c, 0.5 * fade)

    def _hex(self, surf, p, t_ms, src, dst):
        """Motes spiral in on the target, then the type's mark."""
        cx, cy = dst.center
        c = self.color
        if self.move in ('Thunder Wave',):
            c = (248, 224, 72)
        edge, hot = ui.darken(c, 80), ui.lighten(c, 70)
        k = _clamp(p / self.lands)
        for i in range(8):
            a = i * math.pi / 4 + k * 4 * math.pi
            r = 32 * (1 - ui.ease_out(k)) + 4
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.7
            pygame.draw.rect(surf, edge, (int(x) - 2, int(y) - 2, 5, 5))
            pygame.draw.rect(surf, hot, (int(x) - 1, int(y) - 1, 3, 3))
        if p >= self.lands:
            q = self._after(p)
            _glow(surf, (cx, cy), 22, c, 1 - q)
            _ring(surf, (cx, cy), 6 + 18 * q, hot)
            self._type_burst(surf, (cx, cy), q, 14, 6)

    def _hearts(self, surf, p, t_ms, src, dst):
        """Hearts float over to the target and pop into sparkles."""
        pink = (248, 120, 168)
        for i in range(5):
            k = (p - i * 0.08) / 0.6
            if not 0 <= k < 1:
                continue
            x, y = _lerp(src.center, dst.center, k)
            x += math.sin(k * 9 + i) * 6
            y -= math.sin(math.pi * k) * 14
            _heart(surf, (x, y), 3 if i % 2 else 2, pink if i % 2 else ui.lighten(pink, 40))
        if p >= 0.6:
            for i, (dx, dy, s) in enumerate(self.parts[:5]):
                ui.sparkle(surf, int(dst.centerx + dx * 16), int(dst.centery + dy * 12), t_ms + i * 120, pink)

    def _powder(self, surf, p, t_ms, src, dst):
        """A glittering dust settles over the target."""
        c = POWDER_COLORS.get(self.move, ui.lighten(self.color, 40))
        edge = ui.darken(c, 70)
        rng = random.Random(self.start)
        fade = 1 - _clamp((p - 0.8) / 0.2)
        for i in range(26):
            s, dx, sway = rng.random(), rng.uniform(-1, 1), rng.uniform(0, 6.28)
            k = (p * 1.4 - s * 0.4)
            if not 0 <= k < 1 or rng.random() > fade:
                continue
            x = dst.centerx + dx * 22 + math.sin(k * 6 + sway) * 5
            y = dst.top - 22 + k * (dst.height + 22)
            surf.fill(edge, (int(x) - 1, int(y) - 1, 3, 3))
            surf.fill(WHITE if (i + t_ms // 90) % 5 == 0 else c, (int(x), int(y), 1, 1))
        _glow(surf, dst.center, 22, c, 0.4 * math.sin(math.pi * p))

    def _web(self, surf, p, t_ms, src, dst):
        """Threads shoot over and a web spreads across the target."""
        cx, cy = dst.center
        silk = (236, 236, 244) if self.mtype != 'Electric' else (248, 232, 120)
        if p < self.lands:
            k = p / self.lands
            for j in (-1, 1):
                e = _lerp(src.center, (cx, cy + j * 6), k)
                pygame.draw.line(surf, silk, src.center, _pt(e), 1)
            return
        q = self._after(p)
        r = 22 * ui.ease_out(min(1.0, q * 2))
        fade = 1 - _clamp((q - 0.7) / 0.3)
        if fade <= 0:
            return
        spokes = [(math.cos(j * math.pi / 4), math.sin(j * math.pi / 4)) for j in range(8)]
        for ux, uy in spokes:
            pygame.draw.line(surf, silk, (cx, cy), _pt((cx + ux * r, cy + uy * r * 0.85)), 1)
        for ring in (0.35, 0.65, 1.0):
            pts = [_pt((cx + ux * r * ring, cy + uy * r * ring * 0.85)) for ux, uy in spokes]
            pygame.draw.lines(surf, silk, True, pts, 1)

    def _weather(self, surf, p, t_ms, src, dst):
        """Sunny Day, Rain Dance, Sandstorm, Hail, Tailwind: the sky changes."""
        w, h = surf.get_size()
        fade = _clamp(p / 0.2) * _clamp((1 - p) / 0.25)
        rng = random.Random(self.start)
        move = self.move
        if move == 'Sunny Day':
            _glow(surf, (w - 20, 10), 70, (255, 200, 90), fade)
            for j in range(7):
                a = math.pi * 0.55 + j * 0.13 + math.sin(t_ms / 400 + j) * 0.02
                pygame.draw.line(surf, (255, 236, 160), (w - 20, 10),
                                 _pt((w - 20 + math.cos(a) * 160 * fade, 10 + math.sin(a) * 160 * fade)), 1)
            return
        if move in ('Rain Dance', 'Water Sport'):
            col, n, dx, sp, ln = (150, 190, 248), 50, -1.5, 0.45, 6
        elif move == 'Sandstorm':
            col, n, dx, sp, ln = (220, 196, 140), 60, 3.0, 0.3, 3
        elif move == 'Hail':
            col, n, dx, sp, ln = (232, 244, 255), 30, -0.8, 0.35, 0
        else:   # Tailwind
            col, n, dx, sp, ln = (232, 244, 248), 24, 6.0 * self._dir(src, dst), 0.05, 10
        for i in range(n):
            sx, sy, s = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.7, 1.3)
            if rng.random() > fade:
                continue
            x = (sx + dx * t_ms * sp * s / 6) % (w + 20) - 10
            y = (sy + t_ms * sp * s) % (h + 20) - 10
            if ln:
                pygame.draw.line(surf, col, (int(x), int(y)), (int(x - dx * ln / 3), int(y - ln)), 1)
            else:
                surf.fill(ui.darken(col, 70), (int(x) - 1, int(y) - 1, 4, 4))
                surf.fill(col, (int(x), int(y), 2, 2))

    def _hazard(self, surf, p, t_ms, src, dst):
        """Spikes or pointed stones land around the target's feet."""
        c = (176, 112, 200) if self.move == 'Toxic Spikes' else (150, 140, 128)
        if self.move == 'Stealth Rock':
            c = self.color
        edge, hi = ui.darken(c, 80), ui.lighten(c, 60)
        for i, (dx, dy, s) in enumerate(self.parts[:4]):
            k = _clamp((p - i * 0.06) / self.lands)
            end = (dst.centerx + (i - 1.5) * 12, dst.bottom - 2 - (s * 8 if self.move == 'Stealth Rock' else 0))
            x, y = _lerp(src.center, end, k)
            y -= math.sin(math.pi * k) * 24
            if self.move == 'Stealth Rock' and k >= 1:
                y += math.sin(t_ms / 200 + i) * 2   # they float
            if k <= 0:
                continue
            if self.move == 'Stealth Rock':
                pts = [_pt((x, y - 5)), _pt((x + 3, y)), _pt((x, y + 3)), _pt((x - 3, y))]
            else:
                pts = [_pt((x, y - 4)), _pt((x + 4, y + 2)), _pt((x - 4, y + 2))]
            pygame.draw.polygon(surf, hi, pts)
            pygame.draw.polygon(surf, edge, pts, 1)
            if k >= 1 and (t_ms // 120 + i) % 6 == 0:
                surf.fill(WHITE, (int(x), int(y) - 3, 1, 1))

    def _room(self, surf, p, t_ms, src, dst):
        """Trick Room and friends: the space itself twists (Gravity pulls)."""
        w, h = surf.get_size()
        fade = _clamp(p / 0.2) * _clamp((1 - p) / 0.25)
        c = ui.lighten(self.color, 50)
        if self.move == 'Gravity':
            for j in range(14):
                x = j * w / 14 + 8
                y = (t_ms * 0.4 + j * 37) % (h + 30) - 30
                if fade > 0.2:
                    pygame.draw.line(surf, c, (int(x), int(y)), (int(x), int(y) + 14), 1)
            _flash(surf, (40, 20, 70), 50 * fade)
            return
        for i in range(4):
            k = (p * 1.4 - i * 0.18) % 1
            rw, rh = int(w * k), int(h * k)
            if rw > 4 and fade > 0.1:
                pygame.draw.rect(surf, c if i % 2 else WHITE, ((w - rw) // 2, (h - rh) // 2, rw, rh), 1)
        _flash(surf, self.color, 28 * fade)
