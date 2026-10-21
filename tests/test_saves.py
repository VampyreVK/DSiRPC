"""core/saves.py, the PC's copy of the console's saves: the three-way plan
(sync and backup-only), history (kept, pruned, never lost on a replace),
restores, damaged uploads, a save changed by hand in the folder, and the
manifest surviving a restart."""

import os

import pytest

from core import saves
from core.saves import (BACKUP, CONFLICT, DOWNLOAD, DOWNLOAD_NEW, EXCLUDED, IN_SYNC, PUT_BACKUP, PUT_SAFETY,
                        PUT_SYNC, UPLOAD, SaveStore, crc32, game_key)

CODE, HCRC = "IRBO", 0x1A2B
KEY = game_key(CODE, HCRC)


def entry(slot=0, present=True, data=None, base=0, excluded=False, code=CODE, hcrc=HCRC, name="Pokemon Black"):
    return {"code": code, "hcrc": hcrc, "slot": slot, "present": present,
            "crc": crc32(data) if data is not None else 0, "base": base, "excluded": excluded, "name": name}


def actions(store, entries, backup_only=False):
    return [(i["slot"], i["action"]) for i in store.plan(entries, backup_only)]


@pytest.fixture
def store(tmp_path):
    return SaveStore(str(tmp_path / "saves"), keep=3)


def test_the_three_way_plan(store):
    v1, v2, v3 = b"save one", b"save two", b"save three"
    assert actions(store, [entry(data=v1)]) == [(0, UPLOAD)]             # new to the PC
    store.put(KEY, 0, "Pokemon Black", v1, crc32(v1), PUT_SYNC, "DSi 0001")
    assert actions(store, [entry(data=v1, base=crc32(v1))]) == [(0, IN_SYNC)]
    assert actions(store, [entry(data=v2, base=crc32(v1))]) == [(0, UPLOAD)]       # only the console changed
    store.put(KEY, 0, "Pokemon Black", v2, crc32(v2), PUT_SYNC, "3DS 0002")
    assert actions(store, [entry(data=v1, base=crc32(v1))]) == [(0, DOWNLOAD)]     # only the PC's changed
    assert actions(store, [entry(data=v3, base=crc32(v1))]) == [(0, CONFLICT)]     # both did
    assert actions(store, [entry(data=v3, base=0)]) == [(0, CONFLICT)]             # first sync, and they differ
    assert actions(store, [entry(data=v2, base=0)]) == [(0, IN_SYNC)]              # first sync, the same save
    assert actions(store, [entry(data=v3, excluded=True)]) == [(0, EXCLUDED)]


def test_saves_the_console_doesnt_have(store):
    store.put(KEY, 0, "Pokemon Black", b"slot 0", crc32(b"slot 0"), PUT_SYNC, "DSi 0001")
    store.put(KEY, 1, "Pokemon Black", b"slot 1", crc32(b"slot 1"), PUT_SYNC, "DSi 0001")
    # The ROM is there but no save: both slots come down
    assert sorted(actions(store, [entry(present=False)])) == [(0, DOWNLOAD_NEW), (1, DOWNLOAD_NEW)]
    # A slot 0 save of its own, but no slot 1
    v = b"slot 0"
    assert sorted(actions(store, [entry(data=v, base=crc32(v))])) == [(0, IN_SYNC), (1, DOWNLOAD_NEW)]
    # No ROM listed, nothing offered; nothing kept, nothing to list
    assert actions(store, [entry(present=False, code="CPUE")]) == []
    # Backup only never takes anything
    assert actions(store, [entry(present=False)], backup_only=True) == []


def test_backup_only(store):
    v1, v2 = b"save one", b"save two"
    assert actions(store, [entry(data=v1)], backup_only=True) == [(0, BACKUP)]
    store.put(KEY, 0, "Pokemon Black", v1, crc32(v1), PUT_BACKUP, "3DS 0002")
    assert actions(store, [entry(data=v1, base=crc32(v1))], backup_only=True) == [(0, IN_SYNC)]
    assert actions(store, [entry(data=v2, base=crc32(v1))], backup_only=True) == [(0, BACKUP)]
    # Thinks it's backed up, but the PC doesn't have it (a new backups folder)
    assert actions(store, [entry(data=v2, base=crc32(v2))], backup_only=True) == [(0, BACKUP)]
    # Backups never become the latest that sync-mode consoles share
    assert store.latest(KEY, 0) is None and store.history(KEY, 0)[0]["source"] == "3DS 0002"


def test_history_is_kept_and_pruned(store, tmp_path):
    versions = [f"version {i}".encode() for i in range(6)]
    for i, v in enumerate(versions):
        store.put(KEY, 0, "Pokemon Black", v, crc32(v), PUT_SYNC, "DSi 0001", when=1_700_000_000 + i * 60)
    h = store.history(KEY, 0)
    assert [r["version"] for r in h] == [0, 1, 2, 3]                      # the latest, then 3 kept (keep=3)
    assert store.read(KEY, 0, 0)[0] == versions[5]
    assert [store.read(KEY, 0, n)[0] for n in (1, 2, 3)] == [versions[4], versions[3], versions[2]]
    folder = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]"
    assert (folder / "Pokemon Black.sav").read_bytes() == versions[5]
    assert len(os.listdir(folder / "history")) == 3                       # the pruned files are gone
    # Uploading the same save again changes nothing
    assert not store.put(KEY, 0, "Pokemon Black", versions[5], crc32(versions[5]), PUT_SYNC, "DSi 0001")


