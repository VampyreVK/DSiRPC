"""The launcher's save sync end to end: launcher/source/savesync.c (with
sync.c and settings.c) built for the PC, talking to DSiRPC's ConsoleSync and
SaveStore on loopback, on SD cards in temporary folders. A DSi and a 3DS
(different file names for the same game) share saves, the two-stage check
(stray saves left out, saves already in sync not counted), the PC's copies
dated by the console's clock, conflicts both ways, restores, back-up-only
mode, exclusions, a swap that didn't finish, and the launcher's settings."""

import os
import subprocess

import pytest

from core import saves
from core.console_sync import ConsoleSync
from helpers import REPO, cbuild

LAUNCHER = os.path.join(REPO, "launcher", "source")
HOST = os.path.join(REPO, "tests", "c", "savesync", "savesync_host.c")
DSI = "0009BF120001|0|sync"
DSI_BACKUP = "0009BF120001|0|backup"
THREE_DS = "0009BF120002|2|sync"
UPLOAD, DOWNLOAD, CONFLICT, BACKUP, EXCLUDED, DOWNLOAD_NEW = (saves.UPLOAD, saves.DOWNLOAD, saves.CONFLICT,
                                                               saves.BACKUP, saves.EXCLUDED, saves.DOWNLOAD_NEW)


def rom(code, hcrc=0x1A2B):
    header = bytearray(0x200)
    header[0:12] = b"TEST GAME\0\0\0"
    header[0x0C:0x10] = code.encode()
    header[0x15E] = hcrc & 0xFF
    header[0x15F] = hcrc >> 8
    return bytes(header)


@pytest.fixture(scope="module")
def host(cc, tmp_path_factory):
    exe = str(tmp_path_factory.mktemp("savesync") / "savesync_host")
    sources = [HOST] + [os.path.join(LAUNCHER, f) for f in ("savesync.c", "sync.c", "settings.c", "bootstrap_ini.c")]
    return cbuild.build(exe, sources, flags=["-std=gnu11", "-I", LAUNCHER])


@pytest.fixture
def pc(tmp_path):
    store = saves.SaveStore(str(tmp_path / "pc saves"), keep=5)
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", saves=lambda: store)
    sync.start()
    yield sync.port, store
    sync.stop()


class Console:
    """An SD card in a folder, and the launcher's save sync run on it."""

    def __init__(self, host, port, folder, console=DSI):
        self.host, self.port, self.root, self.console = host, port, folder, console
        os.makedirs(os.path.join(folder, "sd:", "DSiRPC"), exist_ok=True)

    def put(self, path, data):
        p = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)

    def read(self, path):
        with open(os.path.join(self.root, path), "rb") as f:
            return f.read()

    def exists(self, path):
        return os.path.exists(os.path.join(self.root, path))

    def run(self, *commands, scan=True):
        lines = [f"console {self.console}"]
        if scan:
            lines.append("scan sd:/roms/nds|sd:/DSiRPC")
        lines += list(commands)
        r = subprocess.run([self.host, str(self.port)], input="\n".join(lines) + "\n", capture_output=True,
                           text=True, cwd=self.root, env=cbuild.run_env(), timeout=120)
        assert r.returncode == 0, r.stderr
        assert "?" not in [ln.split(" ")[0] for ln in r.stdout.splitlines()], r.stdout
        return r.stdout.splitlines()


def items(lines):
    out = {}
    for ln in lines:
        if ln.startswith("item "):
            name, slot, present, changed, excluded, crc, base, path = ln[5:].split("|")
            out[(name, int(slot))] = {"present": present == "1", "changed": changed == "1",
                                      "excluded": excluded == "1", "crc": int(crc, 16), "base": int(base, 16),
                                      "path": path}
    return out


def actions(lines):
    assert any(ln.startswith("plan 1") for ln in lines), lines
    return {(ln[7:].split("|")[0], int(ln[7:].split("|")[1])): int(ln[7:].split("|")[2])
            for ln in lines if ln.startswith("action ")}


