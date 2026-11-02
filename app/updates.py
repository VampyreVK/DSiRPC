"""
updates.py - DSiRPC updating itself from its GitHub releases, for the tray
(app/tray.py): its "Check for updates...", and a quiet look a minute after
DSiRPC starts and then once a day ([app] check_updates). When the latest
release is newer than this DSiRPC, the menu offers it ("Update to
v1.1.0..."). Picking it downloads this computer's zip (checked against the
SHA-256 GitHub gives for it), unpacks it in DSiRPC's data folder (update/)
and starts a small step that waits for DSiRPC to quit, puts the new version
in place and starts it again. Then DSiRPC quits.

    Windows (the download's folder, with python/ and version.txt):
            app/update_apply.py, run by the new release's own Python,
            replaces the program's folders and files only; dsirpc.cfg,
            ra/, logs/, saves/ and the downloaded sprites stay as they are.
    macOS   (DSiRPC.app): a shell script swaps the app for the new one
            (the settings are in ~/Library/Application Support/DSiRPC).

Where it can't update itself (a source checkout, a dev build from a branch,
an app it can't write to), it says what the latest release is and offers
its page. The console's files come with the new DSiRPC: the launcher
updates itself from it the next time it connects (core/console_update.py).

The releases' downloads have to keep their names (DSiRPC-<tag>-windows.zip
and DSiRPC-<tag>-macos.zip, as .github/workflows/build.yml makes them) and
say which version they are (version.txt, the app's Info.plist).
"""

import hashlib
import json
import logging
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile

from core.console_update import pc_version
from core.paths import DATA, MAC_APP, ROOT

REPO = "VampyreVK/DSiRPC"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
UPDATE_DIR = os.path.join(DATA, "update")
LOG = os.path.join(DATA, "logs", "update.log")
FIRST_CHECK_S = 60          # after DSiRPC starts
CHECK_EVERY_S = 24 * 3600
CHUNK = 64 * 1024


class UpdateError(Exception):
    """Why an update couldn't go ahead, said for the person"""


def parse_version(text):
    """(1, 0, 2) for "v1.0.2" or "1.0.2"; None for a dev build ("dev",
    "dev-abc1234") or anything else"""
    m = re.fullmatch(r"v?(\d+)((?:\.\d+)*)", (text or "").strip())
    if not m:
        return None
    parts = (int(m.group(1)),) + tuple(int(p) for p in m.group(2).split(".")[1:])
    return parts + (0,) * (3 - len(parts))


def install_kind():
    """How this DSiRPC updates itself: "windows" (the Windows download),
    "mac" (the macOS app), or None (a source checkout, or anything else)"""
    if MAC_APP:
        return "mac"
    if sys.platform == "win32" and os.path.isfile(os.path.join(ROOT, "version.txt")) and \
            os.path.isfile(os.path.join(ROOT, "python", "pythonw.exe")):
        return "windows"
    return None


def asset_name(tag, kind):
    return f"DSiRPC-{tag}-{'macos' if kind == 'mac' else 'windows'}.zip"


class Release:
    """The latest release, from GitHub's answer: its tag, its page and this
    computer's download (name, url, size, sha256; None if there isn't one)"""

    def __init__(self, data, kind):
        self.tag = str(data.get("tag_name") or "")
        self.version = parse_version(self.tag)
        self.page = data.get("html_url") or RELEASES_PAGE
        self.asset = None
        if kind:
            for a in data.get("assets") or []:
                if a.get("name") == asset_name(self.tag, kind) and a.get("browser_download_url"):
                    digest = str(a.get("digest") or "")
                    self.asset = {"name": a["name"], "url": a["browser_download_url"], "size": int(a.get("size") or 0),
                                  "sha256": digest[7:].lower() if digest.startswith("sha256:") else ""}


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"DSiRPC/{pc_version()}"})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_latest(kind, url=LATEST_URL, timeout=15):
    try:
        with _get(url, timeout) as r:
            data = json.load(r)
    except (OSError, ValueError) as e:
        raise UpdateError(f"GitHub didn't answer ({e})") from e
    release = Release(data, kind)
    if release.version is None:
        raise UpdateError(f"the latest release's tag isn't a version ({release.tag!r})")
    return release


