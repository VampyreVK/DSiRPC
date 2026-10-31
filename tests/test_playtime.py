"""DSiRPC playtime, for the launcher's modern look: DSiRPC's side
(core/playtime.py: counting, the file, the exchange through ConsoleSync, the
console's higher numbers taken) and, end to end, the launcher's
(launcher/source/stats.c, in tests/c/update's host built for the PC): the
higher of each number kept on both sides in stats.idx and playtime.json, a
DSiRPC that only knows version 1 of the exchange, one from before playtimes,
offline play from the unlock file's playtime slots added once, and the
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
from helpers import REPO, cbuild, launcher_ui

LAUNCHER = os.path.join(REPO, "launcher", "source")
HOST = os.path.join(REPO, "tests", "c", "update", "update_host.c")
SD = os.path.join("sd:", "DSiRPC")
INFO = {'pc': "VIV-PC", 'ra': "Viv", 'discord': True}
T = 1730000000      # Oct 2024: the console counts from 2000


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


def test_the_launcher_calls_a_mac_macos(monkeypatch):
    monkeypatch.setattr(pt.socket, "gethostname", lambda: "GAMING-PC.lan")
    monkeypatch.setattr(pt.sys, "platform", "win32")
    assert pt.pc_name() == "GAMING-PC"
    monkeypatch.setattr(pt.socket, "gethostname", lambda: "MacBookPro.local")
    monkeypatch.setattr(pt.sys, "platform", "darwin")
    assert pt.pc_name() == "macOS"


def test_another_version_is_turned_down(tmp_path):
    p = played(tmp_path, [("CPUE", 1000)])
    assert pt.parse_answer(answer_for(pt.request(version=3), p, INFO))[0] == pt.BAD_REQUEST


def test_the_consoles_higher_numbers_count(tmp_path):
    """Version 2: the console's numbers come first; each one counts where
    it's higher (a game played with another PC), never lower"""
    p = played(tmp_path, [("CPUE", T + 1000), ("CPUE", T + 1030), ("IRBO", T + 2000), ("IRBO", T + 2040)])
    console = {"CPUE": (9000, pt.console_time(T + 5000)),    # more, and later
               "IRBO": (10, pt.console_time(T + 100)),       # less, and earlier: stays the PC's
               "ADME": (77, pt.console_time(T + 3000))}      # only on the console
    status, _, _, _, games = pt.parse_answer(answer_for(pt.request(games=console), p, INFO))
    assert status == pt.OK
    assert games == {"CPUE": (9000, pt.console_time(T + 5000)), "IRBO": (40, pt.console_time(T + 2040)),
                     "ADME": (77, pt.console_time(T + 3000))}
    assert pt.Playtime(p.path).games() == {"CPUE": (9000, T + 5000), "IRBO": (40, T + 2040), "ADME": (77, T + 3000)}
    # Counting goes on from there
    p.tick("CPUE", now=T + 5001)
    p.tick("CPUE", now=T + 5011)
    assert p.games()["CPUE"] == (9010, T + 5011)


def test_version_1_still_works(tmp_path):
    p = played(tmp_path, [("CPUE", 1000), ("CPUE", 1030)])
    assert pt.parse_answer(answer_for(pt.request(version=1), p, INFO))[4] == {"CPUE": (30, pt.console_time(1030))}


def test_the_consoles_clock_back_to_a_unix_time():
    for t in (946684800 + 86400, 1730239200, 1761800000):
        assert pt.unix_time(pt.console_time(t)) == t
    assert pt.unix_time(0) == 0


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


def write_stats(sd, games):
    os.makedirs(os.path.join(sd, SD), exist_ok=True)
    with open(os.path.join(sd, SD, "stats.idx"), "w", encoding="ascii") as f:
        f.write("DSiRPC stats 1\npc OTHER-PC\nra \ndiscord 0\n")
        for code, (secs, last) in games.items():
            f.write(f"{code} {secs} {last}\n")