def test_a_dsi_and_a_3ds_share_their_saves(host, pc, tmp_path):
    port, store = pc
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"black slot 0" * 100)
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav1", b"black slot 1" * 100)
    dsi.put("sd:/roms/nds/Puzzles/Picross.nds", rom("APKE", 0x0042))   # a subfolder, no save yet
    out = dsi.run("plan", "sync *", "done")
    found = items(out)
    assert set(found) == {("Pokemon Black", 0), ("Pokemon Black", 1), ("Picross", 0)}
    assert not found[("Picross", 0)]["present"] and found[("Pokemon Black", 0)]["changed"]
    assert actions(out) == {("Pokemon Black", 0): UPLOAD, ("Pokemon Black", 1): UPLOAD}
    assert "counts 2 0 0 0" in out
    key = saves.game_key("IRBO", 0x1A2B)
    assert store.read(key, 0)[0] == b"black slot 0" * 100 and store.read(key, 1)[0] == b"black slot 1" * 100
    assert store.latest(key, 0)["source"] == "DSi 0001"

    # Nothing changed: in sync, nothing to send
    again = dsi.run("plan")
    assert not any(v["changed"] for v in items(again).values())
    assert set(actions(again).values()) == {saves.IN_SYNC}

    # The 3DS names the game differently and has no save: it gets both slots,
    # in its game's "saves" folder
    three = Console(host, port, str(tmp_path / "3ds"), THREE_DS)
    three.put("sd:/roms/nds/POKEMON_B.nds", rom("IRBO"))
    out = three.run("plan", "sync *")
    assert actions(out) == {("POKEMON_B", 0): DOWNLOAD_NEW, ("POKEMON_B", 1): DOWNLOAD_NEW}
    assert any(ln.startswith("action POKEMON_B|0|") and ln.endswith("|DSi 0001") for ln in out)   # whose it is
    assert "counts 0 2 0 0" in out
    assert three.read("sd:/roms/nds/saves/POKEMON_B.sav") == b"black slot 0" * 100
    assert three.read("sd:/roms/nds/saves/POKEMON_B.sav1") == b"black slot 1" * 100
    assert set(actions(three.run("plan")).values()) == {saves.IN_SYNC}


def test_the_two_stage_check(host, pc, tmp_path):
    port, _ = pc
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"save 1" * 50)
    assert dsi.run("quick sd:/roms/nds|sd:/DSiRPC", scan=False) == ["console ok", "quick -1"]   # never synced
    dsi.run("plan", "sync *")
    assert dsi.run("quick sd:/roms/nds|sd:/DSiRPC", scan=False)[-1] == "quick 0"
    # nds-bootstrap only touched it (a new time, the same save): not a change
    save = os.path.join(dsi.root, "sd:/roms/nds/saves/Pokemon Black.sav")
    os.utime(save, (1_900_000_000, 1_900_000_000))
    assert dsi.run("quick sd:/roms/nds|sd:/DSiRPC", scan=False)[-1] == "quick 0"
    assert not items(dsi.run())[("Pokemon Black", 0)]["changed"]
    # Played and saved, and a new game's first save; a save no game is named
    # after (a renamed backup) doesn't count
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"save 2" * 50)
    dsi.put("sd:/roms/nds/Puzzles/Picross.nds", rom("APKE", 0x0042))
    dsi.put("sd:/roms/nds/saves/Picross.sav", b"new")
    dsi.put("sd:/roms/nds/saves/(Backup) Pokemon Black.sav", b"an old copy")
    assert dsi.run("quick sd:/roms/nds|sd:/DSiRPC", scan=False)[-1] == "quick 2"
    assert ("(Backup) Pokemon Black", 0) not in items(dsi.run())


def test_dated_copies_and_saves_already_in_sync(host, pc, tmp_path):
    port, store = pc
    key = saves.game_key("IRBO", 0x1A2B)
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"black")
    os.utime(os.path.join(dsi.root, "sd:/roms/nds/saves/Pokemon Black.sav"), (1_760_000_000, 1_760_000_000))
    dsi.run("plan", "sync *")
    # The PC's copy is dated when the DSi wrote the save (its clock's time), not when it arrived
    written = int(saves.from_console_time(1_760_000_000 - 946_684_800))
    rec = store.latest(key, 0)
    assert int(rec["time"]) == written
    assert int(os.stat(os.path.join(store.root, store.data["games"][key]["folder"], rec["file"])).st_mtime) == written
    # A 3DS that already has the very same save (copied over by hand): in sync, and from its
    # first look at the list on, not counted as changed at startup
    three = Console(host, port, str(tmp_path / "3ds"), THREE_DS)
    three.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    three.put("sd:/roms/nds/saves/Pokemon Black.sav", b"black")
    assert actions(three.run("plan")) == {("Pokemon Black", 0): saves.IN_SYNC}
    assert three.run("quick sd:/roms/nds|sd:/DSiRPC", scan=False)[-1] == "quick 0"


