"""What the launcher is doing, on the PC (core/launcher_activity.py): the
tracker itself; the offline sync, the save sync and the console updates
telling it as they go (core/console_sync.py, core/save_session.py through
app/engine.py, core/console_update.py); Discord while the console is in the
launcher (rpc/generic_presence.py's launcher_presence(), through
rpc/presence_connector.py); the overlay window's activity card
(overlay/activity_card.py): when it shows, that it slides down and away,
that its bar moves (one bar across a whole update or save sync), and that
the window draws it, under a toast; and the tray's watcher."""

import socket
import time
from types import SimpleNamespace

import pytest

from core import console_update as cu, offline, saves
from core import launcher_activity as la
from core import save_session as ss
from core.console_sync import ConsoleSync
from core.launcher_activity import LauncherActivity

HOST = "127.0.0.1"


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _wait(cond, secs=5):
    end = time.monotonic() + secs
    while not cond() and time.monotonic() < end:
        time.sleep(0.01)
    return cond()


# -- the tracker ----------------------------------------------------------------

def test_an_activity_from_start_to_finish():
    clock = Clock()
    act = LauncherActivity(clock)
    assert act.current() is None and act.line() is None and not act.active()
    act.start("saves", "Syncing saves", console="3DS", total=3, detail="3 saves to move")
    assert act.active("saves") and not act.active("update")
    assert act.line() == "Syncing saves (0 of 3)"
    act.progress(2, detail="Uploaded Pokemon Black")
    v = act.current()
    assert (v['done'], v['total'], v['detail'], v['console']) == (2, 3, "Uploaded Pokemon Black", "3DS")
    act.progress(5)                                   # (more than the plan said: the total grows)
    assert act.line() == "Syncing saves (5 of 5)"
    act.finish("2 uploaded, 3 downloaded")
    assert act.line() == "Syncing saves: done" and not act.active()
    act.progress(1)                                   # (nothing changes once it's over)
    assert act.current()['done'] == 5
    clock.t += la.DONE_S + 0.1
    assert act.current() is None                      # shown for a while, then gone


def test_a_launcher_that_goes_quiet_mid_way():
    clock = Clock()
    act = LauncherActivity(clock)
    act.start("achievements", "Syncing achievements")
    assert act.line() == "Syncing achievements"      # (no count yet)
    clock.t += la.IDLE_S - 1
    act.progress(1, 4)
    clock.t += la.IDLE_S - 1
    assert act.active()                               # still talking
    clock.t += 2
    assert act.current() is None                      # gone without a word: over


def test_bytes_are_counted_as_a_percentage():
    act = LauncherActivity()
    act.start("update", "Updating the console", total=200, unit="bytes")
    act.progress(50)
    assert act.line() == "Updating the console (25%)"
    act.finish("Sent the launcher", ok=False)
    assert act.line() == "Updating the console: failed"
    assert la.fraction(act.current()) == 0.25        # (a failed one stays where it got to)


# -- the syncs telling it ---------------------------------------------------------

def test_the_offline_sync_tells_it(tmp_path):
    act = LauncherActivity()
    seen = []
    real_progress = act.progress

    def progress(*a, **k):
        real_progress(*a, **k)
        seen.append(act.current()['detail'])
    act.progress = progress
    sync = ConsoleSync(lambda game, stamps, unlocks: [("IRBO", b"set one" * 4000), ("CPUE", b"set two")],
                       lambda u: None, port=0, host=HOST, activity=act)
    sync.start()
    try:
        from test_console_sync import exchange
        assert len(exchange(sync.port, offline.build_request("IRBO", {}, b""))[2]) == 2
        assert _wait(lambda: act.current() and act.current()['finished'])
        v = act.current()
        assert (v['kind'], v['title'], v['console'], v['ok']) == ("achievements", "Syncing achievements", "DSi", True)
        assert v['summary'] == "2 sets sent" and v['unit'] == "bytes" and v['done'] == v['total'] > 28000
        assert "Sending 2 achievement sets" in seen
    finally:
        sync.stop()


def test_a_sync_with_nothing_to_send_is_up_to_date():
    act = LauncherActivity()
    sync = ConsoleSync(lambda game, stamps, unlocks: [], lambda u: None, port=0, host=HOST, activity=act)
    sync.start()
    try:
        with socket.create_connection((HOST, sync.port), timeout=5) as c:
            c.sendall(offline.build_request(None, {}, b""))
            c.recv(4096)
        assert _wait(lambda: act.current() and act.current()['finished'])
        assert act.current()['summary'] == "Everything was up to date"
    finally:
        sync.stop()


