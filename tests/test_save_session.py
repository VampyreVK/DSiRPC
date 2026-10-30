"""core/save_session.py through core/console_sync.py over loopback TCP, with a
stand-in for the launcher (launcher/source/savesync.c): the plan, uploads in
each kind (dated by the console's time), downloads, history, a restore, the
summary event, damaged and bad requests, a launcher from another release,
and save backups turned off."""

import os
import socket
import struct
import time

import pytest

from core import save_session as ss
from core import saves
from core.console_sync import ConsoleSync
from core.saves import crc32

HOST = "127.0.0.1"
CODE, HCRC = "IRBO", 0x1A2B
MAC = bytes.fromhex("0009bf123f21")


def talk(port, data, read_answer):
    with socket.create_connection((HOST, port), timeout=5) as s:
        s.sendall(data)
        buf = bytearray()

        def read(n):
            while len(buf) < n:
                chunk = s.recv(65536)
                if not chunk:
                    raise ConnectionError("DSiRPC hung up")
                buf.extend(chunk)
            out = bytes(buf[:n])
            del buf[:n]
            return out
        return read_answer(read)


def plan(port, entries, backup_only=False, model=0):
    def answer(read):
        magic, status, n = struct.unpack("<4sHH", read(8))
        items = []
        for _ in range(n):
            code, hcrc, slot, action, size, crc, when, versions, src_len = ss.PLAN_ITEM.unpack(read(ss.PLAN_ITEM.size))
            items.append({"code": code.decode(), "slot": slot, "action": action, "size": size, "crc": crc,
                          "time": when, "versions": versions, "source": read(src_len).decode()})
        return magic, status, items
    return talk(port, ss.request(ss.OP_PLAN, ss.plan_body(entries), MAC, model, backup_only), answer)


def put(port, data, kind, slot=0, crc=None, model=0, name=b"Pokemon Black", when=0):
    body = ss.PUT.pack(CODE.encode(), HCRC, slot, kind, len(data), crc32(data) if crc is None else crc,
                       when, len(name)) + name + data
    return talk(port, ss.request(ss.OP_PUT, body, MAC, model), lambda read: struct.unpack("<4sH", read(6)))


def get(port, version=0, flags=0, slot=0):
    def answer(read):
        magic, status, size, crc = struct.unpack("<4sHII", read(14))
        return magic, status, read(size), crc
    body = ss.GET.pack(CODE.encode(), HCRC, slot, version, flags)
    return talk(port, ss.request(ss.OP_GET, body, MAC, 2), answer)


def history(port, slot=0):
    def answer(read):
        magic, status, n = struct.unpack("<4sHH", read(8))
        out = []
        for _ in range(n):
            version, when, size, crc, src_len = ss.HIST_ITEM.unpack(read(ss.HIST_ITEM.size))
            out.append((version, size, crc, read(src_len).decode(), when))
        return magic, status, out
    return talk(port, ss.request(ss.OP_HIST, ss.HIST.pack(CODE.encode(), HCRC, slot), MAC), answer)


def entry(data, base=0, present=True, slot=0):
    return {"code": CODE, "hcrc": HCRC, "slot": slot, "present": present, "crc": crc32(data) if data else 0,
            "base": base, "name": "Pokemon Black", "size": len(data or b"")}


@pytest.fixture
def server(tmp_path):
    started = []

    def go(enabled=True):
        store = saves.SaveStore(str(tmp_path / "saves"), keep=5) if enabled else None
        events = []
        sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host=HOST,
                           saves=lambda: store, on_saves=events.append)
        sync.start()
        started.append(sync)
        return sync.port, store, events
    yield go
    for s in started:
        s.stop()


def test_plan_upload_download(server):
    port, store, events = server()
    v1, v2 = b"\x01" * 512, b"\x02" * 512
    magic, status, items = plan(port, [entry(v1)])
    assert (magic, status) == (b"DRSP", ss.OK)
    assert [(i["slot"], i["action"]) for i in items] == [(0, saves.UPLOAD)]
    assert put(port, v1, saves.PUT_SYNC) == (b"DRSK", ss.OK)
    assert store.latest("IRBO-1A2B", 0)["source"] == "DSi 3F21"
    # The 3DS hasn't played since its last sync (with this PC: its save is here as a backup): it's
    # offered the DSi's newer save, keeps its own in history first, then takes it
    assert put(port, v2, saves.PUT_BACKUP, model=2) == (b"DRSK", ss.OK)
    _, _, items = plan(port, [entry(v2, base=crc32(v2))], model=2)
    assert items[0]["action"] == saves.DOWNLOAD and items[0]["crc"] == crc32(v1) and items[0]["source"] == "DSi 3F21"
    _, _, items = plan(port, [entry(b"\x03" * 512, base=crc32(v2))], model=2)
    assert items[0]["action"] == saves.CONFLICT                       # played on both since
    assert put(port, v2, saves.PUT_SAFETY, model=2) == (b"DRSK", ss.OK)
    magic, status, data, crc = get(port)
    assert (magic, status, data, crc) == (b"DRSD", ss.OK, v1, crc32(v1))
    assert talk(port, ss.request(ss.OP_DONE, ss.DONE.pack(1, 1, 0, 0), MAC, 2),
                lambda read: struct.unpack("<4sH", read(6))) == (b"DRSK", ss.OK)
    # The event comes after the answer (the console isn't kept waiting for the
    # tray), so it may be a moment behind it
    deadline = time.monotonic() + 5
    while events[-1]["type"] != "saves_synced" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert events[-1] == {"type": "saves_synced", "console": "3DS 3F21", "uploaded": 1, "downloaded": 1,
                          "backed_up": 0, "failed": 0}