def test_a_replaced_console_save_goes_to_history(store):
    pc, console = b"the PC's", b"the console's"
    store.put(KEY, 0, "Pokemon Black", pc, crc32(pc), PUT_SYNC, "DSi 0001")
    assert store.put(KEY, 0, "Pokemon Black", console, crc32(console), PUT_SAFETY, "3DS 0002")
    assert not store.put(KEY, 0, "Pokemon Black", console, crc32(console), PUT_SAFETY, "3DS 0002")   # kept already
    h = store.history(KEY, 0)
    assert h[0]["crc"] == crc32(pc) and h[1]["crc"] == crc32(console) and h[1]["reason"] == "replaced"
    assert store.backed_up(KEY, 0, crc32(console))


def test_restore(store):
    old, new = b"old save", b"new save"
    store.put(KEY, 0, "Pokemon Black", old, crc32(old), PUT_SYNC, "DSi 0001")
    store.put(KEY, 0, "Pokemon Black", new, crc32(new), PUT_SYNC, "DSi 0001")
    data, rec = store.restore(KEY, 0, 1, "3DS 0002")
    assert data == old and rec["crc"] == crc32(old) and store.latest(KEY, 0)["crc"] == crc32(old)
    assert store.history(KEY, 0)[1]["crc"] == crc32(new)                  # the replaced latest is kept
    # Every console in sync with `new` is offered the restored save
    assert actions(store, [entry(data=new, base=crc32(new))]) == [(0, DOWNLOAD)]


def test_dated_by_the_consoles_time(store, tmp_path):
    folder = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]"
    store.put(KEY, 0, "Pokemon Black", b"one", crc32(b"one"), PUT_SYNC, "DSi 0001", when=1_700_000_000)
    assert int((folder / "Pokemon Black.sav").stat().st_mtime) == 1_700_000_000
    store.put(KEY, 0, "Pokemon Black", b"kept", crc32(b"kept"), PUT_SAFETY, "3DS 0002", when=1_700_003_600)
    kept = store.history(KEY, 0)[1]
    assert int((folder / kept["file"]).stat().st_mtime) == 1_700_003_600 == int(kept["time"])
    store.put(KEY, 0, "Pokemon Black", b"two", crc32(b"two"), PUT_SYNC, "DSi 0001", when=1_700_007_200)
    # A restore keeps the version's own time (file and record)
    one = next(v for v in store.history(KEY, 0) if v["crc"] == crc32(b"one"))
    store.restore(KEY, 0, one["version"], "DSi 0001")
    assert int(store.latest(KEY, 0)["time"]) == 1_700_000_000
    assert int((folder / "Pokemon Black.sav").stat().st_mtime) == 1_700_000_000
    assert saves.from_console_time(saves.to_console_time(1_700_000_000)) == 1_700_000_000
    assert saves.from_console_time(0) is None and saves.from_console_time(60) is None   # unknown, 2000


def test_damaged_uploads_and_files(store, tmp_path):
    with pytest.raises(saves.SaveError):
        store.put(KEY, 0, "Pokemon Black", b"save", 1234, PUT_SYNC, "DSi 0001")
    with pytest.raises(saves.SaveError):
        store.read(KEY, 0, 0)
    store.put(KEY, 0, "Pokemon Black", b"save", crc32(b"save"), PUT_SYNC, "DSi 0001")
    hist = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]" / "history"
    store.put(KEY, 0, "Pokemon Black", b"save 2", crc32(b"save 2"), PUT_SYNC, "DSi 0001")
    (hist / os.listdir(hist)[0]).write_bytes(b"tampered")
    with pytest.raises(saves.SaveError):
        store.read(KEY, 0, 1)


def test_a_save_copied_into_the_folder_by_hand(store, tmp_path):
    v1 = b"from the DSi"
    store.put(KEY, 0, "Pokemon Black", v1, crc32(v1), PUT_SYNC, "DSi 0001")
    latest = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]" / "Pokemon Black.sav"
    latest.write_bytes(b"from an emulator")
    os.utime(latest, (1_800_000_000, 1_800_000_000))
    assert actions(store, [entry(data=v1, base=crc32(v1))]) == [(0, DOWNLOAD)]
    rec = store.latest(KEY, 0)
    assert rec["source"] == "PC" and rec["crc"] == crc32(b"from an emulator")
    assert store.read(KEY, 0, 0)[0] == b"from an emulator"
    latest.unlink()                                                       # deleted by hand: the console's goes up again
    assert actions(store, [entry(data=v1, base=crc32(v1))]) == [(0, UPLOAD)]


def test_the_manifest_survives_a_restart(store, tmp_path):
    store.put(KEY, 0, "Pokemon Black", b"save", crc32(b"save"), PUT_SYNC, "DSi 0001")
    again = SaveStore(str(tmp_path / "saves"), keep=3)
    assert again.latest(KEY, 0)["crc"] == crc32(b"save") and again.read(KEY, 0)[0] == b"save"
    (tmp_path / "saves" / "saves.json").write_text("{ not json")
    assert SaveStore(str(tmp_path / "saves")).latest(KEY, 0) is None      # unreadable: a fresh start, no crash


def test_names_and_labels():
    assert saves.safe_name('Pokémon: Black/White?', "x") == "Pokémon BlackWhite"
    assert saves.safe_name("...", "IRBO-1A2B") == "IRBO-1A2B"
    assert saves.console_label(2, bytes.fromhex("0009bf123f21")) == "3DS 3F21"
    assert saves.console_label(0, bytes.fromhex("0009bf123f21")) == "DSi 3F21"
    assert saves.slot_ext(0) == ".sav" and saves.slot_ext(3) == ".sav3"