def _remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.lexists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def download(asset, folder, progress=None):
    """The release's zip, in folder, checked against its size and SHA-256.
    progress(done, total) as it comes. Returns its path."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, asset["name"])
    part = path + ".part"
    sha, done = hashlib.sha256(), 0
    try:
        with _get(asset["url"], 30) as r, open(part, "wb") as f:
            total = asset["size"] or int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except OSError as e:
        _remove(part)
        raise UpdateError(f"the download didn't finish ({e})") from e
    if (asset["size"] and done != asset["size"]) or (asset["sha256"] and sha.hexdigest() != asset["sha256"]):
        _remove(part)
        raise UpdateError("the download came out damaged")
    os.replace(part, path)
    return path


def download_version(folder):
    """The version a Windows download says it is (version.txt), or None"""
    try:
        with open(os.path.join(folder, "version.txt"), encoding="utf-8") as f:
            first = f.readline().strip()
    except OSError:
        return None
    return first[len("DSiRPC "):].strip() if first.startswith("DSiRPC ") else None


def app_version(app):
    """The version DSiRPC.app says it is (its Info.plist), or None"""
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
            return str(plistlib.load(f).get("DSiRPCVersion") or "") or None
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None


def unpack(path, folder, kind, tag):
    """The zip, unpacked in folder (emptied first). Returns the new release:
    its DSiRPC folder (Windows) or DSiRPC.app (macOS), once it's checked to
    be that release."""
    _remove(folder)
    os.makedirs(folder)
    try:
        if kind == "mac":
            # ditto keeps the app's links, permissions and signature
            subprocess.run(["ditto", "-x", "-k", path, folder], check=True, capture_output=True)
        else:
            with zipfile.ZipFile(path) as z:
                z.extractall(folder)
    except (OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as e:
        raise UpdateError(f"the download couldn't be unpacked ({e})") from e
    new = os.path.join(folder, "DSiRPC")
    if kind == "mac":
        new = os.path.join(new, "DSiRPC.app")
        version = app_version(new)
    else:
        version = download_version(new)
        if not os.path.isfile(os.path.join(new, "python", "pythonw.exe")):
            version = None
    if version != tag:
        raise UpdateError(f"the download isn't {tag} (it says {version or 'nothing'})")
    return new


def mac_app_path(executable=None):
    """DSiRPC.app, from the app's own program (Contents/MacOS/DSiRPC)"""
    app = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(executable or sys.executable))))
    return app if app.endswith(".app") else None


def cant_replace(kind):
    """Why this DSiRPC can't put a new version in its own place, or None"""
    if kind == "mac":
        app = mac_app_path()
        if app is None:
            return "it isn't running as DSiRPC.app"
        if "/AppTranslocation/" in app:
            return "macOS runs it from a read-only copy (move DSiRPC.app to Applications first)"
        if not (os.access(os.path.dirname(app), os.W_OK) and os.access(app, os.W_OK)):
            return f"it can't write to {os.path.dirname(app)}"
        return None
    if kind == "windows":
        return None if os.access(ROOT, os.W_OK) else f"it can't write to {ROOT}"
    return "it runs from the source code (git pull updates it)"


def mac_script(app, new, pid, log, opener="open"):
    """The shell script that swaps DSiRPC.app for the new one once DSiRPC
    (process pid) has quit, then opens it. The old app is put back if the
    new one can't go in its place."""
    q = shlex.quote
    return f"""#!/bin/sh
# DSiRPC's update (app/updates.py): once DSiRPC (process {pid}) has quit, the
# new app takes the old one's place, then opens
app={q(app)}
new={q(new)}
log={q(log)}
note() {{ echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$log"; }}
n=0
while kill -0 {int(pid)} 2>/dev/null; do
    n=$((n + 1))
    if [ "$n" -gt 600 ]; then note "DSiRPC didn't quit: not updated"; exit 1; fi
    sleep 0.2
done
rm -rf "$app.old"
if mv "$app" "$app.old"; then
    if mv "$new" "$app"; then
        rm -rf "$app.old"
        note "Updated from $new"
    else
        mv "$app.old" "$app"
        note "Couldn't put the new app in place: not updated"
    fi
else
    note "Couldn't move the old app: not updated"
fi
{opener} "$app"
"""


def start_apply(kind, new, pid):
    """Starts the step that puts the new version in place once process pid
    (this DSiRPC) has ended, and starts DSiRPC again."""
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if kind == "mac":
        script = os.path.join(UPDATE_DIR, "update.sh")
        with open(script, "w") as f:
            f.write(mac_script(mac_app_path(), new, pid, LOG))
        os.chmod(script, 0o755)
        subprocess.Popen(["/bin/sh", script], start_new_session=True, close_fds=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    # The new release's Python runs a copy of update_apply.py from here, so
    # nothing it replaces is in use
    script = os.path.join(UPDATE_DIR, "update_apply.py")
    shutil.copy2(os.path.join(ROOT, "app", "update_apply.py"), script)
    flags = 0x00000008 | 0x00000200      # DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([os.path.join(new, "python", "pythonw.exe"), script, "--pid", str(pid), "--new", new,
                      "--install", ROOT, "--log", LOG, "--start"], cwd=UPDATE_DIR, creationflags=flags,
                     close_fds=True)


def clean_up():
    """What an earlier update left in update/: the new DSiRPC runs by now."""
    _remove(UPDATE_DIR)