def test_the_console_update_tells_it_how_much_has_gone():
    heard = []
    data = b"x" * (cu.CHUNK * 2 + 10)
    files = SimpleNamespace(read=lambda f: (data, 1234))

    def ask(req):
        rest = req[4:]

        def read(n):
            nonlocal rest
            chunk, rest = rest[:n], rest[n:]
            return chunk
        cu.handle(req[:4], read, lambda b: None, files, progress=lambda *a: heard.append(a))
    ask(cu.request(cu.OP_GET, cu.LAUNCHER, model=3))
    assert heard[0] == ("the launcher", 0, len(data), "3DS", 0)          # (a launcher that doesn't say the total)
    assert [h[1] for h in heard] == [0, cu.CHUNK, cu.CHUNK * 2, len(data)]

    # From a launcher that doesn't say: each file one of its own, done once it's gone
    act = LauncherActivity()
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST, activity=act)
    for h in heard:
        sync._update_progress(*h)
    v = act.current()
    assert (v['kind'], v['detail'], v['summary'], v['console'], v['finished'] is not None) == \
        ("update", "Sending the launcher", "Sent the launcher", "3DS", True)

    # One that says (both files' bytes): one bar across both, done after the second
    heard.clear()
    ask(cu.request(cu.OP_GET, cu.LAUNCHER, model=3, update=len(data) * 2))
    ask(cu.request(cu.OP_GET, cu.BOOTSTRAP, model=3, update=len(data) * 2))
    assert {h[4] for h in heard} == {len(data) * 2}
    act = LauncherActivity()
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST, activity=act)
    dones, gens = [], set()
    for h in heard:
        sync._update_progress(*h)
        v = act.current()
        dones.append(v['done'])
        gens.add(v['generation'])
        if h[0] == "the launcher":
            assert v['finished'] is None and v['detail'] == "Sending the launcher"
    assert dones == sorted(dones) and dones[-1] == len(data) * 2 and len(gens) == 1
    v = act.current()
    assert (v['detail'], v['summary'], v['finished'] is not None, v['total']) == \
        ("Sending nds-bootstrap", "Sent the launcher and nds-bootstrap", True, len(data) * 2)


def _engine(act):
    from app.engine import Engine
    engine = Engine.__new__(Engine)
    engine.activity = act
    engine._save_batch, engine._save_moves = None, 0
    return engine


def _moving(name, key, up, done, size, kind=None):
    return {"type": "save_moving", "console": "3DS 3F21", "name": name, "key": key, "slot": 0, "up": up,
            "kind": kind, "done": done, "size": size}


def test_the_save_sync_tells_it(tmp_path):
    """core/save_session.py's events, through the engine's _save_activity():
    the plan alone shows nothing (the connecting screen asks for it too);
    the launcher's batch starts it, by its bytes, each piece of a save moves
    the bar, the batch's end says how it went"""
    act = LauncherActivity()
    engine = _engine(act)
    store = saves.SaveStore(str(tmp_path / "saves"), keep=5)
    events = []

    def on_saves(e):
        events.append(e)
        engine._save_activity(e)
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST, saves=lambda: store, on_saves=on_saves)
    sync.start()
    try:
        from test_save_session import entry, plan, put, talk, MAC
        port = sync.port
        v1 = b"\x01" * (ss.CHUNK * 2 + 100)
        plan(port, [entry(v1)])
        assert _wait(lambda: any(e["type"] == "save_plan" for e in events))
        assert events[0]["moves"] == 1 and act.current() is None            # (not a sync: nothing shows)

        batch = lambda n, size: talk(port, ss.request(ss.OP_BATCH, ss.BATCH.pack(n, size), MAC), lambda read: read(6))
        assert batch(1, len(v1))[4:6] == b"\0\0"
        assert _wait(lambda: act.active("saves"))
        assert (act.current()['total'], act.current()['unit'], act.current()['items']) == (len(v1), "bytes", 1)
        put(port, v1, saves.PUT_SYNC)
        assert _wait(lambda: act.current()['done'] == len(v1))
        moving = [e["done"] for e in events if e["type"] == "save_moving"]
        assert moving == [0, ss.CHUNK, ss.CHUNK * 2, len(v1)]                # (a piece at a time)
        v = act.current()
        assert (v['item'], v['detail'], la.describe(v)) == (1, "Uploading Pokemon Black", "Syncing saves (1 of 1)")
        batch(0, 0)
        assert _wait(lambda: act.current()['finished'] is not None)
        v = act.current()
        assert (v['summary'], v['ok'], v['console']) == ("1 uploaded", True, "DSi")
        # (the launcher's done, when it leaves the Saves screen, changes nothing)
        talk(port, ss.request(ss.OP_DONE, ss.DONE.pack(1, 0, 0, 0), MAC), lambda read: read(6))
        assert act.current()['summary'] == "1 uploaded"
    finally:
        sync.stop()


