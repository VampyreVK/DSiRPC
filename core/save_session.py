"""
save_session.py - the launcher's save sync, DSiRPC's side of the exchange
(core/saves.py keeps the saves, launcher/source/savesync.c is the console's
side). It shares the offline sync's TCP port (core/console_sync.py hands
over any connection that starts with "DRSV").

Each TCP connection is one request and its answer, so nothing waits while
someone browses the list on the console. Little-endian throughout:

    every request:  "DRSV" | version u16 | flags u16 (bit 0: backup only) |
                    MAC[6] | console model u8 | op u8

    op 1, the plan: n u16, then n x (code[4] | header CRC u16 | slot u8 |
                    state u8 (bit 0: there's a save, bit 1: excluded) |
                    size u32 | CRC u32 | CRC at the last sync u32 |
                    name length u8 | name)
        answer:     "DRSP" | status u16 | n u16, then n x (code[4] |
                    header CRC u16 | slot u8 | action u8 | the PC's size u32 |
                    CRC u32 | time u32 | versions u8 | source length u8 |
                    source)
    op 2, upload:   code[4] | header CRC u16 | slot u8 | kind u8 (1 sync,
                    2 backup, 3 a save about to be replaced) | size u32 |
                    CRC u32 | name length u8 | name | the save
        answer:     "DRSK" | status u16
    op 3, download: code[4] | header CRC u16 | slot u8 | version u8 (0 the
                    latest, 1.. history, newest first) | flags u8 (bit 0:
                    make it the latest, a restore in sync mode)
        answer:     "DRSD" | status u16 | size u32 | CRC u32 | the save
    op 4, history:  code[4] | header CRC u16 | slot u8
        answer:     "DRSL" | status u16 | n u16, then n x (version u8 |
                    time u32 | size u32 | CRC u32 | source length u8 | source)
    op 5, done:     uploaded u16 | downloaded u16 | backed up u16 | failed u16
        answer:     "DRSK" | status u16

Times are seconds since 2000-01-01, local time, as the console counts.
Status: 0 OK, 1 not found, 2 damaged (CRC mismatch), 3 can't store,
4 bad request, 5 save backups are off.
"""

import logging
import struct

from . import saves

VERSION = 1
MAGIC = b"DRSV"
HEADER = struct.Struct("<4sHH6sBB")
PLAN_ENTRY = struct.Struct("<4sHBBIIIB")
PLAN_ITEM = struct.Struct("<4sHBBIIIBB")
PUT = struct.Struct("<4sHBBIIB")
GET = struct.Struct("<4sHBBB")
HIST = struct.Struct("<4sHB")
HIST_ITEM = struct.Struct("<BIIIB")
DONE = struct.Struct("<HHHH")

OP_PLAN, OP_PUT, OP_GET, OP_HIST, OP_DONE = 1, 2, 3, 4, 5
OK, NOT_FOUND, DAMAGED, CANT_STORE, BAD_REQUEST, OFF = range(6)
FLAG_BACKUP_ONLY = 1
STATE_PRESENT, STATE_EXCLUDED = 1, 2
GET_MAKE_LATEST = 1
MAX_ENTRIES = 2048


class RequestError(Exception):
    pass


def _code(raw):
    if len(raw) != 4 or not all(48 <= b <= 57 or 65 <= b <= 90 for b in raw):
        raise RequestError("bad game code")
    return raw.decode()


def _text(read, n, limit=64):
    if n > limit:
        raise RequestError("name too long")
    return read(n).decode("utf-8", "replace") if n else ""


def _short(text, limit=32):
    return text.encode("utf-8")[:limit]


def handle(magic, read, send, store, on_event=None):
    """Answers one request: magic is the 4 bytes already read, read(n) and
    send(bytes) talk to the console, store is the SaveStore (None if save
    backups are off). on_event(dict), if given, hears what happened."""
    rest = read(HEADER.size - 4)
    _, version, flags, mac, model, op = HEADER.unpack(magic + rest)
    who = saves.console_label(model, mac)
    backup_only = bool(flags & FLAG_BACKUP_ONLY)
    answers = {OP_PLAN: b"DRSP", OP_PUT: b"DRSK", OP_GET: b"DRSD", OP_HIST: b"DRSL", OP_DONE: b"DRSK"}
    tail = {OP_PLAN: b"\0\0", OP_GET: b"\0" * 8, OP_HIST: b"\0\0"}

    def refuse(status):
        send(answers.get(op, b"DRSK") + struct.pack("<H", status) + tail.get(op, b""))

    if version != VERSION or op not in answers:
        refuse(BAD_REQUEST)
        return
    if store is None:
        refuse(OFF)
        return
    try:
        if op == OP_PLAN:
            _plan(read, send, store, backup_only)
        elif op == OP_PUT:
            _put(read, send, store, who, on_event)
        elif op == OP_GET:
            _get(read, send, store, who, on_event)
        elif op == OP_HIST:
            _history(read, send, store)
        else:
            uploaded, downloaded, backed_up, failed = DONE.unpack(read(DONE.size))
            send(b"DRSK" + struct.pack("<H", OK))
            if on_event:
                on_event({"type": "saves_synced", "console": who, "uploaded": uploaded,
                          "downloaded": downloaded, "backed_up": backed_up, "failed": failed})
    except RequestError as e:
        logging.warning(f"Save sync from the {who}: {e}")
        refuse(BAD_REQUEST)


