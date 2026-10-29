"""core/saves.py, the PC's copy of the console's saves: the three-way plan
(sync and backup-only), each console's backups next to the live save (kept,
pruned, never lost on a replace), what each console last had, restores,
dates, damaged uploads, saves put in the folder by hand (External ones and
copies of backups), the first layout upgraded, and the manifest surviving a
restart."""

import json
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


def actions(store, entries, backup_only=False, console=None):
    return [(i["slot"], i["action"]) for i in store.plan(entries, backup_only, console)]


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


def test_backups_are_kept_and_pruned(store, tmp_path):
    versions = [f"version {i}".encode() for i in range(6)]
    for i, v in enumerate(versions):
        store.put(KEY, 0, "Pokemon Black", v, crc32(v), PUT_SYNC, "DSi 0001", when=1_700_000_000 + i * 60)
    # The live save, then the console's last 3 backups (keep=3), the newest of which is the live save over
    # again: listed once
    h = store.history(KEY, 0)
    assert [r["version"] for r in h] == [0, 1, 2]
    assert [store.read(KEY, 0, n)[0] for n in (0, 1, 2)] == [versions[5], versions[4], versions[3]]
    folder = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]"
    assert (folder / "Pokemon Black.sav").read_bytes() == versions[5]
    assert len(os.listdir(folder / "backups" / "DSi 0001")) == 3          # the pruned files are gone
    assert [b["crc"] for b in store.backups(KEY, 0)] == [crc32(v) for v in versions[3:]]
    # Uploading the same save again changes nothing
    assert not store.put(KEY, 0, "Pokemon Black", versions[5], crc32(versions[5]), PUT_SYNC, "DSi 0001")


def test_a_backup_folder_for_each_console(store, tmp_path):
    dsi, three = b"the DSi's adventure", b"the 3DS's adventure"
    store.put(KEY, 0, "Pokemon Black", dsi, crc32(dsi), PUT_SYNC, "DSi 0001")
    store.put(KEY, 0, "Pokemon Black", three, crc32(three), PUT_SYNC, "3DS 0002")
    backups = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]" / "backups"
    assert sorted(os.listdir(backups)) == ["3DS 0002", "DSi 0001"]
    assert store.latest(KEY, 0)["source"] == "3DS 0002"                   # the live save: the newest
    assert [(b["source"], b["crc"]) for b in store.backups(KEY, 0)] == [("DSi 0001", crc32(dsi)),
                                                                         ("3DS 0002", crc32(three))]
    # Each console's backups are pruned on their own
    for i in range(5):
        v = f"DSi save {i}".encode()
        store.put(KEY, 0, "Pokemon Black", v, crc32(v), PUT_BACKUP, "DSi 0001")
    assert len(store.backups(KEY, 0, "DSi 0001")) == 3 and len(store.backups(KEY, 0, "3DS 0002")) == 1
    # What each console last had: the save it sent
    assert store.console_had(KEY, 0, "3DS 0002")["crc"] == crc32(three)


def test_what_a_console_had_counts_when_it_forgot(store):
    """A console whose saves.idx is gone (a new SD card, say) sends no base:
    what DSiRPC remembers it had decides instead of a conflict."""
    v1, v2, v3 = b"save one", b"save two", b"save three"
    store.put(KEY, 0, "Pokemon Black", v1, crc32(v1), PUT_SYNC, "DSi 0001")
    store.put(KEY, 0, "Pokemon Black", v2, crc32(v2), PUT_SYNC, "3DS 0002")
    assert actions(store, [entry(data=v1)], console="DSi 0001") == [(0, DOWNLOAD)]   # unchanged since: take v2
    assert actions(store, [entry(data=v3)], console="DSi 0001") == [(0, CONFLICT)]   # played on both
    assert actions(store, [entry(data=v3)], console="3DS 0002") == [(0, UPLOAD)]     # only it played since
    assert actions(store, [entry(data=v3)]) == [(0, CONFLICT)]                       # nobody it knows
    # A console in sync is noted as having the live save
    assert actions(store, [entry(data=v2)], console="DSi 0001") == [(0, IN_SYNC)]
    assert store.console_had(KEY, 0, "DSi 0001") == {"crc": crc32(v2), "from": "3DS 0002",
                                                      "time": store.console_had(KEY, 0, "DSi 0001")["time"]}


