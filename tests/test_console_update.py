"""Updating the console's files from the PC: DSiRPC's side (core/console_update.py:
which files it offers, the exchange, through ConsoleSync) and, end to end,
the launcher's (launcher/source/update.c built for the PC) on SD cards in
temporary folders: both files updated, only what changed, the CRCs kept in
update.idx, a missing nds-bootstrap put there, updates off, a damaged file,
files changing on the PC mid-update, a swap that fails and puts everything
back, a DSiRPC from before updates, finding a DSiRPC from another release,
and the Auto-update setting."""

import os
import socket
import struct
import subprocess
import threading
import time
import zlib

import pytest

from core import console_update as cu, offline
from core.console_sync import ConsoleSync
from helpers import REPO, cbuild

LAUNCHER = os.path.join(REPO, "launcher", "source")
HOST = os.path.join(REPO, "tests", "c", "update", "update_host.c")
SD = os.path.join("sd:", "DSiRPC")


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def nds(tag, size=4096):
    """A small .nds: a header with its CRC, then `tag` over and over."""
    data = bytearray(size)
    data[0:12] = b"DSIRPC TEST\0"
    data[0x0C:0x10] = b"####"
    data[0x200:] = (tag.encode() * (size // len(tag) + 1))[:size - 0x200]
    data[0x15E:0x160] = crc16(data[:0x15E]).to_bytes(2, "little")
    return bytes(data)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def read(path):
    with open(path, "rb") as f:
        return f.read()


class FakeConn:
    """read(n) and send() for core.console_update.handle(), from one request."""

    def __init__(self, data):
        self.data, self.out = data, b""

    def read(self, n):
        assert len(self.data) >= n, "read past the request"
        chunk, self.data = self.data[:n], self.data[n:]
        return chunk

    def send(self, data):
        self.out += data


def ask(files, op, file=0):
    req = cu.request(op, file)
    conn = FakeConn(req[4:])
    cu.handle(req[:4], conn.read, conn.send, files)
    return conn.out


def parse_list(out):
    assert out[:4] == b"DRUA"
    status, n = struct.unpack_from("<HB", out, 4)
    pos, files = 7, {}
    for _ in range(n):
        fid, size, crc = cu.FILE_ENTRY.unpack_from(out, pos)
        files[fid] = (size, crc)
        pos += cu.FILE_ENTRY.size
    label = out[pos + 1:pos + 1 + out[pos]].decode()
    assert len(out) == pos + 1 + out[pos]
    return status, files, label


# -- DSiRPC's side -------------------------------------------------------------

def test_the_pc_offers_the_files_it_came_with(tmp_path):
    root = str(tmp_path)
    write(os.path.join(root, "SD card", "DSiRPC", "dsirpc-launcher.nds"), nds("launcher"))
    write(os.path.join(root, "SD card", "DSiRPC", "nds-bootstrap-dsirpc.nds"), nds("bootstrap", 8192))
    write(os.path.join(root, "launcher", "dsirpc-launcher.nds"), nds("a local build"))   # the download's wins
    with open(os.path.join(root, "version.txt"), "w") as f:
        f.write("DSiRPC v0.9.0\nPython 3.13.16\n")
    files = cu.ConsoleFiles(root)
    assert files.version == "v0.9.0"
    have = files.files()
    assert have == {cu.LAUNCHER: (4096, zlib.crc32(nds("launcher"))),
                    cu.BOOTSTRAP: (8192, zlib.crc32(nds("bootstrap", 8192)))}

    status, listed, label = parse_list(ask(files, cu.OP_LIST))
    assert (status, listed, label) == (cu.OK, have, "v0.9.0")
    out = ask(files, cu.OP_GET, cu.BOOTSTRAP)
    assert out[:4] == b"DRUF" and struct.unpack_from("<HII", out, 4) == (cu.OK, 8192, have[cu.BOOTSTRAP][1])
    assert out[14:] == nds("bootstrap", 8192)
    assert struct.unpack_from("<H", ask(files, cu.OP_GET, 9), 4)[0] == cu.NOT_FOUND
    assert struct.unpack_from("<H", ask(files, 7), 4)[0] == cu.BAD_REQUEST


def test_a_source_checkout_offers_its_own_builds(tmp_path):
    root = str(tmp_path)
    write(os.path.join(root, "launcher", "dsirpc-launcher.nds"), nds("launcher"))
    write(os.path.join(root, "nds-bootstrap", "retail", "bin", "nds-bootstrap-nightly.nds"), nds("bootstrap"))
    files = cu.ConsoleFiles(root, version="dev-abc1234")
    assert set(files.files()) == {cu.LAUNCHER, cu.BOOTSTRAP}
    assert files.version == "dev-abc1234"
    assert cu.ConsoleFiles(str(tmp_path / "nothing")).files() == {}
    assert cu.pc_version(str(tmp_path / "nothing")) == "dev"    # no version.txt, not a git checkout


def test_crcs_are_kept_until_a_file_changes(tmp_path, monkeypatch):
    path = os.path.join(str(tmp_path), "SD card", "DSiRPC", "dsirpc-launcher.nds")
    write(path, nds("one"))
    files = cu.ConsoleFiles(str(tmp_path), version="v1")
    first = files.files()[cu.LAUNCHER]
    reads = []
    real_crc = cu.zlib.crc32
    monkeypatch.setattr(cu.zlib, "crc32", lambda *a: reads.append(1) or real_crc(*a))
    assert files.files()[cu.LAUNCHER] == first and not reads
    write(path, nds("two", 5000))
    assert files.files()[cu.LAUNCHER] == (5000, real_crc(nds("two", 5000))) and reads


def test_console_updates_off():
    status, listed, label = parse_list(ask(None, cu.OP_LIST))
    assert (status, listed, label) == (cu.OFF, {}, "")
    assert struct.unpack_from("<HII", ask(None, cu.OP_GET, cu.LAUNCHER), 4) == (cu.OFF, 0, 0)


def test_an_older_dsirpc_turns_the_request_down_at_once():
    """The request is as long as the offline sync's, so a DSiRPC from before
    updates reads all of it, sees it isn't a sync request and answers,
    instead of waiting for bytes that never come."""
    req = cu.request(cu.OP_LIST)
    assert len(req) == offline.REQUEST.size

    def more(n):
        raise AssertionError("it waited for more")
    with pytest.raises(offline.FormatError):
        offline.parse_request(req, more)


def test_consolesync_hands_the_request_over(tmp_path):
    write(os.path.join(str(tmp_path), "SD card", "DSiRPC", "dsirpc-launcher.nds"), nds("launcher"))
    files = cu.ConsoleFiles(str(tmp_path), version="v0.9.0")
    on = {"files": files}
    sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1", updates=lambda: on["files"])
    sync.start()
    try:
        def exchange(req):
            with socket.create_connection(("127.0.0.1", sync.port), timeout=5) as s:
                s.sendall(req)
                s.shutdown(socket.SHUT_WR)
                out = b""
                while chunk := s.recv(65536):
                    out += chunk
            return out
        status, listed, _ = parse_list(exchange(cu.request(cu.OP_LIST)))
        assert status == cu.OK and set(listed) == {cu.LAUNCHER}
        assert exchange(cu.request(cu.OP_GET, cu.LAUNCHER))[14:] == nds("launcher")
        on["files"] = None    # the tray's "Console updates" off
        assert parse_list(exchange(cu.request(cu.OP_LIST)))[0] == cu.OFF
    finally:
        sync.stop()


# -- end to end, with the launcher's side --------------------------------------

@pytest.fixture(scope="module")
def host(cc, tmp_path_factory):
    exe = str(tmp_path_factory.mktemp("update") / "update_host")
    sources = [HOST] + [os.path.join(LAUNCHER, f)
                        for f in ("update.c", "sync.c", "settings.c", "bootstrap_ini.c", "stats.c")]
    return cbuild.build(exe, sources, flags=["-std=gnu11", "-I", LAUNCHER])


class Setup:
    """DSiRPC (its console files in a folder) and a console's SD card in another."""

    def __init__(self, host, tmp_path):
        self.host = host
        self.pc = str(tmp_path / "pc")
        self.sd = str(tmp_path / "console")
        os.makedirs(os.path.join(self.sd, SD), exist_ok=True)
        self.files = cu.ConsoleFiles(self.pc, version="dev-abc1234")
        self.on = True
        self.sync = ConsoleSync(lambda *a: [], lambda u: None, port=0, host="127.0.0.1",
                                updates=lambda: self.files if self.on else None)
        self.sync.start()

    def pc_file(self, name, data):
        write(os.path.join(self.pc, "SD card", "DSiRPC", name), data)

    def sd_path(self, name):
        return os.path.join(self.sd, SD, name)

    def run(self, *commands, port=None):
        r = subprocess.run([self.host, str(port or self.sync.port)], input="\n".join(commands) + "\n",
                           capture_output=True, text=True, cwd=self.sd, env=cbuild.run_env(), timeout=120)
        assert r.returncode == 0, r.stderr
        assert not any(ln.startswith("?") for ln in r.stdout.splitlines()), r.stdout
        return r.stdout.splitlines()


CHECK = "check sd:/DSiRPC/dsirpc-launcher.nds|sd:/DSiRPC/nds-bootstrap-dsirpc.nds|sd:/DSiRPC"


def result(lines, command):
    line = next(ln for ln in lines if ln.startswith(command + " "))
    return line[len(command) + 1:].split("|")


def planned(lines):
    return {int(ln[5:].split("|")[0]): ln[5:].split("|") for ln in lines if ln.startswith("file ")}


@pytest.fixture
def setup(host, tmp_path):
    s = Setup(host, tmp_path)
    yield s
    s.sync.stop()


def test_the_console_updates_both_files(setup):
    setup.pc_file("dsirpc-launcher.nds", nds("new launcher", 6000))
    setup.pc_file("nds-bootstrap-dsirpc.nds", nds("new bootstrap", 9000))
    write(setup.sd_path("dsirpc-launcher.nds"), nds("old launcher", 5000))
    write(setup.sd_path("nds-bootstrap-dsirpc.nds"), nds("old bootstrap", 9000))   # same size: the CRC tells
    out = setup.run(CHECK, "download", "install")
    assert result(out, "check")[:4] == ["1", "2", "15000", "dev-abc1234"]
    assert result(out, "download")[0] == "1" and result(out, "install")[0] == "1"
    assert read(setup.sd_path("dsirpc-launcher.nds")) == nds("new launcher", 6000)
    assert read(setup.sd_path("nds-bootstrap-dsirpc.nds")) == nds("new bootstrap", 9000)
    assert sorted(os.listdir(os.path.join(setup.sd, SD))) == ["dsirpc-launcher.nds", "nds-bootstrap-dsirpc.nds",
                                                             "update.idx"]
    index = read(setup.sd_path("update.idx")).decode().splitlines()
    assert index[0] == "DSiRPC update 1"
    assert f"{zlib.crc32(nds('new launcher', 6000)):08X} 6000 " in index[1]
    assert index[1].endswith(" sd:/DSiRPC/dsirpc-launcher.nds")

    # Up to date now. update.idx stands in for reading the files while their
    # sizes and times stay the same (so a file changed in place, keeping
    # both, isn't read again).
    assert result(setup.run(CHECK), "check")[:2] == ["0", "0"]
    path = setup.sd_path("nds-bootstrap-dsirpc.nds")
    st = os.stat(path)
    write(path, nds("tampered!", 9000))
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert result(setup.run(CHECK), "check")[:2] == ["0", "0"]
    os.utime(path, (st.st_atime + 10, st.st_mtime + 10))      # its time changed: read again
    out = setup.run(CHECK)
    assert result(out, "check")[:2] == ["1", "1"] and planned(out)[cu.BOOTSTRAP][4] == "1"


def test_only_what_changed_and_a_missing_bootstrap(setup):
    setup.pc_file("dsirpc-launcher.nds", nds("launcher"))
    setup.pc_file("nds-bootstrap-dsirpc.nds", nds("bootstrap", 9000))
    write(setup.sd_path("dsirpc-launcher.nds"), nds("launcher"))
    out = setup.run(CHECK, "download", "install")
    assert result(out, "check")[:3] == ["1", "1", "9000"]
    assert planned(out)[cu.LAUNCHER][4] == "0" and planned(out)[cu.BOOTSTRAP][4] == "1"
    assert read(setup.sd_path("nds-bootstrap-dsirpc.nds")) == nds("bootstrap", 9000)

    # A launcher that can't find its own file leaves it alone
    out = setup.run("check |sd:/DSiRPC/nds-bootstrap-dsirpc.nds|sd:/DSiRPC")
    assert result(out, "check")[:2] == ["0", "0"] and set(planned(out)) == {cu.BOOTSTRAP}


def test_nothing_without_updates_or_files_on_the_pc(setup):
    write(setup.sd_path("dsirpc-launcher.nds"), nds("launcher"))
    assert result(setup.run(CHECK), "check")[:2] == ["0", "0"]        # the PC has no files
    setup.pc_file("dsirpc-launcher.nds", nds("new launcher"))
    setup.on = False
    assert result(setup.run(CHECK), "check")[:2] == ["0", "0"]        # console updates off
    setup.on = True
    assert result(setup.run(CHECK), "check")[:2] == ["1", "1"]


def test_a_damaged_file_changes_nothing(setup):
    setup.pc_file("dsirpc-launcher.nds", b"not an nds file at all " * 100)
    write(setup.sd_path("dsirpc-launcher.nds"), nds("old launcher"))
    out = setup.run(CHECK, "download")
    assert result(out, "download") == ["-1", "the launcher arrived damaged"]
    assert read(setup.sd_path("dsirpc-launcher.nds")) == nds("old launcher")
    assert sorted(os.listdir(os.path.join(setup.sd, SD))) == ["dsirpc-launcher.nds"]


def test_files_changing_on_the_pc_mid_update(setup, tmp_path):
    setup.pc_file("dsirpc-launcher.nds", nds("new launcher"))
    write(setup.sd_path("dsirpc-launcher.nds"), nds("old launcher"))
    # The check runs, then a newer download is unzipped over DSiRPC's folder
    proc = subprocess.Popen([setup.host, str(setup.sync.port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, cwd=setup.sd, env=cbuild.run_env())
    proc.stdin.write(CHECK + "\n")
    proc.stdin.flush()
    assert proc.stdout.readline().startswith("check 1|")
    proc.stdout.readline()
    setup.pc_file("dsirpc-launcher.nds", nds("newer launcher", 4100))
    out, _ = proc.communicate("download\n", timeout=60)
    assert out.splitlines()[-1].startswith("download -1|DSiRPC's files changed while updating")
    assert read(setup.sd_path("dsirpc-launcher.nds")) == nds("old launcher")
    assert not os.path.exists(setup.sd_path("dsirpc-launcher.nds.tmp"))


def test_a_swap_that_fails_puts_everything_back(setup):
    setup.pc_file("dsirpc-launcher.nds", nds("new launcher"))
    setup.pc_file("nds-bootstrap-dsirpc.nds", nds("new bootstrap"))
    write(setup.sd_path("dsirpc-launcher.nds"), nds("old launcher"))
    write(setup.sd_path("nds-bootstrap-dsirpc.nds"), nds("old bootstrap"))
    # The launcher goes in first, then nds-bootstrap's download is gone
    out = setup.run(CHECK, "download", "unlink sd:/DSiRPC/nds-bootstrap-dsirpc.nds.tmp", "install")
    assert result(out, "download")[0] == "1"
    assert result(out, "install") == ["0", "Can't replace nds-bootstrap (is the SD card locked?). "
                                           "The old files are back."]
    assert read(setup.sd_path("dsirpc-launcher.nds")) == nds("old launcher")
    assert read(setup.sd_path("nds-bootstrap-dsirpc.nds")) == nds("old bootstrap")
    assert sorted(os.listdir(os.path.join(setup.sd, SD))) == ["dsirpc-launcher.nds", "nds-bootstrap-dsirpc.nds",
                                                             "update.idx"]


def test_a_dsirpc_from_before_updates(setup):
    """It turns the request down as a bad offline sync, right away."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def old_dsirpc():
        conn, _ = srv.accept()
        with conn:
            header = conn.recv(offline.REQUEST.size, socket.MSG_WAITALL)
            try:
                offline.parse_request(header, conn.recv)
            except offline.FormatError:
                conn.sendall(offline.build_answer(1, 0, []))
            try:
                conn.recv(16)     # the console hangs up (with the answer half read)
            except OSError:
                pass
    t = threading.Thread(target=old_dsirpc, daemon=True)
    t.start()
    write(setup.sd_path("dsirpc-launcher.nds"), nds("launcher"))
    start = time.monotonic()
    out = setup.run(CHECK, port=srv.getsockname()[1])
    assert result(out, "check")[:2] == ["0", "0"] and time.monotonic() - start < 10
    t.join(5)
    srv.close()


def test_finding_a_dsirpc_from_another_release(setup):
    """The sync can't use it, but the update check can: its address and TCP
    port are kept."""
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))

    def answer():
        data, addr = udp.recvfrom(64)
        if data.startswith(offline.DISCOVER):
            udp.sendto(offline.ANSWER + struct.pack("<BH", offline.VERSION + 1, 4321), addr)
    t = threading.Thread(target=answer, daemon=True)
    t.start()
    out = setup.run("find", port=udp.getsockname()[1])
    r, addr, port, msg = result(out, "find")
    assert (r, addr, port) == ("-1", "127.0.0.1", "4321") and "different releases" in msg
    t.join(5)
    udp.close()


def test_the_auto_update_setting(setup):
    assert setup.run("settings sd:/DSiRPC/launcher.ini|off")[-1] == "settings 1|0"
    assert setup.run("settings sd:/DSiRPC/launcher.ini|on")[-1] == "settings 1|1"
    assert "AUTO_UPDATE = on" in read(setup.sd_path("launcher.ini")).decode()
    assert setup.run("settings sd:/DSiRPC/launcher.ini|-")[-1] == "settings 1|1"   # not there: on