def _plan(read, send, store, backup_only):
    (n,) = struct.unpack("<H", read(2))
    if n > MAX_ENTRIES:
        raise RequestError("too many saves")
    entries = []
    for _ in range(n):
        code, hcrc, slot, state, size, crc, base, name_len = PLAN_ENTRY.unpack(read(PLAN_ENTRY.size))
        name = _text(read, name_len)
        if slot > saves.MAX_SLOT:
            raise RequestError("bad save slot")
        entries.append({"code": _code(code), "hcrc": hcrc, "slot": slot, "present": bool(state & STATE_PRESENT),
                        "excluded": bool(state & STATE_EXCLUDED), "size": size, "crc": crc, "base": base,
                        "name": name})
    items = store.plan(entries, backup_only)
    out = [b"DRSP" + struct.pack("<HH", OK, len(items))]
    for i in items:
        rec = i["latest"] or {}
        source = _short(rec.get("source", ""))
        out.append(PLAN_ITEM.pack(i["code"].encode(), i["hcrc"], i["slot"], i["action"], rec.get("size", 0),
                                  rec.get("crc", 0), saves.to_console_time(rec["time"]) if rec else 0,
                                  min(255, i["versions"]), len(source)) + source)
    send(b"".join(out))


def _put(read, send, store, who, on_event):
    code, hcrc, slot, kind, size, crc, name_len = PUT.unpack(read(PUT.size))
    name = _text(read, name_len)
    if size > saves.MAX_SAVE_SIZE or slot > saves.MAX_SLOT or kind not in (saves.PUT_SYNC, saves.PUT_BACKUP,
                                                                         saves.PUT_SAFETY):
        raise RequestError("bad upload")
    code = _code(code)
    data = read(size)
    key = saves.game_key(code, hcrc)
    try:
        stored = store.put(key, slot, name, data, crc, kind, who)
    except saves.SaveError as e:
        logging.warning(f"Save sync from the {who}: {name}: {e}")
        send(b"DRSK" + struct.pack("<H", DAMAGED))
        return
    except OSError as e:
        logging.warning(f"Save sync from the {who}: can't store {name}: {e}")
        send(b"DRSK" + struct.pack("<H", CANT_STORE))
        return
    send(b"DRSK" + struct.pack("<H", OK))
    what = {saves.PUT_SYNC: "synced", saves.PUT_BACKUP: "backed up", saves.PUT_SAFETY: "kept before replacing"}[kind]
    if stored:
        logging.info(f"Save sync: {name}{saves.slot_ext(slot)} {what} from the {who} ({size} bytes)")
    if on_event:
        on_event({"type": "save_uploaded", "console": who, "name": name, "slot": slot, "kind": kind})


def _get(read, send, store, who, on_event):
    code, hcrc, slot, version, flags = GET.unpack(read(GET.size))
    key = saves.game_key(_code(code), hcrc)
    try:
        if flags & GET_MAKE_LATEST:
            data, rec = store.restore(key, slot, version, who)
        else:
            data, rec = store.read(key, slot, version)
    except saves.SaveError as e:
        logging.warning(f"Save sync to the {who}: {e}")
        send(b"DRSD" + struct.pack("<HII", NOT_FOUND, 0, 0))
        return
    send(b"DRSD" + struct.pack("<HII", OK, len(data), rec["crc"]) + data)
    logging.info(f"Save sync: {key} slot {slot} " + (f"version {version} " if version else "") +
                 f"sent to the {who} ({len(data)} bytes)")
    if on_event:
        on_event({"type": "save_downloaded", "console": who, "key": key, "slot": slot, "version": version})


def _history(read, send, store):
    code, hcrc, slot = HIST.unpack(read(HIST.size))
    versions = store.history(saves.game_key(_code(code), hcrc), slot)[:255]
    out = [b"DRSL" + struct.pack("<HH", OK, len(versions))]
    for v in versions:
        source = _short(v["source"])
        out.append(HIST_ITEM.pack(v["version"], saves.to_console_time(v["time"]), v["size"], v["crc"],
                                  len(source)) + source)
    send(b"".join(out))


# -- a console, for tests ------------------------------------------------------

def request(op, body, mac=b"\0\x09\xbf\x12\x3f\x21", model=0, backup_only=False):
    return HEADER.pack(MAGIC, VERSION, FLAG_BACKUP_ONLY if backup_only else 0, mac, model, op) + body


def plan_body(entries):
    out = [struct.pack("<H", len(entries))]
    for e in entries:
        name = e["name"].encode()
        state = (STATE_PRESENT if e["present"] else 0) | (STATE_EXCLUDED if e.get("excluded") else 0)
        out.append(PLAN_ENTRY.pack(e["code"].encode(), e["hcrc"], e["slot"], state, e.get("size", 0), e["crc"],
                                   e["base"], len(name)) + name)
    return b"".join(out)
