"""What the launcher is doing, on the PC (core/launcher_activity.py): the
tracker itself; the offline sync, the save sync and the console updates
telling it as they go (core/console_sync.py, core/save_session.py through
app/engine.py, core/console_update.py); Discord while the console is in the
launcher (rpc/generic_presence.py's launcher_presence(), through
rpc/presence_connector.py); and the popup (app/activity_popup.py): when it
shows, and that it draws."""

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
    req = cu.request(cu.OP_GET, cu.LAUNCHER, model=3)
    rest = req[4:]
    out = []

    def read(n):
        nonlocal rest
        chunk, rest = rest[:n], rest[n:]
        return chunk
    cu.handle(req[:4], read, out.append, files, progress=lambda *a: heard.append(a))
    assert heard[0] == ("the launcher", 0, len(data), "3DS")
    assert [h[1] for h in heard] == [0, cu.CHUNK, cu.CHUNK * 2, len(data)]

    # through ConsoleSync's, a file at a time
    act = LauncherActivity()
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST, activity=act)
    for what, sent, total, console in heard:
        sync._update_progress(what, sent, total, console)
    v = act.current()
    assert (v['kind'], v['detail'], v['summary'], v['console'], v['finished'] is not None) == \
        ("update", "Sending the launcher", "Sent the launcher", "3DS", True)


def test_the_save_sync_tells_it(tmp_path):
    """core/save_session.py's events, through the engine's _save_activity():
    the plan says how many saves move, each upload or download counts one
    (not the copy kept before a download), the summary at the end"""
    from app.engine import Engine
    act = LauncherActivity()
    engine = SimpleNamespace(activity=act)
    store = saves.SaveStore(str(tmp_path / "saves"), keep=5)
    events = []

    def on_saves(e):
        events.append(e)
        Engine._save_activity(engine, e)
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST, saves=lambda: store, on_saves=on_saves)
    sync.start()
    try:
        from test_save_session import entry, plan, put, talk, MAC
        port = sync.port
        v1 = b"\x01" * 512
        plan(port, [entry(v1)])
        assert _wait(lambda: act.active("saves"))
        assert act.current()['total'] == 1 and act.current()['detail'] == "1 save to move"
        put(port, v1, saves.PUT_SYNC)
        assert _wait(lambda: act.current()['done'] == 1)
        assert act.current()['detail'] == "Uploaded Pokemon Black"
        put(port, v1, saves.PUT_SAFETY)                       # (not counted)
        talk(port, ss.request(ss.OP_DONE, ss.DONE.pack(1, 0, 0, 0), MAC), lambda read: read(6))
        assert _wait(lambda: act.current()['finished'] is not None)
        v = act.current()
        assert (v['done'], v['total'], v['summary'], v['ok'], v['console']) == (1, 1, "1 uploaded", True, "DSi")
        assert events[0]["type"] == "save_plan" and events[0]["moves"] == 1
    finally:
        sync.stop()


def test_a_save_sync_with_nothing_to_move_shows_nothing():
    act = LauncherActivity()
    from app.engine import Engine
    engine = SimpleNamespace(activity=act)
    Engine._save_activity(engine, {"type": "save_plan", "console": "DSi 3F21", "saves": 4, "moves": 0,
                                   "conflicts": 0})
    Engine._save_activity(engine, {"type": "saves_synced", "console": "DSi 3F21", "uploaded": 0,
                                   "downloaded": 0, "backed_up": 0, "failed": 0})
    assert act.current() is None


# -- Discord in the launcher ---------------------------------------------------------

def test_the_launchers_presence():
    from rpc import generic_presence as gp
    p = gp.launcher_presence({'console': "3DS", 'game': None, 'ip': "10.0.0.5"}, None, start=1234)
    assert p["name"] == "DSiRPC" and p["details"] == "In the launcher" and p["state"] == "Ready to play"
    assert p["large_text"] == "3DS on DSiRPC" and p["large_image"].endswith("/Pixel.gif")
    assert "small_image" not in p and "small_text" not in p and p["start"] == 1234
    p = gp.launcher_presence({'console': "DSi", 'game': "CPUE", 'title': "Pokémon Platinum"}, "Syncing saves (2 of 5)")
    assert p["large_text"] == "DSi on DSiRPC"
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
    assert d.last_sent["large_text"] == "3DS on DSiRPC" and d.status == "would show DSiRPC"
    started = d.start
    d.last_time = 0     # (past Discord's gap)
    d.on_update(Snapshot(None, False, 0, "", dict(launcher, game="CPUE", title="Pokémon Platinum")), [])
    assert d.last_sent["details"] == "Starting Pokémon Platinum" and d.start == started   # the same timer
    d.on_update(Snapshot(None, False, 0, "", None), [])
    assert d.last_sent is None and d.status == "waiting for the game"                   # gone: cleared


