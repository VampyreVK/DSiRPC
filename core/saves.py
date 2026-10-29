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
        Pokemon Black.sav               the live save (slot 0; .sav1 to .sav9
                                        for TWiLight Menu++'s other slots)
        backups/
            DSi 3F21/                   every save that console sent
                Pokemon Black 2026-10-20 14-02-11.sav
            3DS 0002/
                Pokemon Black 2026-10-21 09-15-40.sav
            External/                   saves that came from somewhere else

The live save is the one consoles in sync mode share: the newest one any of
them sent, a version restored, or a save put there by hand. Every save a
console sends is also kept as a backup of that console's, so the live save
is the newest backup over again, on purpose: the live copy is the one that's
shared, the backups are each console's history. Each console's last `keep`
backups are kept (dsirpc.cfg's versions, 10 by default), and nothing is ever
replaced without being kept as a backup first.

A save put in the game's folder by hand is picked up at the next sync.
Copied over the live save, it's the live save from then on: as the backup
it is, if it's one of them, or else as an External backup (the live copy
stays where it was put). Put anywhere else in the folder, it's listed as an
External backup the consoles can restore. A save put there by hand is never
pruned.

saves.json in the backups folder lists it all: each save's CRC32 (zlib's),
size, time and where it came from, and what each console last had (the save
it sent or took). A save's time, and its file's date, is when the console
last wrote it (as its clock says), not when it was copied here.

Whether a save changed is decided three ways, the way RetroAchievements'
cloud sync and Syncthing do, from what the console had at its last sync (the
base: the console remembers it, in saves.idx, and so does DSiRPC):

    the console's == the live save      in sync
    the base == the live save           only the console's changed: up
    the base == the console's           newer from another console: down
    otherwise                           both changed: the console asks

No clocks are compared: a DSi's clock is whatever its owner set.
"""

import datetime
import json
import logging
import os
import re
import shutil
import threading
import time
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
BACKUPS = "backups"
EXTERNAL = "External"           # where a save from outside the consoles came from
EPOCH_2000 = datetime.datetime(2000, 1, 1)
SAVE_FILE = re.compile(r"\.sav([1-9])?$", re.I)


class SaveError(Exception):
    pass


def game_key(code, header_crc):
    return f"{code}-{header_crc & 0xFFFF:04X}"


def slot_ext(slot):
    return ".sav" if slot == 0 else f".sav{slot}"


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


REPLACE_TRIES = 6


def _replace(src, dst):
    """os.replace, tried again for a moment while another program has the
    file open (Windows won't replace it then: a cloud drive's client or an
    antivirus, say), about 1.5 s in all."""
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05 * 2 ** attempt)


def console_label(model, mac):
    """'DSi 3F21' / '3DS 3F21': the console and the end of its MAC address,
    so two of the same kind can be told apart."""
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


def from_console_time(t):
    """The other way round: a console's time (seconds since 2000-01-01, its
    local time) as a PC time, or None if it didn't say (0) or its clock
    can't be right (before 2005, or days ahead of this PC's)."""
    if not t:
        return None
    try:
        when = (EPOCH_2000 + datetime.timedelta(seconds=t)).timestamp()
    except (OverflowError, OSError, ValueError):
        return None
    if when < datetime.datetime(2005, 1, 1).timestamp() or when > time.time() + 2 * 86400:
        return None
    return when


def safe_name(name, fallback):
    """A name that's a valid file name on Windows and macOS."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name or "").strip().strip(".")
    return name[:60].strip() or fallback


def _read(path):
    with open(path, "rb") as f:
        data = f.read(MAX_SAVE_SIZE + 1)
    if len(data) > MAX_SAVE_SIZE:
        raise SaveError(f"{path} is too big to be a save")
    return data


