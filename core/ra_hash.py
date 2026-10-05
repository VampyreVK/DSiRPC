"""
ra_hash.py - RetroAchievements' hash of a DS game file, and finding the file
for a game code in a folder of games.

RetroAchievements identifies a game by an MD5 of parts of its ROM file (the
same hash every RA emulator computes), not by its game code. The DSi can't
send that (the ROM is on its SD card, and what's in RAM has been unpacked),
so when the PC has a copy of the game (say in RALibretro's games folder),
DSiRPC hashes that copy: the exact way to tell RetroAchievements which game
and which version is running.

nds_hash() is a port of rcheevos' rc_hash_nintendo_ds() (src/rhash/hash_rom.c,
v12.5.0), which hashes the first 0x160 bytes of the header, the ARM9 and ARM7
code and the 0xA00-byte icon and title block. DSi games use the same hash.
"""

import hashlib
import json
import os
import struct

from . import ra_set

EXTENSIONS = (".nds", ".dsi", ".srl")
INDEX_FILE = os.path.join(ra_set.RA_DIR, "cache", "roms.json")


class HashError(Exception):
    pass


def nds_hash(path):
    """RetroAchievements' hash of a .nds file, as 32 lower-case hex digits."""
    with open(path, "rb") as f:
        header = f.read(512)
        if len(header) != 512:
            raise HashError(f"{path}: too short for a DS game")
        offset = 0
        if header[0:4] == b"\x2E\x00\x00\xEA" and header[0xB0:0xB4] == b"\x44\x46\x96\x00":
            offset = 512  # SuperCard header
            f.seek(offset)
            header = f.read(512).ljust(512, b"\0")
        arm9_addr, = struct.unpack_from("<I", header, 0x20)
        arm9_size, = struct.unpack_from("<I", header, 0x2C)
        arm7_addr, = struct.unpack_from("<I", header, 0x30)
        arm7_size, = struct.unpack_from("<I", header, 0x3C)
        icon_addr, = struct.unpack_from("<I", header, 0x68)
        if arm9_size + arm7_size > 16 * 1024 * 1024:
            raise HashError(f"{path}: ARM9 + ARM7 code over 16 MB, not a DS game")
        md5 = hashlib.md5()
        md5.update(header[:0x160])
        for addr, size in ((arm9_addr, arm9_size), (arm7_addr, arm7_size)):
            f.seek(addr + offset)
            md5.update(f.read(size).ljust(size, b"\0"))
        f.seek(icon_addr + offset)
        md5.update(f.read(0xA00).ljust(0xA00, b"\0"))  # rcheevos pads a short icon block with zeros
    return md5.hexdigest()


def game_code(path):
    """The game code in a .nds file's header ('AMCE'), or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(0x10)
            if head[0:4] == b"\x2E\x00\x00\xEA":
                f.seek(512)
                head = f.read(0x10)
    except OSError:
        return None
    code = head[0x0C:0x10]
    if len(code) == 4 and all(48 <= b <= 57 or 65 <= b <= 90 for b in code):
        return code.decode("ascii")
    return None


class RomIndex:
    """Which file in a folder (and its subfolders) is which game. Each file's
    game code is read once and remembered in ra/cache/roms.json (by path,
    size and time), and its hash only when it's needed."""

    def __init__(self, folder, index_file=INDEX_FILE):
        self.folder = folder
        self.index_file = index_file
        self._entries = None

    def _load(self):
        try:
            with open(self.index_file, encoding="utf-8") as f:
                data = json.load(f)
            self._entries = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self._entries = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
            tmp = self.index_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=0)
            os.replace(tmp, self.index_file)
        except OSError:
            pass

    def _files(self):
        for root, dirs, files in os.walk(self.folder):
            for name in files:
                if name.lower().endswith(EXTENSIONS):
                    yield os.path.join(root, name)

    def find(self, code):
        """(path, hash) of the file for a game code, or None."""
        if not self.folder or not os.path.isdir(self.folder):
            return None
        if self._entries is None:
            self._load()
        changed = False
        found = None
        for path in self._files():
            try:
                st = os.stat(path)
            except OSError:
                continue
            key = os.path.normcase(os.path.abspath(path))
            e = self._entries.get(key)
            if not e or e.get("size") != st.st_size or e.get("mtime") != int(st.st_mtime):
                e = {"size": st.st_size, "mtime": int(st.st_mtime), "code": game_code(path)}
                self._entries[key] = e
                changed = True
            if e.get("code") == code and found is None:
                if not e.get("hash"):
                    try:
                        e["hash"] = nds_hash(path)
                        changed = True
                    except (OSError, HashError):
                        continue
                found = (path, e["hash"])
        if changed:
            self._save()
        return found
