"""
saves.py - the PC's copy of the console's game saves, for the launcher's
save sync (core/save_session.py has the exchange, launcher/source/savesync.c
the console's side).

Each game has a folder of its own in the backups folder (dsirpc.cfg's
[saves] folder, by default saves/ in DSiRPC's folder), named after the game
and its key, the game code plus the ROM header's CRC (so a ROM hack that kept
the original's code doesn't get its saves, and a DSi and a 3DS that named the
same ROM differently still share them):

    Pokemon Black [IRBO-1A2B]/
        Pokemon Black.sav            the latest save (slot 0; .sav1 to .sav9
                                     for TWiLight Menu++'s other save slots)
        history/
            Pokemon Black 2026-10-20 14-02-11 (DSi 3F21).sav

The latest save is the one consoles in sync mode share: one that changed
there is uploaded and becomes the latest (the old one goes into history),
and one that changed here (a newer save from another console, or a restored
version) is offered to the others. A console in backup-only mode never
takes anything: its changed saves only go into history. history/ keeps the
last `keep` versions of each save (dsirpc.cfg's versions, 10 by default),
and nothing is ever replaced without its old version going there first.

saves.json in the backups folder lists it all, with each version's CRC32
(zlib's), size, time and where it came from.

Whether a save changed is decided three ways, the way RetroAchievements'
cloud sync and Syncthing do: the console sends each save's CRC now and its
CRC at the last sync (the base), so

    console's == latest            in sync
    latest == base                 only the console changed: upload
    console's == base              only the PC's changed: download
    otherwise                      both changed: the console asks

No clocks are compared: a DSi's clock is whatever its owner set.
"""

import datetime
import json
import logging
import os
import re
import threading
import zlib

# What the plan says to do with each save (the same numbers in savesync.h)
IN_SYNC, UPLOAD, DOWNLOAD, CONFLICT, BACKUP, EXCLUDED, DOWNLOAD_NEW = range(7)
ACTION_NAMES = ["in sync", "upload", "download", "conflict", "backup", "excluded", "download (new)"]

# How an uploaded save is kept
PUT_SYNC, PUT_BACKUP, PUT_SAFETY = 1, 2, 3

MAX_SLOT = 9
MAX_SAVE_SIZE = 16 * 1024 * 1024
DEFAULT_KEEP = 10
MANIFEST = "saves.json"
EPOCH_2000 = datetime.datetime(2000, 1, 1)


class SaveError(Exception):
    pass


def game_key(code, header_crc):
    return f"{code}-{header_crc & 0xFFFF:04X}"


def slot_ext(slot):
    return ".sav" if slot == 0 else f".sav{slot}"


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def console_label(model, mac):
    """'DSi 3F21' / '3DS 3F21': the console and the end of its MAC address,
    so two of the same kind can be told apart in history/."""
    kind = "3DS" if model in (2, 3) else "DSi"
    tail = "".join(f"{b:02X}" for b in mac[-2:]) if mac else ""
    return f"{kind} {tail}".strip()


def to_console_time(t):
    """A PC time (Unix seconds) as the console counts: seconds since
    2000-01-01, local time."""
    try:
        return max(0, int((datetime.datetime.fromtimestamp(t) - EPOCH_2000).total_seconds()))
    except (OverflowError, OSError, ValueError):
        return 0