def test_history_and_restore(server):
    port, store, _ = server()
    versions = [bytes([i]) * 256 for i in range(1, 4)]
    for v in versions:
        assert put(port, v, saves.PUT_SYNC)[1] == ss.OK
    magic, status, h = history(port)
    assert (magic, status) == (b"DRSL", ss.OK)
    assert [(v, c) for v, _, c, _, _ in h] == [(0, crc32(versions[2])), (1, crc32(versions[1])), (2, crc32(versions[0]))]
    # Backup only: version 2 comes down, nothing changes here
    _, status, data, _ = get(port, version=2)
    assert status == ss.OK and data == versions[0] and store.latest("IRBO-1A2B", 0)["crc"] == crc32(versions[2])
    # Sync mode's restore: it becomes the latest too
    _, status, data, _ = get(port, version=2, flags=ss.GET_MAKE_LATEST)
    assert status == ss.OK and data == versions[0] and store.latest("IRBO-1A2B", 0)["crc"] == crc32(versions[0])
    assert get(port, version=9)[1] == ss.NOT_FOUND


def test_backup_only_over_the_wire(server):
    port, store, _ = server()
    v = b"\x05" * 128
    _, _, items = plan(port, [entry(v)], backup_only=True)
    assert items[0]["action"] == saves.BACKUP
    assert put(port, v, saves.PUT_BACKUP)[1] == ss.OK
    _, _, items = plan(port, [entry(v, base=crc32(v))], backup_only=True)
    assert items[0]["action"] == saves.IN_SYNC and store.latest("IRBO-1A2B", 0) is None


def test_damaged_and_bad_requests(server):
    port, store, _ = server()
    assert put(port, b"save", saves.PUT_SYNC, crc=1234) == (b"DRSK", ss.DAMAGED)
    assert store.latest("IRBO-1A2B", 0) is None
    bad = ss.request(ss.OP_PUT, ss.PUT.pack(b"ir!o", HCRC, 0, 1, 0, 0, 0, 0), MAC)
    assert talk(port, bad, lambda read: struct.unpack("<4sH", read(6))) == (b"DRSK", ss.BAD_REQUEST)
    # A launcher from another release (another version of the exchange) is told so
    wrong_version = ss.HEADER.pack(ss.MAGIC, 1, 0, MAC, 0, ss.OP_PLAN) + b"\0\0"
    assert talk(port, wrong_version, lambda read: struct.unpack("<4sHH", read(8))) == (b"DRSP", ss.OTHER_RELEASE, 0)


def test_save_backups_off(server):
    port, _, _ = server(enabled=False)
    assert plan(port, [entry(b"save")])[1] == ss.OFF
    assert put(port, b"save", saves.PUT_SYNC) == (b"DRSK", ss.OFF)


def test_uploads_keep_the_consoles_time(server):
    port, store, _ = server()
    written = 1_760_000_000                         # when the console wrote the save (a PC time)
    t1 = saves.to_console_time(written)             # as the console counts
    v1, v2 = b"\x07" * 256, b"\x08" * 256
    assert put(port, v1, saves.PUT_SYNC, when=t1)[1] == ss.OK
    folder = os.path.join(store.root, store.data["games"]["IRBO-1A2B"]["folder"])
    rec = store.latest("IRBO-1A2B", 0)
    assert int(rec["time"]) == written and int(os.stat(os.path.join(folder, rec["file"])).st_mtime) == written
    # The next one pushes it into history, which keeps its date (in the name too)
    assert put(port, v2, saves.PUT_SYNC, when=t1 + 3600)[1] == ss.OK
    _, _, h = history(port)
    assert [when for *_, when in h] == [t1 + 3600, t1]
    old = store.history("IRBO-1A2B", 0)[1]
    assert int(os.stat(os.path.join(folder, old["file"])).st_mtime) == written
    assert saves.datetime.datetime.fromtimestamp(written).strftime("%Y-%m-%d %H-%M-%S") in old["file"]
    # A console that can't tell (0), or whose clock can't be right: the time it arrived
    for when in (0, 60):
        v = bytes([when + 1]) * 64
        assert put(port, v, saves.PUT_BACKUP, when=when)[1] == ss.OK
        kept = next(r for r in store.history("IRBO-1A2B", 0) if r["crc"] == crc32(v))
        assert abs(kept["time"] - saves.time.time()) < 60


def test_a_file_held_for_a_moment(server, monkeypatch):
    """Windows won't replace a file another program has open (a cloud drive's
    client, an antivirus): the store tries again for a moment, and when it
    can't, the launcher hears so instead of losing the connection."""
    port, store, _ = server()
    real = saves.os.replace
    held = {"left": 2}

    def replace(src, dst):
        if held["left"]:
            held["left"] -= 1
            raise PermissionError(13, "in use by another program")
        return real(src, dst)
    monkeypatch.setattr(saves.os, "replace", replace)
    monkeypatch.setattr(saves.time, "sleep", lambda s: None)
    assert put(port, b"held a moment", saves.PUT_SYNC) == (b"DRSK", ss.OK)
    assert store.read(saves.game_key(CODE, HCRC), 0)[0] == b"held a moment" and held["left"] == 0

    held["left"] = 99                            # held for good: the save isn't stored
    assert put(port, b"held for good", saves.PUT_SYNC) == (b"DRSK", ss.CANT_STORE)

    def stuck(*a, **k):                          # saves.json held while planning
        raise PermissionError(13, "in use by another program")
    monkeypatch.setattr(store, "plan", stuck)
    answer = talk(port, ss.request(ss.OP_PLAN, ss.plan_body([]), MAC), lambda read: struct.unpack("<4sHH", read(8)))
    assert answer == (b"DRSP", ss.CANT_STORE, 0)  # answered, so the launcher tries again