def test_conflicts_both_ways(host, pc, tmp_path):
    port, store = pc
    key = saves.game_key("IRBO", 0x1A2B)
    dsi = Console(host, port, str(tmp_path / "dsi"))
    three = Console(host, port, str(tmp_path / "3ds"), THREE_DS)
    for c in (dsi, three):
        c.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"start")
    dsi.run("plan", "sync *")
    three.run("plan", "sync *")
    # Both play
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"the DSi's adventure")
    three.put("sd:/roms/nds/saves/Pokemon Black.sav", b"the 3DS's adventure")
    assert actions(dsi.run("plan", "sync *"))[("Pokemon Black", 0)] == UPLOAD
    out = three.run("plan", "sync Pokemon Black|0")
    assert actions(out)[("Pokemon Black", 0)] == CONFLICT
    assert "sync Pokemon Black|0 0 " in out                       # asked, not answered: nothing done
    # The 3DS takes the PC's: its own goes into history first
    out = three.run("plan", "sync Pokemon Black|0|take")
    assert "sync Pokemon Black|0 1 " in out
    assert three.read("sd:/roms/nds/saves/Pokemon Black.sav") == b"the DSi's adventure"
    assert store.backed_up(key, 0, saves.crc32(b"the 3DS's adventure"))
    # And the other way: the 3DS plays on and keeps its own over the DSi's
    three.put("sd:/roms/nds/saves/Pokemon Black.sav", b"the 3DS again")
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"the DSi again")
    dsi.run("plan", "sync *")
    out = three.run("plan", "sync Pokemon Black|0|keep")
    assert "sync Pokemon Black|0 1 " in out
    assert store.read(key, 0)[0] == b"the 3DS again" and store.backed_up(key, 0, saves.crc32(b"the DSi again"))
    assert actions(dsi.run("plan"))[("Pokemon Black", 0)] == DOWNLOAD
    # Each console's saves in a folder of its own, next to the live save
    folder = os.path.join(store.root, store.data["games"][key]["folder"])
    assert sorted(os.listdir(os.path.join(folder, "backups"))) == ["3DS 0002", "DSi 0001"]
    assert open(os.path.join(folder, "Pokemon Black.sav"), "rb").read() == b"the 3DS again"


def test_a_save_changed_behind_saves_idxs_back(host, pc, tmp_path):
    """saves.idx vouches for a save whose size and time haven't changed. One
    rewritten in place with its time put back still goes up with the CRC of
    what's sent (it was turned down as damaged), and a download the list
    planned over it stops instead of replacing it."""
    port, store = pc
    key = saves.game_key("CPUE", 0x5A5A)
    path = "sd:/roms/nds/saves/Platinum.sav"
    dsi = Console(host, port, str(tmp_path / "dsi"))
    three = Console(host, port, str(tmp_path / "3ds"), THREE_DS)
    for c in (dsi, three):
        c.put("sd:/roms/nds/Platinum.nds", rom("CPUE", 0x5A5A))
    dsi.put(path, b"first!" * 1000)
    dsi.run("plan", "sync *")

    def in_place(data):
        full = os.path.join(dsi.root, path)
        st = os.stat(full)
        dsi.put(path, data)
        os.utime(full, ns=(st.st_atime_ns, st.st_mtime_ns))

    # Played (a new time: saves.idx reads it), then written again in place
    dsi.put(path, b"second" * 1000)
    later = os.stat(os.path.join(dsi.root, path)).st_mtime + 10
    os.utime(os.path.join(dsi.root, path), (later, later))
    dsi.run("plan")
    in_place(b"third!" * 1000)
    out = dsi.run("plan", "sync Platinum|0")
    assert actions(out)[("Platinum", 0)] == UPLOAD and "sync Platinum|0 1 " in out
    assert store.read(key, 0)[0] == b"third!" * 1000

    # The 3DS's save is the live one now; the DSi's changes in place again
    three.put(path, b"the 3DS's")
    three.run("plan", "sync Platinum|0|keep")
    in_place(b"fourth" * 1000)
    out = dsi.run("plan", "sync Platinum|0")
    assert actions(out)[("Platinum", 0)] == DOWNLOAD                  # the list didn't know
    assert any(ln.startswith("sync Platinum|0 -1 This save changed since the") for ln in out)
    assert dsi.read(path) == b"fourth" * 1000                          # not replaced
    assert store.backed_up(key, 0, saves.crc32(b"fourth" * 1000))     # and on the PC
    assert actions(dsi.run("plan"))[("Platinum", 0)] == CONFLICT       # yours to settle


