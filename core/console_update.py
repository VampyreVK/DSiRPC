"""
console_update.py - updating the console's DSiRPC files from the PC, so a new
build doesn't need the SD card taken out: the launcher (dsirpc-launcher.nds)
and our nds-bootstrap build (nds-bootstrap-dsirpc.nds), as they came with
this DSiRPC (launcher/source/update.c is the console's side). The launcher
asks as it starts, once it has found DSiRPC; when one of its files differs
from DSiRPC's, it offers the update (A) and takes the file from here.

DSiRPC's copies, the first found of each (ConsoleFiles):

    SD card/DSiRPC/<name>         the Windows download, and inside the macOS
                                  app (packaging/macos/DSiRPC.spec)
    launcher/dsirpc-launcher.nds, nds-bootstrap/retail/bin/nds-bootstrap-nightly.nds
                                  a source checkout's own builds

It shares the offline sync's TCP port (core/console_sync.py hands over any
connection that starts with "DRUP"). This exchange never changes, so every
launcher that can update can update from any later DSiRPC, whatever else
changed between them; something new gets a new op. Little-endian:

    every request:  "DRUP" | version u16 (1) | MAC[6] | console model u8 | op u8 |
                    file u8 (op 2, else 0) | 5 bytes 0
                    (20 bytes, as long as the offline sync's request, so a
                    DSiRPC from before updates turns it down at once instead
                    of waiting for more)
    op 1, the list
        answer:     "DRUA" | status u16 | n u8, then n x (file u8 | size u32 |
                    CRC32 u32) | label length u8 | label (this DSiRPC's
                    version, for the screen)
    op 2, a file
        answer:     "DRUF" | status u16 | size u32 | CRC32 u32 | the file

Files: 1 the launcher, 2 nds-bootstrap (the launcher skips numbers it doesn't
know). Status: 0 OK, 1 DSiRPC has no such file, 4 bad request, 5 console
updates are off (the tray menu's "Console updates").
"""

import logging
import os
import plistlib
import struct
import subprocess
import sys
import zlib

from . import saves
from .paths import ROOT

MAGIC = b"DRUP"
VERSION = 1
HEADER = struct.Struct("<4sH6sBBB5x")
FILE_ENTRY = struct.Struct("<BII")

OP_LIST, OP_GET = 1, 2
OK, NOT_FOUND, BAD_REQUEST, OFF = 0, 1, 4, 5
LAUNCHER, BOOTSTRAP = 1, 2
NAMES = {LAUNCHER: "dsirpc-launcher.nds", BOOTSTRAP: "nds-bootstrap-dsirpc.nds"}
WHAT = {LAUNCHER: "the launcher", BOOTSTRAP: "nds-bootstrap"}
SD_FOLDER = os.path.join("SD card", "DSiRPC")
BUILDS = {LAUNCHER: os.path.join("launcher", "dsirpc-launcher.nds"),
          BOOTSTRAP: os.path.join("nds-bootstrap", "retail", "bin", "nds-bootstrap-nightly.nds")}
MAX_FILE = 8 * 1024 * 1024     # the launcher refuses bigger ones too
CHUNK = 64 * 1024              # sent a piece at a time: the socket's timeout is per piece
LABEL_MAX = 32


def pc_version(root=ROOT):
    """This DSiRPC's version, for the console's screen: the download's
    ("v0.8.1", "dev-abc1234": version.txt, or the macOS app's Info.plist),
    a source checkout's commit ("dev-abc1234"), else "dev"."""
    try:
        with open(os.path.join(root, "version.txt"), encoding="utf-8") as f:
            first = f.readline().strip()
        if first.startswith("DSiRPC "):
            return first[len("DSiRPC "):].strip()
    except OSError:
        pass
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        plist = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "Info.plist")
        try:
            with open(plist, "rb") as f:
                version = plistlib.load(f).get("DSiRPCVersion")
            if version:
                return str(version)
        except (OSError, ValueError, plistlib.InvalidFileException):
            pass
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                           timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0 and r.stdout.strip():
            return "dev-" + r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "dev"