def test_one_bar_across_every_save_of_a_sync():
    act = LauncherActivity()
    engine = _engine(act)
    e = engine._save_activity
    e({"type": "save_batch", "console": "3DS 3F21", "saves": 2, "bytes": 512 + 256 + 1024})
    seen = []

    def step(*a, **k):
        e(_moving(*a, **k))
        v = act.current()
        seen.append((v['done'], v['item'], v['detail']))
    for d in (0, 256, 512):
        step("Pokemon Black", "IRBO", True, d, 512, saves.PUT_SYNC)
    e({"type": "save_uploaded", "console": "3DS 3F21", "name": "Pokemon Black", "kind": saves.PUT_SYNC})
    # The next: its copy kept first, then the PC's taken, cut off once and tried again
    for d in (0, 256):
        step("Platinum", "CPUE", True, d, 256, saves.PUT_SAFETY)
    e({"type": "save_uploaded", "console": "3DS 3F21", "name": "Platinum", "kind": saves.PUT_SAFETY})
    for d in (0, 512):
        step("Platinum", "CPUE", False, d, 1024)
    for d in (0, 512, 1024):
        step("Platinum", "CPUE", False, d, 1024)
    e({"type": "save_downloaded", "console": "3DS 3F21", "name": "Platinum"})
    assert [s[0] for s in seen] == [0, 256, 512, 512, 768, 768, 1280, 768, 1280, 1792]
    assert [s[1] for s in seen] == [1, 1, 1, 2, 2, 2, 2, 2, 2, 2]
    assert seen[3][2] == "Backing up Platinum first" and seen[-1][2] == "Downloading Platinum"
    assert act.current()['finished'] is None and la.fraction(act.current()) == 1.0
    e({"type": "save_batch", "console": "3DS 3F21", "saves": 0, "bytes": 0})
    v = act.current()
    assert (v['summary'], v['ok']) == ("1 uploaded, 1 downloaded", True)

    # A save that didn't make it: failed
    e({"type": "save_batch", "console": "DSi 3F21", "saves": 1, "bytes": 512})
    e(_moving("Tetris DS", "ATRE", True, 0, 512, saves.PUT_SYNC))
    e({"type": "save_batch", "console": "DSi 3F21", "saves": 0, "bytes": 0})
    v = act.current()
    assert (v['summary'], v['ok']) == ("1 failed", False)


def test_a_launcher_from_before_batches():
    """Each save moved is one more of the plan's (as long as one moves)"""
    act = LauncherActivity()
    engine = _engine(act)
    e = engine._save_activity
    e({"type": "save_plan", "console": "DSi 3F21", "saves": 4, "moves": 2, "conflicts": 0})
    assert act.current() is None
    e(_moving("Pokemon Black", "IRBO", True, 0, 512, saves.PUT_SYNC))
    assert act.current()['total'] == 2 and act.current()['detail'] == "Uploading Pokemon Black"
    e({"type": "save_uploaded", "console": "DSi 3F21", "name": "Pokemon Black", "kind": saves.PUT_SYNC})
    assert act.current()['done'] == 1
    e({"type": "saves_synced", "console": "DSi 3F21", "uploaded": 1, "downloaded": 0, "backed_up": 0, "failed": 0})
    assert act.current()['summary'] == "1 uploaded"


def test_a_save_sync_with_nothing_to_move_shows_nothing():
    act = LauncherActivity()
    engine = _engine(act)
    engine._save_activity({"type": "save_plan", "console": "DSi 3F21", "saves": 4, "moves": 3, "conflicts": 0})
    engine._save_activity({"type": "saves_synced", "console": "DSi 3F21", "uploaded": 0,
                           "downloaded": 0, "backed_up": 0, "failed": 0})
    assert act.current() is None


# -- Discord in the launcher ---------------------------------------------------------

def test_the_launchers_presence():
    from rpc import generic_presence as gp
    p = gp.launcher_presence({'console': "3DS", 'game': None, 'ip': "10.0.0.5"}, None, start=1234)
    assert p["name"] == "DSiRPC" and p["details"] == "In the launcher" and "state" not in p   # (idle: no second line)
    assert p["large_text"] == "DSiRPC on 3DS" and p["large_image"].endswith("/Pixel.gif")
    assert "small_image" not in p and "small_text" not in p and p["start"] == 1234
    p = gp.launcher_presence({'console': "DSi", 'game': "CPUE", 'title': "Pokémon Platinum"}, "Syncing saves (2 of 5)")
    assert p["large_text"] == "DSiRPC on DSi"
    assert (p["details"], p["state"]) == ("Starting Pokémon Platinum", "Syncing saves (2 of 5)")