class Updater:
    """The tray's updates: the menu item's label, the checks and the update.
    The tray gives it notify(body, title), ask(text) -> bool (a question
    answered yes or no), show(text), open_page(url), quit_app() (DSiRPC
    quits so the update can go in) and changed() (the label changed).
    Anything slow runs on a thread of its own."""

    def __init__(self, cfg, notify, ask, show, open_page, quit_app, changed):
        self.cfg = cfg
        self.notify, self.ask, self.show, self.open_page = notify, ask, show, open_page
        self.quit_app, self.changed = quit_app, changed
        self.kind = install_kind()
        self.current = pc_version()
        self.release = None        # the latest release, once looked up
        self.state = "idle"        # or checking, downloading, installing
        self.progress = 0          # the download's, in percent
        self.notified = None       # the release a notification was shown for
        self._busy = threading.Lock()
        self._stop = threading.Event()

    def newer(self, release):
        """Whether release is newer than this DSiRPC (never for a dev build)"""
        current = parse_version(self.current)
        return current is not None and release is not None and release.version is not None and \
            release.version > current

    def label(self):
        if self.state == "checking":
            return "Checking for updates..."
        if self.state == "downloading":
            return f"Downloading {self.release.tag}... {self.progress}%"
        if self.state == "installing":
            return "Installing the update..."
        if self.newer(self.release):
            return f"Update to {self.release.tag}..."
        return "Check for updates..."

    def clicked(self):
        """The menu item: the update if there's one, else a check"""
        threading.Thread(target=self._clicked, name="Updates", daemon=True).start()

    def _clicked(self):
        if self.newer(self.release):
            self.update()
        else:
            self.check(manual=True)

    def start(self):
        """The quiet checks: a minute after DSiRPC starts, then once a day.
        Not for a dev build or a checkout (no release is newer than them)."""
        threading.Thread(target=self._auto, name="UpdateCheck", daemon=True).start()

    def stop(self):
        self._stop.set()

    def _auto(self):
        if self._stop.wait(FIRST_CHECK_S):
            return
        if self._busy.acquire(blocking=False):
            try:
                clean_up()
            finally:
                self._busy.release()
        while parse_version(self.current) is not None:
            if self.cfg.check_updates:
                self.check(manual=False)
            if self._stop.wait(CHECK_EVERY_S):
                return

    def _set(self, state):
        self.state = state
        self.changed()

    def _progress(self, done, total):
        pct = min(100, done * 100 // total) if total else 0
        if pct >= self.progress + 2 or pct == 100:
            self.progress = pct
            self.changed()

    def check(self, manual):
        """Looks up the latest release. Quietly, a notification if it's new
        (once); asked for (manual), the update or what's what."""
        if not self._busy.acquire(blocking=False):
            return
        try:
            self._set("checking")
            try:
                self.release = fetch_latest(self.kind)
            except UpdateError as e:
                logging.info(f"Update check: {e}")
                if manual:
                    self.show(f"Couldn't check for updates: {e}. Try again later.")
                return
            finally:
                self._set("idle")
            release = self.release
            if self.newer(release):
                logging.info(f"Update check: {release.tag} is out (this is {self.current})")
                if not manual and self.notified != release.tag:
                    self.notified = release.tag
                    self.notify(f"DSiRPC {release.tag} is out (you have {self.current}). "
                                f"Pick \"Update to {release.tag}\" in its menu.", "DSiRPC update")
            elif manual and parse_version(self.current) is None:
                if self.ask(f"The latest release is {release.tag}. This DSiRPC is {self.current}, which "
                            f"doesn't update itself.\n\nOpen the release's page?"):
                    self.open_page(release.page)
            elif manual:
                self.show(f"DSiRPC is up to date ({self.current}).")
        finally:
            self._busy.release()
        if manual and self.newer(self.release):
            self.update()

    def update(self):
        """Asks, then downloads the release, unpacks it, starts the step that
        puts it in place, and quits DSiRPC."""
        release = self.release
        why = cant_replace(self.kind)
        if why is None and release.asset is None:
            why = "the release has no download for this computer"
        if why:
            if self.ask(f"DSiRPC {release.tag} is out, but this DSiRPC can't update itself: {why}.\n\n"
                        f"Open the release's page to download it?"):
                self.open_page(release.page)
            return
        if not self.ask(f"DSiRPC {release.tag} is out (you have {self.current}).\n\nUpdate now? DSiRPC "
                        f"downloads it and restarts; your settings, achievements and save backups stay as "
                        f"they are."):
            return
        if not self._busy.acquire(blocking=False):
            return
        try:
            self.progress = 0
            self._set("downloading")
            try:
                path = download(release.asset, UPDATE_DIR, self._progress)
                self._set("installing")
                new = unpack(path, os.path.join(UPDATE_DIR, "new"), self.kind, release.tag)
                start_apply(self.kind, new, os.getpid())
            except (UpdateError, OSError) as e:
                logging.warning(f"Update to {release.tag}: {e}")
                self._set("idle")
                if self.ask(f"Couldn't update to {release.tag}: {e}.\n\nOpen the release's page to download "
                            f"it yourself?"):
                    self.open_page(release.page)
                return
            logging.info(f"Update: {release.tag} is ready; DSiRPC quits so it can go in, then starts again")
            self.notify(f"Restarting with {release.tag}...", "DSiRPC update")
            self.quit_app()
        finally:
            self._busy.release()