class ConsoleFiles:
    """DSiRPC's copies of the console's files, looked for in root (DSiRPC's
    folder) each time they're asked for: a newer download unzipped over this
    one is offered right away. CRCs are kept until a file changes."""

    def __init__(self, root=ROOT, version=None):
        self.root = root
        self._version = version
        self._crcs = {}          # path -> (size, mtime_ns, crc)

    @property
    def version(self):
        if self._version is None:
            self._version = pc_version(self.root)
        return self._version

    def path(self, file):
        if file not in NAMES:
            return None
        for p in (os.path.join(self.root, SD_FOLDER, NAMES[file]), os.path.join(self.root, BUILDS[file])):
            if os.path.isfile(p):
                return p
        return None

    def _crc(self, path, st):
        known = self._crcs.get(path)
        if known and known[:2] == (st.st_size, st.st_mtime_ns):
            return known[2]
        crc = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
        self._crcs[path] = (st.st_size, st.st_mtime_ns, crc)
        return crc

    def files(self):
        """{file: (size, CRC32)} for the files DSiRPC has (none too big,
        none unreadable)."""
        out = {}
        for file in NAMES:
            p = self.path(file)
            if not p:
                continue
            try:
                st = os.stat(p)
                if 0 < st.st_size <= MAX_FILE:
                    out[file] = (st.st_size, self._crc(p, st))
            except OSError as e:
                logging.warning(f"Console update: can't read {p}: {e}")
        return out

    def read(self, file):
        """(bytes, CRC32) of one file, or None."""
        p = self.path(file)
        if not p:
            return None
        try:
            with open(p, "rb") as f:
                data = f.read(MAX_FILE + 1)
        except OSError as e:
            logging.warning(f"Console update: can't read {p}: {e}")
            return None
        if not data or len(data) > MAX_FILE:
            return None
        return data, zlib.crc32(data)


def handle(magic, read, send, files):
    """Answers one request: magic is the 4 bytes already read, read(n) and
    send(bytes) talk to the console, files is the ConsoleFiles (None while
    console updates are off)."""
    rest = read(HEADER.size - 4)
    _, version, mac, model, op, file = HEADER.unpack(magic + rest)
    who = saves.console_label(model, mac)

    if op == OP_GET:
        got = files.read(file) if files is not None else None
        if got is None:
            send(b"DRUF" + struct.pack("<HII", OFF if files is None else NOT_FOUND, 0, 0))
            return
        data, crc = got
        send(b"DRUF" + struct.pack("<HII", OK, len(data), crc))
        for i in range(0, len(data), CHUNK):
            send(data[i:i + CHUNK])
        logging.info(f"Console update: sent {WHAT[file]} ({len(data) // 1024} KB) to the {who}")
        return

    if op != OP_LIST or files is None:
        send(b"DRUA" + struct.pack("<HBB", BAD_REQUEST if op != OP_LIST else OFF, 0, 0))
        return
    have = files.files()
    label = files.version.encode("ascii", "replace")[:LABEL_MAX]
    out = [b"DRUA" + struct.pack("<HB", OK, len(have))]
    out += [FILE_ENTRY.pack(file, size, crc) for file, (size, crc) in sorted(have.items())]
    out.append(bytes([len(label)]) + label)
    send(b"".join(out))
    logging.debug(f"Console update: the {who} asked; DSiRPC {files.version} has "
                  + (", ".join(f"{WHAT[f]} ({c:08X})" for f, (_, c) in sorted(have.items())) or "no console files"))


# -- a console, for tests ------------------------------------------------------

def request(op, file=0, mac=b"\0\x09\xbf\x12\x3f\x21", model=0):
    return HEADER.pack(MAGIC, VERSION, mac, model, op, file)