def test_the_higher_number_wins_both_ways(host, tmp_path):
    """The console played Platinum longer with another PC and Animal
    Crossing only there; this PC played Black longer: both end up with the
    higher of each"""
    p = played(tmp_path, [("CPUE", T + 1000), ("CPUE", T + 1030), ("IRBO", T + 2000), ("IRBO", T + 2050)])
    sd = str(tmp_path / "console")
    write_stats(sd, {"CPUE": (9000, pt.console_time(T + 5000)), "IRBO": (10, pt.console_time(T + 100)),
                     "ADME": (77, pt.console_time(T + 3000))})
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", stats=lambda: (p, INFO))
    sync.start()
    try:
        out = run(host, sync.port, sd, "stats sd:/DSiRPC")
    finally:
        sync.stop()
    assert out[0] == "stats 1|VIV-PC|Viv|1|3|"      # the PC's name now
    assert sorted(out[1:]) == sorted([f"game CPUE|9000|{pt.console_time(T + 5000)}",
                                      f"game IRBO|50|{pt.console_time(T + 2050)}",
                                      f"game ADME|77|{pt.console_time(T + 3000)}"])
    assert pt.Playtime(p.path).games() == {"CPUE": (9000, T + 5000), "IRBO": (50, T + 2050), "ADME": (77, T + 3000)}


def test_a_dsirpc_that_only_knows_version_1(host, tmp_path):
    """It turns version 2 down; the launcher asks again with 1, and keeps the
    higher numbers itself"""
    p = played(tmp_path, [("CPUE", T + 1000), ("CPUE", T + 1030)])
    srv = socket.create_server(("127.0.0.1", 0))
    versions = []

    def old_dsirpc():
        for _ in range(2):
            conn, _ = srv.accept()
            with conn:
                data = b""
                while len(data) < pt.HEADER.size:
                    data += conn.recv(64)
                version = pt.HEADER.unpack(data[:pt.HEADER.size])[1]
                versions.append(version)
                if version != 1:
                    conn.sendall(pt.ANSWER.pack(b"DRGA", pt.BAD_REQUEST, 0, 0, 0, 0))
                    continue
                answer = []
                pt.handle(data[:4], lambda n, d=data[4:]: d[:n], answer.append, p, INFO)
                conn.sendall(b"".join(answer))
                return

    t = threading.Thread(target=old_dsirpc, daemon=True)
    t.start()
    sd = str(tmp_path / "console")
    write_stats(sd, {"CPUE": (9000, pt.console_time(T + 5000)), "ADME": (77, pt.console_time(T + 3000))})
    out = run(host, srv.getsockname()[1], sd, "stats sd:/DSiRPC")
    t.join(5)
    srv.close()
    assert versions == [2, 1]
    assert out[0] == "stats 1|VIV-PC|Viv|1|2|"
    assert sorted(out[1:]) == sorted([f"game CPUE|9000|{pt.console_time(T + 5000)}",
                                      f"game ADME|77|{pt.console_time(T + 3000)}"])
    assert p.games() == {"CPUE": (30, T + 1030)}     # it never heard


def test_offline_play_is_added_once(host, tmp_path):
    """As it starts, the launcher adds each start's playtime the game left in
    RPCUNLK.BIN to stats.idx, and clears those slots: never twice, and the
    unlocks waiting stay for DSiRPC"""
    sd = str(tmp_path / "console")
    write_stats(sd, {"CPUE": (1000, 5)})
    unlocks = launcher_ui.unlock_file([(4242, "CPUE", 777), (offline.PLAYTIME_ID, "CPUE", 600),
                                       (offline.PLAYTIME_ID, "IRBO", 90)])   # a game not in stats.idx yet
    path = os.path.join(sd, "sd:", "RPCUNLK.BIN")
    with open(path, "wb") as f:
        f.write(unlocks)
    out = run(host, 1, sd, "played sd:/DSiRPC|sd:/RPCUNLK.BIN")
    assert out[0] == "played 2|2" and sorted(out[1:]) == ["game CPUE|1600", "game IRBO|90"]
    with open(path, "rb") as f:
        data = f.read()
    assert data[:32] == unlocks[:32] and data[32:64] == bytes(32) and offline.count_unlocks(data) == 1
    assert run(host, 1, sd, "played sd:/DSiRPC|sd:/RPCUNLK.BIN")[0] == "played 0|2"


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