class SaveStore:
    def __init__(self, root, keep=DEFAULT_KEEP):
        self.root = root
        self.keep = max(1, int(keep or DEFAULT_KEEP))
        self.lock = threading.Lock()
        self.data = {"version": 2, "games": {}}
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
                if data.get("version", 1) < 2:
                    self._upgrade()
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            logging.warning(f"Save backups: can't read {self._manifest()} ({e}); starting a new one")

    def _upgrade(self):
        """From the first layout (the latest save and one history/ folder):
        history/ becomes each console's backups, and the latest save gets a
        backup of its own if it had none."""
        for key, g in self.data["games"].items():
            for n, s in g["slots"].items():
                live = s.pop("latest", None)
                backups = []
                for rec in s.pop("history", []):
                    rec = dict(rec)
                    dest = self._backup_name(key, int(n), rec["time"], rec["source"], backups)
                    try:
                        self._move(key, rec["file"], dest)
                        rec["file"] = dest
                    except OSError as e:
                        logging.warning(f"Save backups: can't move {rec['file']} ({e}); left where it is")
                    backups.append(rec)
                s.update(live=live, backups=backups, consoles={})
                if live and not any(b["crc"] == live["crc"] for b in backups):
                    dest = self._backup_name(key, int(n), live["time"], live["source"], backups)
                    try:
                        os.makedirs(os.path.dirname(os.path.join(self._folder(key), dest)), exist_ok=True)
                        shutil.copy2(os.path.join(self._folder(key), live["file"]), os.path.join(self._folder(key), dest))
                        backups.append(dict({k: v for k, v in live.items() if k != "mtime"}, file=dest))
                    except OSError as e:
                        logging.warning(f"Save backups: can't keep a backup of {live['file']} ({e})")
            try:
                os.rmdir(os.path.join(self._folder(key), "history"))
            except OSError:
                pass
        self.data["version"] = 2
        try:
            self._save()
        except OSError as e:
            logging.warning(f"Save backups: can't write {self._manifest()} ({e})")

    def _save(self):
        os.makedirs(self.root, exist_ok=True)
        tmp = self._manifest() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1, sort_keys=True)
        _replace(tmp, self._manifest())

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
            s = {"live": None, "backups": [], "consoles": {}}
            g["slots"][str(slot)] = s
        return s

    def _folder(self, key):
        return os.path.join(self.root, self.data["games"][key]["folder"])

    # -- reading -----------------------------------------------------------

    def latest(self, key, slot):
        """The live save's record ({'crc', 'size', 'time', 'source', ...}), or None."""
        s = self._slot(key, slot)
        return s["live"] if s else None

    def history(self, key, slot):
        """[record]: the live save first (version 0, if there is one), then
        the backups, newest first, each save once (the live save's own
        backup, or another console's copy of the same save, isn't listed
        twice; versions from 1). Each record also has 'version'."""
        s = self._slot(key, slot)
        if not s:
            return []
        out, seen = [], set()
        if s["live"]:
            out.append(dict(s["live"], version=0))
            seen.add(s["live"]["crc"])
        n = 1
        newest_first = sorted(enumerate(s["backups"]), key=lambda p: (p[1]["time"], p[0]), reverse=True)
        for _, b in newest_first:
            if b["crc"] not in seen:
                seen.add(b["crc"])
                out.append(dict(b, version=n))
                n += 1
        return out

    def backups(self, key, slot, console=None):
        """The backups kept (oldest first), only `console`'s if given."""
        s = self._slot(key, slot)
        return [b for b in (s["backups"] if s else []) if console is None or b["source"] == console]

    def slots(self, key):
        g = self._game(key)
        return sorted(int(n) for n, s in g["slots"].items() if s["live"]) if g else []

    def read(self, key, slot, version=0):
        """(bytes, record) of version 0 (the live save) or 1.. (the backups,
        newest first). Raises SaveError if it's not there, or doesn't match
        its CRC."""
        with self.lock:
            rec = next((v for v in self.history(key, slot) if v["version"] == version), None)
            if rec is None:
                raise SaveError(f"no version {version} of {key} slot {slot}")
            path = os.path.join(self._folder(key), rec["file"])
        try:
            data = _read(path)
        except OSError as e:
            raise SaveError(f"can't read {path}: {e}") from e
        if len(data) != rec["size"] or crc32(data) != rec["crc"]:
            raise SaveError(f"{path} isn't the save it should be (changed outside DSiRPC?)")
        return data, rec

    def backed_up(self, key, slot, crc, console=None):
        """True if a save with this CRC is kept: the live save or a backup,
        or with `console`, one of that console's backups."""
        s = self._slot(key, slot)
        if not s:
            return False
        if console is None and s["live"] and s["live"]["crc"] == crc:
            return True
        return any(b["crc"] == crc for b in self.backups(key, slot, console))

    def console_had(self, key, slot, console):
        """What DSiRPC last knew `console` to have in this slot ({'crc',
        'from', 'time'}: the save it sent or took, and whose it was), or None."""
        s = self._slot(key, slot)
        return s["consoles"].get(console) if s else None

    # -- writing -----------------------------------------------------------

    def _write(self, key, rel, data, when=None):
        """Writes a file in the game's folder, dated `when` (a PC time) if
        given; returns its modified time."""
        path = os.path.join(self._folder(key), rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        _replace(tmp, path)
        if when is not None:
            try:
                os.utime(path, (when, when))
            except (OSError, OverflowError, ValueError) as e:
                logging.info(f"Save backups: can't date {path} ({e})")
        return int(os.stat(path).st_mtime)

    def _move(self, key, rel, dest):
        folder = self._folder(key)
        os.makedirs(os.path.dirname(os.path.join(folder, dest)), exist_ok=True)
        _replace(os.path.join(folder, rel), os.path.join(folder, dest))

    def _remove(self, key, rel):
        try:
            os.remove(os.path.join(self._folder(key), rel))
        except OSError:
            pass

    def _backup_name(self, key, slot, when, source, more=()):
        """backups/<source>/<game> <time>.sav, not taken yet."""
        g = self.data["games"][key]
        stamp = datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d %H-%M-%S")
        base = os.path.join(BACKUPS, safe_name(source, "PC"), f"{g['name']} {stamp}")
        taken = {b["file"] for s in g["slots"].values() for b in s.get("backups", [])} | {b["file"] for b in more}
        name, n = base, 2
        while name + slot_ext(slot) in taken or os.path.exists(os.path.join(self._folder(key), name + slot_ext(slot))):
            name, n = f"{base} {n}", n + 1
        return name + slot_ext(slot)

    def _add_backup(self, key, slot, data, crc, source, reason, when):
        """Keeps a save as one of `source`'s backups, unless its newest backup
        is that save already. Returns True if it was added."""
        s = self._slot(key, slot)
        mine = self.backups(key, slot, source)
        if mine and mine[-1]["crc"] == crc:
            return False
        rel = self._backup_name(key, slot, when, source)
        self._write(key, rel, data, when)
        s["backups"].append({"file": rel, "crc": crc, "size": len(data), "time": when, "source": source,
                             "reason": reason})
        return True

    def _prune(self, key, slot, source):
        """Each console's last `keep` backups (not External ones, nor saves
        put in the folder by hand)."""
        if source == EXTERNAL:
            return
        s = self._slot(key, slot)
        mine = [b for b in s["backups"] if b["source"] == source and not b.get("by_hand")]
        while len(mine) > self.keep:
            old = mine.pop(0)
            s["backups"].remove(old)
            self._remove(key, old["file"])

    def _keep_live(self, key, slot):
        """Before the live save is replaced: kept as a backup if none is it
        (one from the first layout, say)."""
        s = self._slot(key, slot)
        live = s["live"]
        if not live or any(b["crc"] == live["crc"] for b in s["backups"]):
            return
        try:
            data = _read(os.path.join(self._folder(key), live["file"]))
        except (OSError, SaveError):
            return
        crc = crc32(data)
        source = live["source"] if crc == live["crc"] else EXTERNAL
        self._add_backup(key, slot, data, crc, source, "kept", live["time"])

    def _set_live(self, key, slot, data, crc, source, reason, when, **more):
        s = self._slot(key, slot)
        rel = self.data["games"][key]["name"] + slot_ext(slot)
        mtime = self._write(key, rel, data, when)
        s["live"] = dict({"file": rel, "crc": crc, "size": len(data), "time": when, "source": source,
                          "reason": reason, "mtime": mtime}, **more)

    def _note_console(self, s, console, crc, source):
        """What `console` has now: the save it sent or took. Returns True if
        that's news."""
        if not console or not crc:
            return False
        had = s["consoles"].get(console)
        if had and had["crc"] == crc:
            return False
        s["consoles"][console] = {"crc": crc, "from": source or console, "time": time.time()}
        return True

    def _whose(self, s, crc):
        """The newest record of a save with this CRC (the live save or a
        backup), or None."""
        recs = [r for r in [s["live"]] + s["backups"] if r and r["crc"] == crc]
        return max(recs, key=lambda r: r["time"]) if recs else None

    def put(self, key, slot, name, data, crc, kind, source, when=None):
        """Keeps an uploaded save as one of `source`'s backups; kind PUT_SYNC
        also makes it the live save (PUT_BACKUP: a back-up-only console's,
        PUT_SAFETY: a console's save about to be replaced). when: when the
        console last wrote the save (a PC time; now if None), its time here
        and its files' date. Raises SaveError if the data doesn't match its
        CRC. Returns True if anything was stored."""
        if not 0 <= slot <= MAX_SLOT or len(data) > MAX_SAVE_SIZE:
            raise SaveError("bad slot or size")
        if crc32(data) != crc:
            raise SaveError(f"the save arrived damaged ({len(data)} bytes with CRC {crc32(data):08X}, "
                            f"not {crc:08X})")
        when = when if when is not None else datetime.datetime.now().timestamp()
        with self.lock:
            s = self._slot(key, slot, create=True, name=name)
            stored = False
            if kind == PUT_SYNC:
                if not (s["live"] and s["live"]["crc"] == crc):
                    self._keep_live(key, slot)
                    self._set_live(key, slot, data, crc, source, "sync", when)
                    stored = True
                stored |= self._add_backup(key, slot, data, crc, source, "sync", when)
            else:
                reason = "backup" if kind == PUT_BACKUP else "replaced"
                stored = self._add_backup(key, slot, data, crc, source, reason, when)
            if kind != PUT_SAFETY:
                self._note_console(s, source, crc, source)
            self._prune(key, slot, source)
            self._save()
            return stored

    def restore(self, key, slot, version, source):
        """Makes version `version` the live save (sync mode's restore: the
        other consoles are offered it too), still dated and named as whose
        it was. Returns (bytes, record)."""
        data, rec = self.read(key, slot, version)
        if version == 0:
            return data, rec
        with self.lock:
            self._keep_live(key, slot)
            self._set_live(key, slot, data, rec["crc"], rec["source"], "restored", rec["time"], restored_by=source)
            self._save()
        return data, self.latest(key, slot)

    # -- saves put in the folder by hand -----------------------------------

    def _refresh_live(self, key, slot):
        """A live save changed or removed outside DSiRPC: one copied over it
        is the live save now, as the backup it is (if it's one), or kept as
        an External backup too (if it's none). Returns True if anything
        changed."""
        s = self._slot(key, slot)
        rec = s["live"] if s else None
        if not rec:
            return False
        path = os.path.join(self._folder(key), rec["file"])
        try:
            st = os.stat(path)
        except OSError:
            s["live"] = None                    # removed: the consoles send theirs again
            return True
        if st.st_size == rec["size"] and int(st.st_mtime) == rec.get("mtime"):
            return False
        try:
            data = _read(path)
        except (OSError, SaveError):
            return False
        crc = crc32(data)
        if crc != rec["crc"] or len(data) != rec["size"]:
            self._live_by_hand(key, slot, rec["file"], data, crc, st.st_mtime)
        s["live"]["mtime"] = int(st.st_mtime)
        return True

    def _live_by_hand(self, key, slot, rel, data, crc, mtime):
        s = self._slot(key, slot)
        known = self._whose(s, crc)
        if known:
            source, when, reason = known["source"], known["time"], "copied in"
        else:
            source, when, reason = EXTERNAL, mtime, "external"
            self._add_backup(key, slot, data, crc, EXTERNAL, "external", when)
        s["live"] = {"file": rel, "crc": crc, "size": len(data), "time": when, "source": source,
                     "reason": reason, "mtime": int(mtime)}
        logging.info(f"Save backups: {os.path.join(self.data['games'][key]['folder'], rel)} was replaced by hand"
                     + (f" with the {source}'s save" if known else " (an External save)"))

    def _pick_up_by_hand(self, key):
        """Save files put in the game's folder by hand: in the live save's
        place (with no live save yet), the live save; anywhere else, a backup
        where it is (an External one, or the backup it's a copy of). Returns
        True if any was."""
        g = self.data["games"][key]
        folder = self._folder(key)
        known = set()
        for s in g["slots"].values():
            known.update(os.path.normcase(r["file"]) for r in [s["live"]] + s["backups"] if r)
        found = False
        for dirpath, _, filenames in os.walk(folder):
            for fn in sorted(filenames):
                m = SAVE_FILE.search(fn)
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, folder)
                if not m or os.path.normcase(rel) in known:
                    continue
                slot = int(m.group(1) or 0)
                try:
                    data, mtime = _read(path), os.stat(path).st_mtime
                except (OSError, SaveError):
                    continue
                crc = crc32(data)
                s = self._slot(key, slot, create=True)
                if rel == g["name"] + slot_ext(slot) and not s["live"]:
                    self._live_by_hand(key, slot, rel, data, crc, mtime)
                else:
                    known_rec = self._whose(s, crc)
                    s["backups"].append({"file": rel, "crc": crc, "size": len(data),
                                         "time": known_rec["time"] if known_rec else mtime,
                                         "source": known_rec["source"] if known_rec else EXTERNAL,
                                         "reason": "copied in" if known_rec else "external", "by_hand": True})
                    logging.info(f"Save backups: picked up {os.path.join(g['folder'], rel)}"
                                 + ("" if known_rec else " (an External save)"))
                known.add(os.path.normcase(rel))
                found = True
        return found

    # -- the plan ----------------------------------------------------------

    def plan(self, entries, backup_only, console=None):
        """What to do with each save `console` listed. entries: dicts with
        code, hcrc, slot, present, crc, base, excluded, name (base: what the
        console had at its last sync, by its own count, 0 if it can't tell:
        then what DSiRPC remembers it had counts). Adds a 'download (new)'
        item for every live save here for a game the console has (by its
        listed ROMs) but not in that slot. Returns [item dict]: the entry's
        key, slot and name, and action, plus the live save's record (or
        None)."""
        items, seen, games = [], set(), {}
        with self.lock:
            changed = False
            for key, g in self.data["games"].items():
                changed |= self._pick_up_by_hand(key)
                for n in g["slots"]:
                    changed |= self._refresh_live(key, int(n))
            for e in entries:
                key = game_key(e["code"], e["hcrc"])
                games.setdefault(key, e["name"])
                seen.add((key, e["slot"]))
                s = self._slot(key, e["slot"])
                live = s["live"] if s else None
                had = (s["consoles"].get(console) if s and console else None) or {}
                # What the console had at its last sync only counts if that
                # sync was with this DSiRPC: a save it never saw came from
                # another one (synced with the PC, then with the Mac, the
                # console would otherwise take the Mac's older save as the
                # newer one). Then what this DSiRPC remembers it had decides.
                known = self._knows(s, e["base"])
                base = (e["base"] if known else 0) or had.get("crc", 0)
                action = self._decide(key, e, live, base, backup_only, console)
                if s and e["present"]:
                    # What the console has, as far as anyone can tell
                    if live and e["crc"] == live["crc"]:
                        changed |= self._note_console(s, console, live["crc"], live["source"])
                    elif known:
                        whose = self._whose(s, e["base"])
                        changed |= self._note_console(s, console, e["base"], whose["source"] if whose else None)
                if action is None:
                    continue
                items.append({"code": e["code"], "hcrc": e["hcrc"], "slot": e["slot"], "name": e["name"],
                              "action": action, "latest": live,
                              "versions": len(self.history(key, e["slot"]))})
            if not backup_only:
                for key, name in games.items():
                    for slot in self.slots(key):
                        if (key, slot) not in seen:
                            code, hcrc = key.split("-")
                            items.append({"code": code, "hcrc": int(hcrc, 16), "slot": slot, "name": name,
                                          "action": DOWNLOAD_NEW, "latest": self.latest(key, slot),
                                          "versions": len(self.history(key, slot))})
            if changed:
                self._save()
        return items

    @staticmethod
    def _knows(s, crc):
        """Whether this DSiRPC has seen a save with this CRC in the slot: the
        live save, a backup, or what a console had."""
        if not s or not crc:
            return False
        if s["live"] and s["live"]["crc"] == crc:
            return True
        return any(b["crc"] == crc for b in s["backups"]) or \
            any(c.get("crc") == crc for c in s["consoles"].values())

    def _decide(self, key, e, live, base, backup_only, console):
        if e["excluded"]:
            return EXCLUDED if e["present"] or live else None
        if backup_only:
            if not e["present"]:
                return None
            if e["crc"] != base or not self.backed_up(key, e["slot"], e["crc"], console):
                return BACKUP
            return IN_SYNC
        if not e["present"]:
            return DOWNLOAD_NEW if live else None
        if live is None:
            return UPLOAD
        mine, pc = e["crc"], live["crc"]
        if mine == pc:
            return IN_SYNC
        if base and base == pc:
            return UPLOAD                       # nothing newer from the others since: only this one changed
        if base and base == mine:
            return DOWNLOAD                     # unchanged here since; newer from another console
        return CONFLICT
