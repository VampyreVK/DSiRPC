"""core/hub.py's DsiSource, DSiRPC's side, against helpers/fake_dsi.py over
loopback UDP, in real time: Pokemon Black/White (its parser, the quick
battle reads, the game card while the memory doesn't look like the game,
the Continue menu, the trainer's gait in the field) and the
RetroAchievements side on the simulated puzzle game (every-frame checks
from the capture ring, nothing checked twice when the console's checker
runs the set, DSiRPC's unlocks pushed to the console)."""

import collections
import struct
import threading
import time
import types

import pytest

import core.hub
import core.ra_game
from core import offline, ra_set
from core.bw_parser import BWParser, WHITE_SHIFT
from helpers import bw_fake, gen_set, puzzle_game
from helpers.fake_dsi import FakeDsi, free_port, pc_socket_only

pytestmark = pytest.mark.realtime


@pytest.fixture
def hub(monkeypatch, tmp_path):
    pc_socket_only(monkeypatch)
    monkeypatch.setattr(offline, "_known_path", lambda ra_dir=None: str(tmp_path / "console_sets.json"))
    sets = {}
    monkeypatch.setattr(core.ra_game.ra_set, "for_game", lambda code, ra_dir=None: sets.get(code))
    BWParser._player_slot.clear()
    made = []

    def start(ram=None, code="TEST", game=None, before_start=None):
        port = free_port()
        fake = FakeDsi(port, ram=ram, code=code, game=game)
        if before_start:
            before_start(fake)
        fake.start()
        src = core.hub.DsiSource(None, port=port)
        made.append((fake, src))
        return fake, src
    start.sets = sets
    yield start
    for fake, src in made:
        fake.stop()
        src.close()
    BWParser._player_slot.clear()


def until(src, cond, secs=8.0):
    end = time.time() + secs
    d = None
    while time.time() < end:
        d = src.read()
        if d is not None and cond(d):
            return d
        time.sleep(min(0.3, src.next_delay() or 0.1))
    raise AssertionError(f"timed out; the last state's kind: {d and d.get('kind')}")


# -- Pokemon Black and White --------------------------------------------------------

def test_black_white(hub):
    fake, src = hub(ram=bw_fake.make("White"), code="IRAO")
    src.parse_interval = 1.0
    d = until(src, lambda d: d.get("kind") == "bw")
    assert d["version"] == "White" and d["trainer_name"] == "Hilda" and d["location"]["name"] == "Castelia City"
    assert core.hub.is_bw(d) and not core.hub.is_other(d)

    # A battle starts
    fake.ram[:] = bw_fake.make("White", battle=True, wild=False)
    d = until(src, lambda d: d["battle"]["active"])
    assert [m["species_id"] for m in d["battle"]["mons"]] == [501, 506]
    # The foe takes a hit: the quick reads see it, in a request or two
    ptr = int(d["battle"]["mons"][1]["battler"], 16)
    before = fake.requests[b"R"]
    fake.poke(ptr + BWParser.B_SPECIES + 4, struct.pack("<H", 3))
    until(src, lambda d: d["battle"]["active"] and d["battle"]["mons"][1]["curr_hp"] == 3, 4.0)
    assert fake.requests[b"R"] - before <= 4

    # It ends
    fake.ram[:] = bw_fake.make("White")
    until(src, lambda d: d.get("kind") == "bw" and not d["battle"]["active"])
    # Something else in memory (another region of the game): the game card, then back
    fake.ram[:] = bytes(len(fake.ram))
    assert until(src, lambda d: d.get("kind") == "other")["kind"] == "other"
    fake.ram[:] = bw_fake.make("White")
    until(src, lambda d: d.get("kind") == "bw")
    # The Continue menu: the game card until you're in the field
    fake.ram[:] = bw_fake.make("White", zone=0, field=False)
    until(src, lambda d: d.get("kind") == "other")
    fake.ram[:] = bw_fake.make("White", zone=0, player_slot=0, facing=1)
    d = until(src, lambda d: d.get("kind") == "bw")
    assert d["location"]["facing"] == "down"