def test_discord_shows_the_launcher_until_the_game_says_hello():
    from core.hub import Snapshot
    from rpc.presence_connector import DiscordConnector
    d = DiscordConnector(lambda: "", dry_run=True, check_images=False)
    d.activity = LauncherActivity()
    d.activity.start("saves", "Syncing saves", total=2)
    launcher = {'ip': "10.0.0.5", 'game': None, 'title': '', 'console': "3DS", 'at': time.time(), 'here': True}
    d.on_update(Snapshot(None, False, 0, "3DS at 10.0.0.5: in the launcher", launcher), [])
    assert d.last_sent["details"] == "In the launcher" and d.last_sent["state"] == "Syncing saves (0 of 2)"
    assert d.last_sent["large_text"] == "DSiRPC on 3DS" and d.status == "would show DSiRPC"
    started = d.start
    d.last_time = 0     # (past Discord's gap)
    d.on_update(Snapshot(None, False, 0, "", dict(launcher, game="CPUE", title="Pokémon Platinum")), [])
    assert d.last_sent["details"] == "Starting Pokémon Platinum" and d.start == started   # the same timer
    d.on_update(Snapshot(None, False, 0, "", None), [])
    assert d.last_sent is None and d.status == "waiting for the game"                   # gone: cleared


# -- the overlay window's card ---------------------------------------------------------

def _view(**k):
    v = {'kind': "saves", 'title': "Syncing saves", 'detail': "", 'done': 0, 'total': 0, 'unit': "",
         'item': 0, 'items': 0, 'console': "DSi", 'started': 100.0, 'changed': 100.0, 'finished': None,
         'summary': "", 'ok': True, 'generation': 3}
    v.update(k)
    return v


def test_when_the_card_shows():
    from overlay.activity_card import SHOW_AFTER, count_text, should_show
    assert not should_show(None, 100.0, 0)
    assert not should_show(_view(), 100.0 + SHOW_AFTER / 2, 0)              # a quick one never shows
    assert should_show(_view(), 100.0 + SHOW_AFTER, 0)                       # a slow one does
    assert not should_show(_view(finished=100.2), 100.3, 0)                  # done before it showed: not now
    assert should_show(_view(finished=105.0), 105.1, 3)                      # done after: it says so
    assert count_text(_view(total=5, done=2)) == "2 of 5"
    assert count_text(_view(total=100, done=40, unit="bytes")) == "40%"
    assert count_text(_view(total=100, done=40, unit="bytes", item=2, items=5)) == "2 of 5"   # (its saves)
    assert count_text(_view(finished=1.0, total=5)) == ""