def test_a_console_that_last_synced_with_another_pc(tmp_path):
    """A console synced its newer save with one PC (its saves.idx says so),
    then meets another PC whose live save is older: that PC never saw the
    console's base, so it's no reason to take its save. It's a conflict, not
    a download over the newer save (Pokemon Black from the 29th, offered the
    Mac's from the 24th)."""
    pc, mac = SaveStore(str(tmp_path / "pc"), keep=3), SaveStore(str(tmp_path / "mac"), keep=3)
    older, newer = b"the 24th, from the 3DS", b"the 29th, on the DSi"
    mac.put(KEY, 0, "Pokemon Black", older, crc32(older), PUT_SYNC, "3DS 0002")
    pc.put(KEY, 0, "Pokemon Black", newer, crc32(newer), PUT_SYNC, "DSi 0001")    # the DSi's base is now this
    assert actions(mac, [entry(data=newer, base=crc32(newer))], console="DSi 0001") == [(0, CONFLICT)]
    assert mac.console_had(KEY, 0, "DSi 0001") is None       # and the PC's base isn't taken as what it had
    assert actions(pc, [entry(data=newer, base=crc32(newer))], console="DSi 0001") == [(0, IN_SYNC)]

    # What the Mac remembers of the console still decides
    mac.put(KEY, 0, "Pokemon Black", older, crc32(older), PUT_SAFETY, "DSi 0001")
    assert actions(mac, [entry(data=newer, base=crc32(newer))], console="DSi 0001") == [(0, CONFLICT)]
    mine = b"the DSi, after the Mac's"
    mac.put(KEY, 0, "Pokemon Black", mine, crc32(mine), PUT_SYNC, "DSi 0001")
    pc_base = crc32(newer)                                    # its saves.idx still has the PC's
    assert actions(mac, [entry(data=mine, base=pc_base)], console="DSi 0001") == [(0, IN_SYNC)]


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
    # Still the DSi's save (the 3DS only restored it), and the replaced live save is kept
    assert rec["source"] == "DSi 0001" and rec["restored_by"] == "3DS 0002"
    assert store.history(KEY, 0)[1]["crc"] == crc32(new)
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
    folder = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]"
    store.put(KEY, 0, "Pokemon Black", b"save 2", crc32(b"save 2"), PUT_SYNC, "DSi 0001")
    (folder / store.history(KEY, 0)[1]["file"]).write_bytes(b"tampered")
    with pytest.raises(saves.SaveError):
        store.read(KEY, 0, 1)


def test_a_save_copied_into_the_folder_by_hand(store, tmp_path):
    v1 = b"from the DSi"
    store.put(KEY, 0, "Pokemon Black", v1, crc32(v1), PUT_SYNC, "DSi 0001")
    latest = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]" / "Pokemon Black.sav"
    latest.write_bytes(b"from an emulator")
    os.utime(latest, (1_800_000_000, 1_800_000_000))
    assert actions(store, [entry(data=v1, base=crc32(v1))]) == [(0, DOWNLOAD)]
    # The live save now, and kept as an External backup too (the live copy stays where it was put)
    rec = store.latest(KEY, 0)
    assert rec["source"] == "External" and rec["crc"] == crc32(b"from an emulator")
    assert store.read(KEY, 0, 0)[0] == b"from an emulator" and latest.read_bytes() == b"from an emulator"
    assert [b["source"] for b in store.backups(KEY, 0) if b["crc"] == crc32(b"from an emulator")] == ["External"]
    # A copy of one of the backups instead: the live save again, as that console's
    latest.write_bytes(v1)
    os.utime(latest, (1_800_000_100, 1_800_000_100))
    assert actions(store, [entry(data=b"x", base=crc32(b"x"))]) == [(0, CONFLICT)]   # a base it never saw
    assert store.latest(KEY, 0)["source"] == "DSi 0001"
    latest.unlink()                                                       # deleted by hand: the console's goes up again
    assert actions(store, [entry(data=v1, base=crc32(v1))]) == [(0, UPLOAD)]