def test_black_white_gait(hub):
    fake, src = hub(ram=bw_fake.make("White", player_slot=2, facing=3), code="IRAO")
    obj = BWParser.MAP_OBJECTS + WHITE_SHIFT + 2 * 0x100
    form = BWParser.FORM + WHITE_SHIFT
    until(src, lambda d: d.get("kind") == "bw")
    phases = [(1.5, 0.0, 0, "stand"), (2.2, 3.75, 0, "walk"), (2.2, 7.5, 0, "run"), (2.2, 7.5, 1, "bike"),
              (1.8, 0.0, 1, "bike_stop")]
    now_phase = [None, 0.0]

    def walk():
        x = 300.5
        for secs, speed, bike, name in phases:
            now_phase[:] = [name, time.time()]
            fake.poke(form, bytes([bike]))
            end = time.time() + secs
            while time.time() < end:
                x += speed * 0.02
                fake.poke(obj + BWParser.O_POSITION, struct.pack("<iii", int(x * 65536), 0, int(512.5 * 65536)))
                time.sleep(0.02)
        now_phase[0] = "done"
    threading.Thread(target=walk, daemon=True).start()
    seen = collections.defaultdict(collections.Counter)
    while now_phase[0] != "done":
        d = src.read()
        name, since = now_phase
        if d and d.get("kind") == "bw" and name and time.time() - since > 0.8:   # (a phase's start can lag)
            seen[name][d["location"].get("gait")] += 1
        time.sleep(src.next_delay() or 0.1)
    for _, _, _, name in phases:
        assert seen[name] and seen[name].most_common(1)[0][0] == name, (name, dict(seen[name]))


# -- the RetroAchievements side --------------------------------------------------------

class PuzzleOnDsi:
    """The puzzle game on the fake DSi, with rcheevos following every frame
    (the truth) and, in console mode, the console's checker reporting what
    it unlocked of the set it runs."""

    def __init__(self, raset, console=None):
        self.truth = puzzle_game.rc_runtime([(a["id"], a["memaddr"]) for a in raset.achievements])
        self.unlocked = {}            # id -> frame
        self.console = console        # {'ids', 'stamp', 'n', 'frame_lane'} or None
        self.console_unlocks = []
        self.game = self.peek = None
        self.fake = None
        self.frame = 0

    def __call__(self, ram):
        if self.game is None:
            self.game = puzzle_game.Game(ram, 11)
            self.peek = puzzle_game.peek_from(ram)
        self.game.step()
        pushed = {aid for aid, _ in self.fake.pushed}
        for name, aid, _ in self.truth.frame(self.peek):
            if name == "achievement_triggered":
                self.unlocked.setdefault(aid, self.frame)
                if self.console and aid in self.console["ids"] and aid not in pushed:
                    self.console_unlocks.append(aid)
        if self.console and self.frame % 30 == 0:
            c = self.console
            ids = ",".join(str(i) for i in self.console_unlocks[-8:])
            self.fake.ach_report = (f"DSiRPC ach n={c['n']} t={len(self.console_unlocks)} p=10 l=12 s=0 x=0 w=0 "
                                    f"f={c['frame_lane']} fr=60 fd=0 fc=0 h=1 st={c['stamp']:08X}"
                                    + (f" ids={ids}" if ids else ""))
        self.frame += 1


def _puzzle_ram():
    ram = bytearray(0x400000)
    header = b"TEST PUZZLE\0" + b"TEST"
    ram[0x3FFE00:0x3FFE00 + len(header)] = header    # the DS header's copy: title and game code
    return ram


def _run(src, seconds):
    unlocks = {}
    end = time.time() + seconds
    while time.time() < end:
        src.read()
        for e in src.take_events():
            if e.get("type") == "achievement":
                unlocks[e["id"]] = (time.time(), e.get("by_console"), e.get("every_frame"))
        time.sleep(src.next_delay() or 0.05)
    return unlocks


