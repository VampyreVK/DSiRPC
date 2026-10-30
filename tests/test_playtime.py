"""Playtimes, for the launcher's modern look: DSiRPC's side (core/playtime.py:
counting, the file, the exchange through ConsoleSync) and, end to end, the
launcher's (launcher/source/stats.c, in tests/c/update's host built for the
PC): the answer kept in stats.idx, a DSiRPC from before playtimes, and the
look's settings in launcher.ini."""

import calendar
import json
import os
import socket
import subprocess
import threading
import time

import pytest

from core import offline, playtime as pt
from core.console_sync import ConsoleSync
from helpers import REPO, cbuild

LAUNCHER = os.path.join(REPO, "launcher", "source")
HOST = os.path.join(REPO, "tests", "c", "update", "update_host.c")
SD = os.path.join("sd:", "DSiRPC")
INFO = {'pc': "VIV-PC", 'ra': "Viv", 'discord': True}


def played(tmp_path, ticks):
    p = pt.Playtime(str(tmp_path / "playtime.json"))
    for code, t in ticks:
        p.tick(code, now=t)
    return p


# -- counting --------------------------------------------------------------------

def test_the_time_between_ticks_counts(tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1005), ("CPUE", 1010)])
    assert p.games() == {"CPUE": (10, 1010)}


def test_a_long_gap_isnt_played(tmp_path):
    later = 1005 + pt.GAP + 1      # the console slept
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1005), ("CPUE", later), ("CPUE", later + 5)])
    assert p.games()["CPUE"] == (10, later + 5)


def test_each_game_counts_its_own(tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("IRBO", 1005), ("IRBO", 1010), ("CPUE", 1012)])
    assert p.games() == {"CPUE": (0, 1012), "IRBO": (5, 1010)}


def test_no_game_or_a_bad_code_isnt_counted(tmp_path):
    p = played(tmp_path, [(None, 1000), ("cpue", 1001), ("CP", 1002), ("", 1003)])
    assert p.games() == {}


def test_they_are_kept(tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1030)])
    p.flush()
    with open(p.path, encoding="utf-8") as f:
        assert json.load(f) == {"CPUE": {"seconds": 30, "last": 1030}}
    assert pt.Playtime(p.path).games() == {"CPUE": (30, 1030)}


def test_a_damaged_file_starts_over(tmp_path):
    path = tmp_path / "playtime.json"
    path.write_text("{not json")
    assert pt.Playtime(str(path)).games() == {}
    path.write_text(json.dumps({"CPUE": {"seconds": "x"}, "bad!": {}, "IRBO": {"seconds": 5, "last": 7}}))
    assert pt.Playtime(str(path)).games() == {"IRBO": (5, 7)}


def test_the_console_counts_local_time_since_2000():
    t = 1730239200
    assert pt.console_time(t) == calendar.timegm(time.localtime(t)) - 946684800
    assert pt.console_time(0) == 0


# -- the exchange ------------------------------------------------------------------

def answer_for(req, times, info):
    data, out = bytearray(req[4:]), []

    def read(n):
        chunk = bytes(data[:n])
        del data[:n]
        return chunk

    pt.handle(req[:4], read, out.append, times, info)
    return b"".join(out)


def test_the_answer(tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1030), ("IRBO", 2000)])
    status, flags, pc, ra, games = pt.parse_answer(answer_for(pt.request(), p, INFO))
    assert (status, flags, pc, ra) == (pt.OK, 1, "VIV-PC", "Viv")
    assert games == {"CPUE": (30, pt.console_time(1030)), "IRBO": (0, pt.console_time(2000))}


def test_not_signed_in_and_nothing_played():
    status, flags, pc, ra, games = pt.parse_answer(answer_for(pt.request(), None, {'pc': "X", 'ra': ""}))
    assert (status, flags, pc, ra, games) == (pt.OK, 0, "X", "", {})


def test_another_version_is_turned_down(tmp_path):
    p = played(tmp_path, [("CPUE", 1000)])
    assert pt.parse_answer(answer_for(pt.request(version=2), p, INFO))[0] == pt.BAD_REQUEST


def test_through_console_sync(tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1012)])
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", stats=lambda: (p, INFO))
    sync.start()
    try:
        with socket.create_connection(("127.0.0.1", sync.port), timeout=5) as s:
            s.sendall(pt.request())
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if len(data) >= pt.ANSWER.size + 6 + 3 + pt.ENTRY.size:
                    break
        assert pt.parse_answer(data)[4] == {"CPUE": (12, pt.console_time(1012))}
    finally:
        sync.stop()


