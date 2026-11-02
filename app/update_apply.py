"""
update_apply.py - puts a new release of DSiRPC's Windows download in place
once DSiRPC has quit. app/updates.py starts it with the new release's own
Python, from a copy beside the update, so nothing it replaces is in use:

    pythonw.exe update_apply.py --pid N --new <the new DSiRPC folder> --install <DSiRPC's folder> [--start]

Only the program's own files change. Each of the program's folders the new
release has (PROGRAM_FOLDERS) and each of its files replaces the old one,
which is kept as <name>.old until everything is in; then the folders that
hold your files too (ra/, Assets/, launcher/) get the release's files added
or replaced. Everything else in DSiRPC's folder (dsirpc.cfg, ra/'s sets and
caches, logs/, saves/, the downloaded sprites) is left as it is. If
something can't be put in place, what was replaced goes back, so DSiRPC
starts again as it was.

Stdlib only, and nothing from DSiRPC: it runs with whichever Python the new
release brings, and keeps working for releases made after it. Keep its
arguments as they are.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

# The folders that are all program: replaced whole
PROGRAM_FOLDERS = {"python", "app", "core", "overlay", "rpc", "utils", "tools", "third_party", "licenses",
                   "SD card"}
WAIT_S = 120


def wait_for_exit(pid, timeout=WAIT_S):
    """True once process pid has ended (or wasn't there)."""
    if not pid:
        return True
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)    # SYNCHRONIZE
        if not handle:
            return True
        try:
            return kernel32.WaitForSingleObject(handle, int(timeout * 1000)) == 0    # WAIT_OBJECT_0
        finally:
            kernel32.CloseHandle(handle)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.2)
    return False


def _remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.lexists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _merge(src, dst):
    """Adds src's files to dst, replacing the ones with the same name."""
    for folder, _, files in os.walk(src):
        target = os.path.join(dst, os.path.relpath(folder, src))
        os.makedirs(target, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(folder, name), os.path.join(target, name))


def apply(new, install, log=print):
    """Puts new's files in install. True once everything's in; False if
    something couldn't be (what was replaced is back as it was)."""
    replaced = []       # (path, its old one's backup or None)
    names = sorted(os.listdir(new))
    mixed = [n for n in names if os.path.isdir(os.path.join(new, n)) and n not in PROGRAM_FOLDERS]
    name = ""
    try:
        for name in names:
            if name in mixed:
                continue
            src, dst = os.path.join(new, name), os.path.join(install, name)
            backup = None
            if os.path.lexists(dst):
                backup = dst + ".old"
                _remove(backup)
                os.replace(dst, backup)
            replaced.append((dst, backup))
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
    except OSError as e:
        log(f"Couldn't put {name} in place ({e}): the old version goes back")
        for dst, backup in reversed(replaced):
            _remove(dst)
            if backup:
                try:
                    os.replace(backup, dst)
                except OSError as e2:
                    log(f"Couldn't put {os.path.basename(dst)} back ({e2}): it's in {backup}")
        return False
    for _, backup in replaced:
        if backup:
            _remove(backup)
    # Then the release's files in the folders that hold yours too
    for name in mixed:
        try:
            _merge(os.path.join(new, name), os.path.join(install, name))
        except OSError as e:
            log(f"Couldn't add all of {name}'s new files ({e})")
    return True


def start(install):
    """DSiRPC in the tray again, as DSiRPC.bat starts it."""
    pythonw = os.path.join(install, "python", "pythonw.exe")
    flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0    # DETACHED_PROCESS, new process group
    subprocess.Popen([pythonw, "dsirpc.py", "tray"], cwd=install, creationflags=flags, close_fds=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Put a new release of DSiRPC in place once it has quit")
    ap.add_argument("--pid", type=int, default=0, help="DSiRPC's process, to wait for")
    ap.add_argument("--new", required=True, help="the new release's DSiRPC folder")
    ap.add_argument("--install", required=True, help="DSiRPC's folder")
    ap.add_argument("--log", help="a file to add what happened to")
    ap.add_argument("--start", action="store_true", help="start DSiRPC again afterwards")
    args = ap.parse_args(argv)

    def log(text):
        line = time.strftime("%Y-%m-%d %H:%M:%S ") + text
        if args.log:
            try:
                with open(args.log, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass
        else:
            print(line)

    if not wait_for_exit(args.pid):
        log(f"DSiRPC (process {args.pid}) didn't quit: not updated")
        return 1
    ok = apply(args.new, args.install, log)
    log(f"Updated from {args.new}" if ok else "Not updated")
    if args.start:
        try:
            start(args.install)
        except OSError as e:
            log(f"Couldn't start DSiRPC again: {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