def test_achievements_on_the_pc(hub, rcheevos):
    raset = ra_set.RaSet(gen_set.make_set(120, seed=4))
    hub.sets["TEST"] = raset
    puzzle = PuzzleOnDsi(raset)
    fake, src = hub(ram=_puzzle_ram(), game=puzzle, before_start=lambda f: setattr(puzzle, "fake", f))
    unlocks = _run(src, 15.0)
    ra = src.ra_game
    assert ra is not None and ra.capture is not None and ra.capture.ids, "nothing checked every frame"
    assert ra.capture.frames > 300 and ra.capture.failed <= 3
    every_frame = {aid for aid, (_, _, ef) in unlocks.items() if ef}
    assert every_frame, "the capture should have unlocked some"
    assert every_frame <= set(puzzle.unlocked), "unlocked every frame but rcheevos never did"
    assert unlocks and not fake.pushed                            # no console checker: nothing to push


def test_achievements_with_the_consoles_checker(hub, rcheevos):
    raset = ra_set.RaSet(gen_set.make_set(120, seed=4))
    hub.sets["TEST"] = raset
    # The console runs a set with the first 60 (as if it was built before
    # the rest existed), so DSiRPC checks the other 60 itself
    half = gen_set.make_set(120, seed=4)
    half["PatchData"]["Achievements"] = half["PatchData"]["Achievements"][:60]
    data = offline.build_set(ra_set.RaSet(half), "TEST")
    offline.remember_set(data)
    info = offline.read_set(data)
    on_console = set(info["frame"]) | set(info["pass"])
    assert len(on_console) == 60
    puzzle = PuzzleOnDsi(raset, console={"ids": on_console, "stamp": info["stamp"], "frame_lane": len(info["frame"]),
                                         "n": len(on_console)})
    fake, src = hub(ram=_puzzle_ram(), game=puzzle, before_start=lambda f: setattr(puzzle, "fake", f))
    unlocks = _run(src, 15.0)
    ra = src.ra_game
    # What the console checks isn't checked on the PC too
    assert ra.in_runtime and not ra.in_runtime & on_console
    assert not set(ra.capture.ids if ra.capture else ()) & on_console
    # The console's unlocks count; DSiRPC's own are pushed to the console
    by_console = {aid for aid, (_, bc, _) in unlocks.items() if bc}
    assert by_console and by_console <= on_console
    end = time.time()
    mine = {aid for aid, (at, bc, _) in unlocks.items() if not bc and at < end - 3.0}
    assert mine - on_console, "DSiRPC should have unlocked some of its own half"
    assert mine <= {aid for aid, _ in fake.pushed}


# -- the launcher ---------------------------------------------------------------

def test_the_launchers_state_times_out(monkeypatch):
    """In the launcher while it says it's still there (every 5 s), gone soon
    after it stops; an older launcher, which never says so, counts as there
    for its 15 minutes; a game being started that never says hello, gone
    after 2."""
    pc_socket_only(monkeypatch)
    src = core.hub.DsiSource(None, port=free_port())
    now = [1000.0]
    monkeypatch.setattr(core.hub, "time", types.SimpleNamespace(time=lambda: now[0]))
    try:
        src.launcher = {'ip': '10.0.0.5', 'game': None, 'title': '', 'console': '3DS', 'at': now[0], 'here': True}
        assert src.launcher_state and src.status == "3DS at 10.0.0.5: in the launcher"
        now[0] += src.LAUNCHER_HERE_S + 1
        assert src.launcher_state is None
        src.launcher = dict(src.launcher, here=False, at=now[0])
        now[0] += src.LAUNCHER_HERE_S + 1
        assert src.launcher_state is not None
        src.launcher = dict(src.launcher, game='IRBO', title='Pokémon Black', at=now[0])
        assert src.status == "3DS at 10.0.0.5: starting Pokémon Black"
        now[0] += src.LAUNCHER_STARTING_S + 1
        assert src.launcher_state is None
    finally:
        src.close()