# -- end to end, with the launcher's side --------------------------------------

@pytest.fixture(scope="module")
def host(cc, tmp_path_factory):
    exe = str(tmp_path_factory.mktemp("playtime") / "update_host")
    sources = [HOST] + [os.path.join(LAUNCHER, f)
                        for f in ("update.c", "sync.c", "settings.c", "bootstrap_ini.c", "stats.c")]
    return cbuild.build(exe, sources, flags=["-std=gnu11", "-I", LAUNCHER])


def run(host, port, sd, *commands):
    os.makedirs(os.path.join(sd, SD), exist_ok=True)
    r = subprocess.run([host, str(port)], input="\n".join(commands) + "\n", capture_output=True, text=True,
                       cwd=sd, env=cbuild.run_env(), timeout=60)
    assert r.returncode == 0, r.stderr
    assert not any(ln.startswith("?") for ln in r.stdout.splitlines()), r.stdout
    return r.stdout.splitlines()


def test_the_launcher_keeps_them(host, tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1030), ("IRBO", 2000)])
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", stats=lambda: (p, INFO))
    sync.start()
    sd = str(tmp_path / "console")
    try:
        out = run(host, sync.port, sd, "stats sd:/DSiRPC")
    finally:
        sync.stop()
    assert out[0] == "stats 1|VIV-PC|Viv|1|2|"
    assert out[1:] == [f"game CPUE|30|{pt.console_time(1030)}", f"game IRBO|0|{pt.console_time(2000)}"]
    with open(os.path.join(sd, SD, "stats.idx"), encoding="ascii") as f:
        assert f.read().splitlines()[:4] == ["DSiRPC stats 1", "pc VIV-PC", "ra Viv", "discord 1"]


def test_a_dsirpc_from_before_playtimes(host, tmp_path):
    """It takes the request for an offline sync and turns it down ("DRSA"):
    nothing changes on the SD card."""
    srv = socket.create_server(("127.0.0.1", 0))

    def old_dsirpc():
        conn, _ = srv.accept()
        with conn:
            data = b""
            while len(data) < offline.REQUEST.size:
                data += conn.recv(64)
            conn.sendall(offline.build_answer(1, 0, []))
            try:
                conn.recv(64)       # its hang-up
            except OSError:
                pass

    t = threading.Thread(target=old_dsirpc, daemon=True)
    t.start()
    sd = str(tmp_path / "console")
    os.makedirs(os.path.join(sd, SD))
    with open(os.path.join(sd, SD, "stats.idx"), "w", encoding="ascii") as f:
        f.write("DSiRPC stats 1\npc OLD\nra \ndiscord 0\nCPUE 5 6\n")
    out = run(host, srv.getsockname()[1], sd, "stats sd:/DSiRPC")
    t.join(5)
    srv.close()
    assert out == ["stats 0|OLD||0|1|", "game CPUE|5|6"]


def test_the_look_settings(host, tmp_path):
    sd = str(tmp_path / "console")
    os.makedirs(os.path.join(sd, SD))
    with open(os.path.join(sd, SD, "old.ini"), "w", encoding="ascii") as f:
        f.write("[LAUNCHER]\r\nSAVE_MODE = sync\r\n")      # from before the looks
    out = run(host, 1, sd, "look sd:/DSiRPC/old.ini|-|-|-|-", "look sd:/DSiRPC/launcher.ini|1|0|2|0",
              "look sd:/DSiRPC/launcher.ini|0|1|1|2", "look sd:/DSiRPC/launcher.ini|0|1|9|1")
    assert out == ["look 0|0|1|0|1",    # the defaults: modern, sounds on, recent first, Bright
                   "look 1|1|0|2|0", "look 1|0|1|1|2",
                   "look 1|0|1|0|1"]    # not an order: recent
    with open(os.path.join(sd, SD, "launcher.ini"), encoding="ascii") as f:
        text = f.read()
    assert "LOOK = modern" in text and "SOUNDS = on" in text and "GAME_SORT = recent" in text
    assert "MUSIC = bright" in text

    # MUSIC's words, any case; one it doesn't know is the default
    for word, music in (("off", 0), ("Subtle", 2), ("BRIGHT", 1), ("loud", 1)):
        with open(os.path.join(sd, SD, "music.ini"), "w", encoding="ascii") as f:
            f.write(f"[LAUNCHER]\r\nMUSIC = {word}\r\n")
        assert run(host, 1, sd, "look sd:/DSiRPC/music.ini|-|-|-|-") == [f"look 0|0|1|0|{music}"]