@pytest.fixture
def overlay_canvas(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    pygame.init()
    pygame.display.set_mode((1, 1))     # (for the views' sprites)
    yield pygame.Surface((256, 192))
    pygame.quit()


def _colors(surf, rect):
    x0, y0, w, h = rect
    return {tuple(surf.get_at((x, y)))[:3] for x in range(x0, x0 + w) for y in range(y0, y0 + h)}


def _bar_row(top=None):
    from overlay import activity_card as ac
    return (ac.TOP if top is None else top) + ac.CARD_H - 7


def _bar_fill(canvas, color="ach", top=None):
    """How many pixels of the card's bar are filled (gold going, green done)."""
    from overlay import ui
    return sum(tuple(canvas.get_at((x, _bar_row(top))))[:3] == ui.THEME[color] for x in range(256))


def test_the_card_slides_down_its_bar_moves_and_it_slides_away(overlay_canvas):
    from overlay import activity_card as ac, ui
    from overlay.font import PixelFont
    canvas = overlay_canvas
    card = ac.ActivityCard(PixelFont(), PixelFont(mini=True))
    card_rect = (ac.CARD_X, ac.TOP, ac.CARD_W, ac.CARD_H)

    def frame(view, t_ms, now):
        canvas.fill((0, 0, 0))
        card.draw(canvas, view, t_ms, now)
        return _colors(canvas, card_rect)

    v0 = _view(total=4, done=0, detail="Uploading Pokemon Black")
    assert frame(v0, 0, 100.5) == {(0, 0, 0)}                             # not yet: under a second
    frame(v0, 100, 101.5)                                                 # comes down...
    frame(v0, 100 + ac.SLIDE_MS // 2, 101.6)
    assert _colors(canvas, (0, 0, 256, ac.TOP + 2)) != {(0, 0, 0)}        # (from the top)
    up = frame(v0, 100 + ac.SLIDE_MS, 101.8)                              # ...and is there
    v = dict(v0, done=1)
    assert ui.THEME['lead_fill'] in up and ui.THEME['lead_border'] in up and len(up) > 6
    assert _colors(canvas, (0, 60, 256, 132)) == {(0, 0, 0)}              # (nothing lower down)
    fills = []
    for i in range(20):                                                   # the bar glides to 1 of 4
        frame(v, 360 + i * 16, 102.0)
        fills.append(_bar_fill(canvas))
    width = ac.CARD_W - 16
    assert 0 < fills[0] < fills[3] < fills[-1] and abs(fills[-1] - width // 4) <= 2
    assert fills[5] > width // 4 * 0.6                                   # (quickly: it keeps up)
    for i in range(20):
        frame(dict(v, done=3), 700 + i * 16, 103.0)
    assert abs(_bar_fill(canvas) - width * 3 // 4) <= 2                  # and on to 3 of 4

    # Without a count, the block going back and forth moves
    spin = _view(generation=4, started=90.0)
    frame(spin, 3000, 104.0)
    a = [tuple(canvas.get_at((x, _bar_row())))[:3] for x in range(256)]
    frame(spin, 3300, 104.0)
    b = [tuple(canvas.get_at((x, _bar_row())))[:3] for x in range(256)]
    assert a != b and ui.THEME['ach'] in a

    # Done: green and full, then away once it's over
    frame(_view(generation=4, started=90.0, finished=105.0, summary="2 uploaded"), 4000, 105.1)
    assert _bar_fill(canvas, "hp_green") == width
    frame(None, 5000, 110.0)
    assert frame(None, 5000 + ac.SLIDE_MS + 1, 110.0) == {(0, 0, 0)}


def test_the_card_on_failure(overlay_canvas):
    from overlay import activity_card as ac, ui
    from overlay.font import PixelFont
    card = ac.ActivityCard(PixelFont(), PixelFont(mini=True))
    v = _view(total=4, done=2)
    for i in range(30):
        card.draw(overlay_canvas, v, i * 16, 102.0)
    card.draw(overlay_canvas, dict(v, finished=103.0, ok=False, summary="Lost the console"), 600, 103.1)
    colors = _colors(overlay_canvas, (0, 0, 256, 40))
    assert ui.THEME['hp_red'] in colors and ui.THEME['hp_green'] not in colors


def test_the_overlay_draws_the_card_over_any_view_under_a_toast(overlay_canvas):
    """Overlay.draw() draws it last, from its activity() each frame, and
    under a toast while one is up"""
    from core.hub import Snapshot
    from overlay.scenes import Overlay
    from overlay.sprites import SpriteBank
    from core.paths import DATA
    import os
    from overlay import activity_card as ac, ui
    overlay = Overlay(SpriteBank(os.path.join(DATA, "Assets")))
    view = _view(total=2, done=1, started=time.time() - 5)
    overlay.activity = lambda: view
    for t in (0, 50, 400):
        overlay.draw(overlay_canvas, Snapshot(), t, 16)
    assert _bar_fill(overlay_canvas) > 0

    overlay.toast("Achievement: Test")
    for t in range(500, 1400, 16):
        overlay.draw(overlay_canvas, Snapshot(), t, 16)
    assert overlay.toast_bottom > ac.TOP
    below = overlay.toast_bottom + 3
    assert _bar_fill(overlay_canvas, top=below) > 0 and _bar_fill(overlay_canvas) == 0
    for t in range(1400, 1400 + scenes_toast_ms() + 600, 16):           # the toast's gone: back up
        overlay.draw(overlay_canvas, Snapshot(), t, 16)
    assert _bar_fill(overlay_canvas) > 0


def scenes_toast_ms():
    from overlay.scenes import TOAST_MS
    return TOAST_MS


def test_the_trays_watcher_hears_each_new_line():
    from core.launcher_activity import ActivityWatcher
    clock = Clock(100.0)
    act = LauncherActivity(clock)
    lines = []
    w = ActivityWatcher(act, lines.append)
    w.tick()
    assert lines == []                                          # nothing going on
    act.start("saves", "Syncing saves", total=2)
    w.tick()
    w.tick()
    act.progress(1)
    w.tick()
    act.finish("2 uploaded")
    w.tick()
    clock.t += la.DONE_S + 1
    w.tick()
    assert lines == ["Syncing saves (0 of 2)", "Syncing saves (1 of 2)", "Syncing saves: done", None]