def safe_name(name, fallback):
    """A name that's a valid file name on Windows and macOS."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name or "").strip().strip(".")
    return name[:60].strip() or fallback


class SaveStore:
    def __init__(self, root, keep=DEFAULT_KEEP):
        self.root = root
        self.keep = max(1, int(keep or DEFAULT_KEEP))
        self.lock = threading.Lock()
        self.data = {"version": 1, "games": {}}
        self._load()

    # -- the manifest ------------------------------------------------------

    def _manifest(self):
        return os.path.join(self.root, MANIFEST)

    def _load(self):
        try:
            with open(self._manifest(), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("games"), dict):
                self.data = data
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            logging.warning(f"Save backups: can't read {self._manifest()} ({e}); starting a new one")

    def _save(self):
        os.makedirs(self.root, exist_ok=True)
        tmp = self._manifest() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1, sort_keys=True)
        os.replace(tmp, self._manifest())

    def _game(self, key, name=None, create=False):
        g = self.data["games"].get(key)
        if g is None and create:
            base = safe_name(name, key)
            g = {"name": base, "folder": f"{base} [{key}]", "slots": {}}
            self.data["games"][key] = g
        return g

    def _slot(self, key, slot, create=False, name=None):
        g = self._game(key, name, create)
        if g is None:
            return None
        s = g["slots"].get(str(slot))
        if s is None and create:
            s = {"latest": None, "history": []}
            g["slots"][str(slot)] = s
        return s

    def _folder(self, key):
        return os.path.join(self.root, self.data["games"][key]["folder"])

    # -- reading -----------------------------------------------------------

    def latest(self, key, slot):
        """The latest save's record ({'crc', 'size', 'time', 'source'}), or None."""
        s = self._slot(key, slot)
        return s["latest"] if s else None

    def history(self, key, slot):
        """[record]: the latest first (as version 0, if there is one), then
        history/, newest first. Each record also has 'version'."""
        s = self._slot(key, slot)
        if not s:
            return []
        out = []
        if s["latest"]:
            out.append(dict(s["latest"], version=0))
        for i, h in enumerate(reversed(s["history"]), start=1):
            out.append(dict(h, version=i))
        return out

    def slots(self, key):
        g = self._game(key)
        return sorted(int(n) for n, s in g["slots"].items() if s["latest"]) if g else []

    def read(self, key, slot, version=0):
        """(bytes, record) of version 0 (the latest) or 1.. (history, newest
        first). Raises SaveError if it's not there, or doesn't match its CRC."""
        with self.lock:
            versions = self.history(key, slot)
            rec = next((v for v in versions if v["version"] == version), None)
            if rec is None:
                raise SaveError(f"no version {version} of {key} slot {slot}")
            path = os.path.join(self._folder(key), rec["file"])
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_SAVE_SIZE + 1)
        except OSError as e:
            raise SaveError(f"can't read {path}: {e}") from e
        if len(data) != rec["size"] or crc32(data) != rec["crc"]:
            raise SaveError(f"{path} isn't the save it should be (changed outside DSiRPC?)")
        return data, rec

    def backed_up(self, key, slot, crc):
        """True if a save with this CRC is kept (the latest or in history)."""
        s = self._slot(key, slot)
        if not s:
            return False
        return any(r and r["crc"] == crc for r in [s["latest"]] + s["history"])

    # -- writing -----------------------------------------------------------

    def _write(self, key, rel, data):
        """Writes a file in the game's folder; returns its modified time."""
        path = os.path.join(self._folder(key), rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return int(os.stat(path).st_mtime)

    def _refresh_latest(self, key, slot):
        """Picks up a latest save changed or removed outside DSiRPC (say, an
        emulator's save copied over it): what's in the file is the PC's
        version now. Returns True if the record changed."""
        s = self._slot(key, slot)
        rec = s["latest"] if s else None
        if not rec:
            return False
        path = os.path.join(self._folder(key), rec["file"])
        try:
            st = os.stat(path)
        except OSError:
            s["latest"] = None
            return True
        if st.st_size == rec["size"] and int(st.st_mtime) == rec.get("mtime"):
            return False
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_SAVE_SIZE + 1)
        except OSError:
            return False
        if len(data) > MAX_SAVE_SIZE:
            return False
        crc = crc32(data)
        if crc != rec["crc"] or len(data) != rec["size"]:
            s["latest"] = {"file": rec["file"], "crc": crc, "size": len(data), "time": st.st_mtime,
                           "source": "PC", "reason": "changed on the PC"}
        s["latest"]["mtime"] = int(st.st_mtime)
        return True

    def _history_name(self, key, slot, when, source):
        g = self.data["games"][key]
        stamp = datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d %H-%M-%S")
        base = f"{g['name']} {stamp} ({safe_name(source, 'PC')})"
        name, n = base, 2
        taken = {h["file"] for h in g["slots"].get(str(slot), {}).get("history", [])}
        while os.path.join("history", name + slot_ext(slot)) in taken:
            name, n = f"{base} {n}", n + 1
        return os.path.join("history", name + slot_ext(slot))

    def _to_history(self, key, slot, rec):
        """Moves a record's file (the old latest) into history/."""
        s = self._slot(key, slot)
        rec = {k: v for k, v in rec.items() if k != "mtime"}
        if any(h["crc"] == rec["crc"] for h in s["history"]):
            self._remove(key, rec["file"])     # already kept there
            return
        rel = self._history_name(key, slot, rec["time"], rec["source"])
        src = os.path.join(self._folder(key), rec["file"])
        dst = os.path.join(self._folder(key), rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            os.replace(src, dst)
        except OSError as e:
            logging.warning(f"Save backups: can't move {src} into history ({e})")
            return
        s["history"].append(dict(rec, file=rel))

    def _add_history(self, key, slot, data, crc, source, reason, when):
        s = self._slot(key, slot)
        if any(r and r["crc"] == crc for r in [s["latest"]] + s["history"]):
            return False                        # already kept
        rel = self._history_name(key, slot, when, source)
        self._write(key, rel, data)
        s["history"].append({"file": rel, "crc": crc, "size": len(data), "time": when,
                             "source": source, "reason": reason})
        return True

    def _remove(self, key, rel):
        try:
            os.remove(os.path.join(self._folder(key), rel))
        except OSError:
            pass

    def _prune(self, key, slot):
        s = self._slot(key, slot)
        while len(s["history"]) > self.keep:
            old = s["history"].pop(0)
            self._remove(key, old["file"])

    def put(self, key, slot, name, data, crc, kind, source, when=None):
        """Keeps an uploaded save. kind PUT_SYNC makes it the latest (the old
        latest goes into history); PUT_BACKUP and PUT_SAFETY (a console's save
        about to be replaced) only add it to history. Raises SaveError if the
        data doesn't match its CRC. Returns True if anything was stored."""
        if not 0 <= slot <= MAX_SLOT or len(data) > MAX_SAVE_SIZE:
            raise SaveError("bad slot or size")
        if crc32(data) != crc:
            raise SaveError("the save arrived damaged (CRC mismatch)")
        when = when if when is not None else datetime.datetime.now().timestamp()
        with self.lock:
            s = self._slot(key, slot, create=True, name=name)
            if kind == PUT_SYNC:
                old = s["latest"]
                if old and old["crc"] == crc:
                    return False
                rel = self.data["games"][key]["name"] + slot_ext(slot)
                if old:
                    self._to_history(key, slot, old)
                mtime = self._write(key, rel, data)
                s["latest"] = {"file": rel, "crc": crc, "size": len(data), "time": when,
                               "source": source, "reason": "sync", "mtime": mtime}
                stored = True
            else:
                reason = "backup" if kind == PUT_BACKUP else "replaced"
                stored = self._add_history(key, slot, data, crc, source, reason, when)
            self._prune(key, slot)
            self._save()
            return stored

    def restore(self, key, slot, version, source):
        """Makes history version `version` the latest (sync mode's restore:
        the other consoles are offered it too). Returns (bytes, record)."""
        data, rec = self.read(key, slot, version)
        if version == 0:
            return data, rec
        name = self.data["games"][key]["name"]
        self.put(key, slot, name, data, rec["crc"], PUT_SYNC, f"{source}, restored")
        return data, self.latest(key, slot)

    # -- the plan ----------------------------------------------------------

    def plan(self, entries, backup_only):
        """What to do with each save the console listed. entries: dicts with
        code, hcrc, slot, present, crc, base, excluded, name (base: the save's
        CRC at its last sync, 0 if never). Adds a 'download (new)' item for
        every save kept here for a game the console has (by its listed
        ROMs) but not in that slot. Returns [item dict]: the entry's key,
        slot and name, and action, plus the latest's record (or None)."""
        items, seen, games = [], set(), {}
        with self.lock:
            changed = False
            for key, g in self.data["games"].items():
                for n in g["slots"]:
                    changed |= self._refresh_latest(key, int(n))
            if changed:
                self._save()
            for e in entries:
                key = game_key(e["code"], e["hcrc"])
                games.setdefault(key, e["name"])
                seen.add((key, e["slot"]))
                latest = self.latest(key, e["slot"])
                action = self._decide(key, e, latest, backup_only)
                if action is None:
                    continue
                items.append({"code": e["code"], "hcrc": e["hcrc"], "slot": e["slot"], "name": e["name"],
                              "action": action, "latest": latest,
                              "versions": len(self.history(key, e["slot"]))})
            if not backup_only:
                for key, name in games.items():
                    for slot in self.slots(key):
                        if (key, slot) not in seen:
                            code, hcrc = key.split("-")
                            items.append({"code": code, "hcrc": int(hcrc, 16), "slot": slot, "name": name,
                                          "action": DOWNLOAD_NEW, "latest": self.latest(key, slot),
                                          "versions": len(self.history(key, slot))})
        return items

    def _decide(self, key, e, latest, backup_only):
        if e["excluded"]:
            return EXCLUDED if e["present"] or latest else None
        if backup_only:
            if not e["present"]:
                return None
            if e["crc"] != e["base"] or not self.backed_up(key, e["slot"], e["crc"]):
                return BACKUP
            return IN_SYNC
        if not e["present"]:
            return DOWNLOAD_NEW if latest else None
        if latest is None:
            return UPLOAD
        console, pc, base = e["crc"], latest["crc"], e["base"]
        if console == pc:
            return IN_SYNC
        if base and base == pc:
            return UPLOAD
        if base and base == console:
            return DOWNLOAD
        return CONFLICT