# -- the popup ------------------------------------------------------------------------

def _view(**k):
    v = {'kind': "saves", 'title': "Syncing saves", 'detail': "", 'done': 0, 'total': 0, 'unit': "",
         'console': "DSi", 'started': 100.0, 'changed': 100.0, 'finished': None, 'summary': "", 'ok': True,
         'generation': 3}
    v.update(k)
    return v


def test_when_the_popup_shows():
    from app.activity_popup import SHOW_AFTER, should_show
    assert not should_show(None, 100.0, 0, 0)
    assert not should_show(_view(), 100.0 + SHOW_AFTER / 2, 0, 0)             # a quick one never shows
    assert should_show(_view(), 100.0 + SHOW_AFTER, 0, 0)                      # a slow one does
    assert not should_show(_view(finished=100.2), 100.3, 0, 0)                 # done before it showed: not now
    assert should_show(_view(finished=105.0), 105.1, 3, 0)                     # done after: it says so
    assert not should_show(_view(), 110.0, 3, 3)                               # clicked away
    assert should_show(_view(generation=4), 110.0, 3, 3)                       # till the next one


def test_the_popup_draws(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    from app import activity_popup as ap
    from overlay import ui
    pygame.display.init()
    try:
        painter = ap.Painter()
        canvas = pygame.Surface((ap.W, ap.H))
        drawn = {}
        for name, view in (("spinner", _view()), ("count", _view(total=5, done=2, detail="Uploaded Pokemon Black")),
                           ("bytes", _view(total=100, done=40, unit="bytes")),
                           ("done", _view(finished=101.0, summary="2 uploaded")),
                           ("failed", _view(finished=101.0, ok=False, summary="Lost the console"))):
            painter.draw(canvas, view, 1234)
            drawn[name] = {tuple(canvas.get_at((x, y)))[:3] for x in range(ap.W) for y in range(ap.H)}
            assert len(drawn[name]) > 6, name
        assert ui.THEME['hp_yellow'] in drawn["spinner"]                   # no count: the block going back and forth
        assert ui.THEME['hp_green'] in drawn["count"] and ui.THEME['hp_green'] in drawn["done"]
        assert ui.THEME['hp_red'] in drawn["failed"] and ui.THEME['hp_red'] not in drawn["done"]
        assert ap.count_text(_view(total=5, done=2)) == "2 of 5"
        assert ap.count_text(_view(total=100, done=40, unit="bytes")) == "40%"
        assert ap.count_text(_view(finished=1.0, total=5)) == ""
    finally:
        pygame.display.quit()


def test_the_popup_watcher_sends_only_changes():
    from app import activity_popup as ap
    clock = Clock(100.0)
    act = LauncherActivity(clock)
    lines, sent = [], []
    popup = ap.ActivityPopup(act, on_line=lines.append)
    popup._send = sent.append
    popup.tick(now=100.0)
    assert sent == [] and lines == []                           # nothing going on
    act.start("saves", "Syncing saves", total=2)
    popup.tick(now=clock.t)
    popup.tick(now=clock.t + 0.5)
    assert lines == ["Syncing saves (0 of 2)"] and sent == []          # not shown yet
    clock.t += 1.5
    popup.tick(now=clock.t)
    popup.tick(now=clock.t)
    assert len(sent) == 1 and sent[-1][1]['title'] == "Syncing saves"  # shown, once
    act.finish("2 uploaded")
    popup.tick(now=clock.t)
    assert sent[-1][1]['finished'] is not None and lines[-1] == "Syncing saves: done"
    clock.t += la.DONE_S + 1
    popup.tick(now=clock.t)
    assert sent[-1] == ('view', None) and lines[-1] is None