def test_saves_put_anywhere_else_in_the_folder(store, tmp_path):
    v1 = b"from the DSi"
    store.put(KEY, 0, "Pokemon Black", v1, crc32(v1), PUT_SYNC, "DSi 0001")
    folder = tmp_path / "saves" / "Pokemon Black [IRBO-1A2B]"
    (folder / "from my emulator.sav").write_bytes(b"an emulator's save")
    (folder / "backups" / "a copy.sav").write_bytes(v1)                   # a copy of the DSi's backup
    (folder / "notes.txt").write_text("not a save")
    store.plan([], False)
    # Listed as an External backup the consoles can restore; the live save stays as it was
    h = store.history(KEY, 0)
    assert store.latest(KEY, 0)["crc"] == crc32(v1)
    assert [(r["source"], r["crc"]) for r in h] == [("DSi 0001", crc32(v1)), ("External", crc32(b"an emulator's save"))]
    assert store.read(KEY, 0, 1)[0] == b"an emulator's save"
    # The copy counts as the DSi's backup it is (not listed twice), and nothing put there by hand is pruned
    assert sum(bool(b.get("by_hand")) for b in store.backups(KEY, 0, "DSi 0001") if b["crc"] == crc32(v1)) == 1
    for i in range(5):
        v = f"later {i}".encode()
        store.put(KEY, 0, "Pokemon Black", v, crc32(v), PUT_SYNC, "DSi 0001")
    assert (folder / "from my emulator.sav").exists() and (folder / "backups" / "a copy.sav").exists()
    # A save in a slot's live place, with no live save there yet: the live save of that slot
    (folder / "Pokemon Black.sav2").write_bytes(b"slot 2, by hand")
    store.plan([], False)
    assert store.latest(KEY, 2)["source"] == "External" and store.read(KEY, 2)[0] == b"slot 2, by hand"


def test_the_first_layout_is_upgraded(tmp_path):
    root = tmp_path / "saves"
    folder = root / "Pokemon Black [IRBO-1A2B]"
    (folder / "history").mkdir(parents=True)
    (folder / "Pokemon Black.sav").write_bytes(b"latest")
    (folder / "history" / "Pokemon Black 2026-10-20 14-02-11 (3DS 0002).sav").write_bytes(b"older")
    latest = {"file": "Pokemon Black.sav", "crc": crc32(b"latest"), "size": 6, "time": 1_760_000_000,
              "source": "DSi 0001", "reason": "sync", "mtime": int((folder / "Pokemon Black.sav").stat().st_mtime)}
    older = {"file": os.path.join("history", "Pokemon Black 2026-10-20 14-02-11 (3DS 0002).sav"),
             "crc": crc32(b"older"), "size": 5, "time": 1_759_990_000, "source": "3DS 0002", "reason": "sync"}
    (root / "saves.json").write_text(json.dumps({"version": 1, "games": {KEY: {
        "name": "Pokemon Black", "folder": "Pokemon Black [IRBO-1A2B]",
        "slots": {"0": {"latest": latest, "history": [older]}}}}}))
    store = SaveStore(str(root), keep=3)
    assert store.latest(KEY, 0)["crc"] == crc32(b"latest")
    assert [(r["source"], store.read(KEY, 0, r["version"])[0]) for r in store.history(KEY, 0)] == [
        ("DSi 0001", b"latest"), ("3DS 0002", b"older")]
    assert not (folder / "history").exists()
    assert sorted(os.listdir(folder / "backups")) == ["3DS 0002", "DSi 0001"]      # the live save got one too
    assert json.loads((root / "saves.json").read_text())["version"] == 2


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