def test_restore_an_older_version(host, pc, tmp_path):
    port, store = pc
    key = saves.game_key("IRBO", 0x1A2B)
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    for v in (b"monday", b"tuesday", b"wednesday"):
        dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", v)
        dsi.run("plan", "sync *")
    out = dsi.run("plan", "versions Pokemon Black|0")
    versions = [ln[8:].split("|") for ln in out if ln.startswith("version ")]
    assert [(int(v), int(c, 16)) for v, _, c, _ in versions] == [
        (0, saves.crc32(b"wednesday")), (1, saves.crc32(b"tuesday")), (2, saves.crc32(b"monday"))]
    out = dsi.run("plan", "restore Pokemon Black|0|2")
    assert "restore 1 " in out
    assert dsi.read("sd:/roms/nds/saves/Pokemon Black.sav") == b"monday"
    assert store.latest(key, 0)["crc"] == saves.crc32(b"monday")        # sync mode: the others get it too
    assert set(actions(dsi.run("plan")).values()) == {saves.IN_SYNC}


def test_backup_only(host, pc, tmp_path):
    port, store = pc
    key = saves.game_key("IRBO", 0x1A2B)
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"shared")
    dsi.run("plan", "sync *")
    mine = Console(host, port, str(tmp_path / "mine"), DSI_BACKUP)
    mine.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    mine.put("sd:/roms/nds/saves/Pokemon Black.sav", b"my own save")
    out = mine.run("plan", "sync *")
    assert actions(out) == {("Pokemon Black", 0): BACKUP} and "counts 0 0 1 0" in out
    assert mine.read("sd:/roms/nds/saves/Pokemon Black.sav") == b"my own save"   # never replaced
    assert store.read(key, 0)[0] == b"shared"                                     # nor the shared one
    assert store.backed_up(key, 0, saves.crc32(b"my own save"))
    assert set(actions(mine.run("plan")).values()) == {saves.IN_SYNC}


def test_excluded_saves_stay_out(host, pc, tmp_path):
    port, store = pc
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav", b"private")
    assert "exclude 1 1" in dsi.run("exclude Pokemon Black|0")
    out = dsi.run("plan", "sync *")
    assert items(out)[("Pokemon Black", 0)]["excluded"]
    assert actions(out) == {("Pokemon Black", 0): EXCLUDED} and "counts 0 0 0 0" in out
    assert store.latest(saves.game_key("IRBO", 0x1A2B), 0) is None


def test_a_swap_that_didnt_finish(host, pc, tmp_path):
    port, _ = pc
    dsi = Console(host, port, str(tmp_path / "dsi"))
    dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav.bak", b"the old save")       # switched off mid-swap
    dsi.put("sd:/roms/nds/saves/Pokemon Black.sav.tmp", b"half a download")
    found = items(dsi.run())
    assert found[("Pokemon Black", 0)]["present"]
    assert dsi.read("sd:/roms/nds/saves/Pokemon Black.sav") == b"the old save"
    assert not dsi.exists("sd:/roms/nds/saves/Pokemon Black.sav.bak")
    assert not dsi.exists("sd:/roms/nds/saves/Pokemon Black.sav.tmp")


def test_dsirpc_without_save_backups(host, tmp_path):
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", saves=lambda: None)
    sync.start()
    try:
        dsi = Console(host, sync.port, str(tmp_path / "dsi"))
        dsi.put("sd:/roms/nds/Pokemon Black.nds", rom("IRBO"))
        out = dsi.run("plan")
        assert any(ln.startswith("plan -1 Save backups are off") for ln in out), out
    finally:
        sync.stop()


def test_the_launchers_settings(host, pc, tmp_path):
    port, _ = pc
    dsi = Console(host, port, str(tmp_path / "dsi"))
    out = dsi.run("settings sd:/DSiRPC/launcher.ini|192.168.1.20|backup", scan=False)
    assert out[-1] == "settings 1 192.168.1.20 1 C0A80114 -"
    out = dsi.run("settings sd:/DSiRPC/launcher.ini|-|sync|sd:/roms/nds/Pokemon Black (USA).nds", scan=False)
    assert out[-1] == "settings 1 - 0 00000000 sd:/roms/nds/Pokemon Black (USA).nds"    # START in the picker
    out = dsi.run("settings sd:/DSiRPC/check.ini|10.0.0.256|sync", scan=False)
    assert out[-1] == "settings 1 - 0 00000000 -"                     # not an address: looked for instead
