"""DSiRPC updating itself (app/updates.py, app/update_apply.py): the versions,
the latest release's download for each computer, the download checked
against its SHA-256, the unpacked release checked to be that one, the
Windows step that swaps the program's files and keeps everyone's own (and
puts everything back if it can't), the macOS script that swaps the app
(run with /bin/sh here), and the tray's side: when it says what, and what
it does when asked."""

import functools
import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
import zipfile

import pytest

from app import update_apply, updates


# -- versions and releases -----------------------------------------------------------

def test_versions():
    assert updates.parse_version("v1.0.2") == (1, 0, 2)
    assert updates.parse_version("1.2") == (1, 2, 0)
    assert updates.parse_version("v1.10.0") > updates.parse_version("v1.9.9")
    for text in ("dev", "dev-abc1234", "", None, "v1.0.0-rc1", "latest"):
        assert updates.parse_version(text) is None, text


def github(tag="v1.1.0", digest=True):
    """GitHub's answer for the latest release, as for v0.9.1"""
    def asset(name, size):
        a = {"name": name, "size": size, "browser_download_url": f"https://github.com/x/releases/download/{tag}/{name}"}
        if digest:
            a["digest"] = "sha256:" + "AB" * 32
        return a
    return {"tag_name": tag, "html_url": f"https://github.com/VampyreVK/DSiRPC/releases/tag/{tag}",
            "assets": [asset("dsirpc-launcher.nds", 1), asset(f"DSiRPC-{tag}-macos.zip", 30),
                       asset(f"DSiRPC-{tag}-windows.zip", 31), asset("nds-bootstrap-dsirpc.nds", 2)]}


def test_each_computer_gets_its_own_download():
    win = updates.Release(github(), "windows")
    assert (win.tag, win.version) == ("v1.1.0", (1, 1, 0))
    assert win.asset["name"] == "DSiRPC-v1.1.0-windows.zip" and win.asset["size"] == 31
    assert win.asset["sha256"] == "ab" * 32
    assert updates.Release(github(), "mac").asset["name"] == "DSiRPC-v1.1.0-macos.zip"
    assert updates.Release(github(), None).asset is None            # a checkout: nothing to download
    assert updates.Release(github(digest=False), "windows").asset["sha256"] == ""


@pytest.fixture
def server(tmp_path):
    """A web server for tmp_path/www: (base url, the folder)"""
    www = tmp_path / "www"
    www.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(www))
    handler.log_message = lambda *a: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", www
    httpd.shutdown()


def test_the_latest_release_from_github(server):
    url, www = server
    (www / "latest").write_text(json.dumps(github("v2.0.1")))
    release = updates.fetch_latest("windows", url=url + "/latest")
    assert release.tag == "v2.0.1" and release.asset["name"] == "DSiRPC-v2.0.1-windows.zip"
    (www / "bad").write_text(json.dumps({"tag_name": "nightly"}))
    with pytest.raises(updates.UpdateError, match="isn't a version"):
        updates.fetch_latest("windows", url=url + "/bad")
    with pytest.raises(updates.UpdateError, match="didn't answer"):
        updates.fetch_latest("windows", url=url + "/missing")


def test_the_download_is_checked(server, tmp_path):
    url, www = server
    data = os.urandom(200_000)
    (www / "DSiRPC-v1.1.0-windows.zip").write_bytes(data)
    asset = {"name": "DSiRPC-v1.1.0-windows.zip", "url": url + "/DSiRPC-v1.1.0-windows.zip", "size": len(data),
             "sha256": hashlib.sha256(data).hexdigest()}
    seen = []
    path = updates.download(asset, str(tmp_path / "update"), lambda done, total: seen.append((done, total)))
    assert open(path, "rb").read() == data and seen[-1] == (len(data), len(data))

    # Damaged on the way (or not the release's): nothing's kept
    for bad in ({"sha256": "00" * 32}, {"size": len(data) + 1}):
        with pytest.raises(updates.UpdateError, match="damaged"):
            updates.download(dict(asset, **bad), str(tmp_path / "other"))
        assert os.listdir(tmp_path / "other") == []


# -- unpacking ------------------------------------------------------------------------

def windows_zip(path, version="v1.1.0", files=None):
    """A Windows download: DSiRPC/ with its Python, version.txt and more"""
    files = files or {}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("DSiRPC/version.txt", f"DSiRPC {version}\r\nPython 3.13.16\r\n")
        z.writestr("DSiRPC/python/pythonw.exe", b"MZ new")
        for name, data in files.items():
            z.writestr("DSiRPC/" + name, data)


def test_the_unpacked_release_is_checked(tmp_path):
    windows_zip(tmp_path / "ok.zip")
    new = updates.unpack(str(tmp_path / "ok.zip"), str(tmp_path / "new"), "windows", "v1.1.0")
    assert new == str(tmp_path / "new" / "DSiRPC") and updates.download_version(new) == "v1.1.0"
    with pytest.raises(updates.UpdateError, match="isn't v1.2.0"):
        updates.unpack(str(tmp_path / "ok.zip"), str(tmp_path / "new"), "windows", "v1.2.0")
    (tmp_path / "junk.zip").write_bytes(b"not a zip")
    with pytest.raises(updates.UpdateError, match="unpacked"):
        updates.unpack(str(tmp_path / "junk.zip"), str(tmp_path / "new"), "windows", "v1.1.0")


def test_the_apps_version(tmp_path):
    import plistlib
    app = tmp_path / "DSiRPC.app"
    (app / "Contents").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleName": "DSiRPC", "DSiRPCVersion": "v1.1.0"}, f)
    assert updates.app_version(str(app)) == "v1.1.0"
    assert updates.app_version(str(tmp_path)) is None
    assert updates.mac_app_path(str(app / "Contents" / "MacOS" / "DSiRPC")) == str(app)
    assert updates.mac_app_path("/usr/bin/python3") is None


# -- the Windows step ---------------------------------------------------------------

def write(root, files):
    for name, data in files.items():
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)


def tree(root):
    out = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as f:
                out[os.path.relpath(path, root).replace(os.sep, "/")] = f.read()
    return out


OLD = {"dsirpc.py": "old", "version.txt": "DSiRPC v1.0.0", "DSiRPC.bat": "old bat",
       "python/pythonw.exe": "old", "python/Lib/site-packages/gone/__init__.py": "an old package",
       "core/hub.py": "old", "app/tray.py": "old", "SD card/DSiRPC/dsirpc-launcher.nds": "old nds",
       "ra/README.md": "old readme", "Assets/Consoles/DSi.png": "old picture", "launcher/audio/bright.xm": "old"}
MINE = {"dsirpc.cfg": "my settings", "ra/cache/playtime.json": "my playtimes", "ra/sets/CPUE.json": "a set",
        "logs/dsirpc.log": "my log", "saves/Pokemon Black/live.sav": "my save",
        "Assets/Sprites/pikachu.png": "downloaded"}
NEW = {"dsirpc.py": "new", "version.txt": "DSiRPC v1.1.0", "DSiRPC.bat": "new bat", "defaults.cfg": "new",
       "python/pythonw.exe": "new", "python/Lib/site-packages/pygame/__init__.py": "new package",
       "core/hub.py": "new", "core/updates_new.py": "new", "app/tray.py": "new",
       "SD card/DSiRPC/dsirpc-launcher.nds": "new nds", "ra/README.md": "new readme",
       "Assets/Consoles/DSi.png": "new picture", "launcher/audio/bright.xm": "new"}


def test_the_windows_step_swaps_only_the_programs_files(tmp_path):
    install, new = str(tmp_path / "DSiRPC"), str(tmp_path / "update" / "new" / "DSiRPC")
    write(install, {**OLD, **MINE})
    write(new, NEW)
    assert update_apply.apply(new, install, log=print)
    # The program is the new one, through and through: an old package isn't
    # mixed in with the new Python's
    assert tree(install) == {**NEW, **MINE}
    assert not any(name.endswith(".old") for name in os.listdir(install))


def test_the_windows_step_puts_it_all_back(tmp_path, monkeypatch):
    install, new = str(tmp_path / "DSiRPC"), str(tmp_path / "update" / "new" / "DSiRPC")
    write(install, {**OLD, **MINE})
    write(new, NEW)
    real = update_apply.shutil.copytree

    def copytree(src, dst, *a, **k):
        if os.path.basename(src) == "python":      # the disk filled up, say
            raise OSError(28, "No space left on device")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(update_apply.shutil, "copytree", copytree)
    lines = []
    assert not update_apply.apply(new, install, log=lines.append)
    assert "the old version goes back" in lines[0]
    # All of it as it was, the new release's pictures and songs included
    # (they only go in once the program has)
    assert tree(install) == {**OLD, **MINE}
    assert not any(name.endswith(".old") for name in os.listdir(install))


def test_the_windows_steps_command(tmp_path):
    install, new = str(tmp_path / "DSiRPC"), str(tmp_path / "new" / "DSiRPC")
    write(install, {**OLD, **MINE})
    write(new, NEW)
    log = tmp_path / "update.log"
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()                                     # DSiRPC, already quit
    script = os.path.join(os.path.dirname(update_apply.__file__), "update_apply.py")
    r = subprocess.run([sys.executable, script, "--pid", str(done.pid), "--new", new, "--install", install,
                        "--log", str(log)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert tree(install) == {**NEW, **MINE} and "Updated from" in log.read_text()


# -- the macOS script ---------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "win32", reason="a shell script")
def test_the_mac_script_swaps_the_app(tmp_path):
    app, new = tmp_path / "Applications" / "DSiRPC.app", tmp_path / "update" / "new" / "DSiRPC" / "DSiRPC.app"
    write(str(app), {"Contents/Info.plist": "old"})
    write(str(new), {"Contents/Info.plist": "new"})
    log = tmp_path / "update.log"
    done = subprocess.Popen(["true"])
    done.wait()
    script = tmp_path / "update.sh"
    script.write_text(updates.mac_script(str(app), str(new), done.pid, str(log), opener="echo opened"))
    r = subprocess.run(["/bin/sh", str(script)], capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == f"opened {app}"
    assert tree(str(app)) == {"Contents/Info.plist": "new"} and not new.exists()
    assert not (tmp_path / "Applications" / "DSiRPC.app.old").exists() and "Updated from" in log.read_text()

    # The new app isn't there (an update gone wrong): the old one stays, and opens
    r = subprocess.run(["/bin/sh", str(script)], capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == f"opened {app}" and tree(str(app)) == {"Contents/Info.plist": "new"}
    assert "not updated" in log.read_text().splitlines()[-1]


# -- the tray's side ----------------------------------------------------------------

class Tray:
    """What the tray gives the updater, recorded; asked questions get answers"""

    def __init__(self, answers=()):
        self.answers, self.asked, self.shown, self.notes, self.pages, self.quit = list(answers), [], [], [], [], 0

    def updater(self, current, check=True, kind="windows"):
        cfg = type("Cfg", (), {"check_updates": check})()
        u = updates.Updater(cfg, lambda body, title: self.notes.append(body), self.ask, self.shown.append,
                            self.pages.append, self.quit_app, lambda: None)
        u.current, u.kind = current, kind
        return u

    def ask(self, text):
        self.asked.append(text)
        return self.answers.pop(0) if self.answers else False

    def quit_app(self):
        self.quit += 1


@pytest.fixture
def latest(monkeypatch):
    """The latest release GitHub answers with (set .tag)"""
    state = {"tag": "v1.1.0"}
    monkeypatch.setattr(updates, "fetch_latest", lambda kind: updates.Release(github(state["tag"]), kind))
    return state


def test_a_new_release_is_said_once(latest):
    t = Tray()
    u = t.updater("v1.0.0")
    assert u.label() == "Check for updates..."
    u.check(manual=False)
    u.check(manual=False)
    assert len(t.notes) == 1 and "v1.1.0 is out" in t.notes[0] and t.asked == []
    assert u.label() == "Update to v1.1.0..."


def test_up_to_date_or_a_dev_build(latest):
    t = Tray()
    t.updater("v1.1.0").check(manual=True)
    assert t.shown == ["DSiRPC is up to date (v1.1.0)."]
    t = Tray(answers=[True])
    u = t.updater("dev-abc1234")
    u.check(manual=True)        # never replaced by a release: the page is offered
    assert "doesn't update itself" in t.asked[0] and t.pages == [github("v1.1.0")["html_url"]]
    assert u.label() == "Check for updates..." and t.notes == []


def test_the_update_asks_then_goes(latest, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(updates, "UPDATE_DIR", str(tmp_path / "update"))
    monkeypatch.setattr(updates, "cant_replace", lambda kind: None)
    monkeypatch.setattr(updates, "download", lambda asset, folder, progress: calls.append(("download", asset["name"]))
                        or progress(1, 1) or os.path.join(folder, asset["name"]))
    monkeypatch.setattr(updates, "unpack", lambda path, folder, kind, tag: calls.append(("unpack", tag)) or "new")
    monkeypatch.setattr(updates, "start_apply", lambda kind, new, pid: calls.append(("apply", new, pid)))

    t = Tray(answers=[False])
    u = t.updater("v1.0.0")
    u.check(manual=True)                            # asked, and not now
    assert "Update now?" in t.asked[0] and calls == [] and t.quit == 0

    t = Tray(answers=[True])
    u = t.updater("v1.0.0")
    u.check(manual=True)
    assert calls == [("download", "DSiRPC-v1.1.0-windows.zip"), ("unpack", "v1.1.0"), ("apply", "new", os.getpid())]
    assert t.quit == 1 and u.state == "installing"


def test_it_says_when_it_cant_update_itself(latest, monkeypatch):
    monkeypatch.setattr(updates, "cant_replace", lambda kind: "it can't write to C:\\Program Files\\DSiRPC")
    t = Tray(answers=[True])
    u = t.updater("v1.0.0")
    u.check(manual=True)
    assert "can't write to" in t.asked[0] and t.pages and t.quit == 0

    monkeypatch.setattr(updates, "cant_replace", lambda kind: None)
    monkeypatch.setattr(updates, "download", lambda *a: (_ for _ in ()).throw(updates.UpdateError("the download "
                                                                                                   "came out damaged")))
    t = Tray(answers=[True, False])
    u = t.updater("v1.0.0")
    u.check(manual=True)
    assert "came out damaged" in t.asked[1] and t.quit == 0 and u.state == "idle"


def test_no_quiet_checks_for_a_dev_build(latest, monkeypatch):
    monkeypatch.setattr(updates, "FIRST_CHECK_S", 0)
    monkeypatch.setattr(updates, "clean_up", lambda: None)
    t = Tray()
    u = t.updater("dev-abc1234")
    u._auto()                                       # returns at once: nothing to look for
    assert u.release is None and t.notes == []


def test_check_updates_setting(tmp_path):
    from utils import config
    path = tmp_path / "dsirpc.cfg"
    cfg = config.Config(str(path))
    assert cfg.check_updates
    cfg.check_updates = False
    cfg.save()
    assert "check_updates: no" in path.read_text() and not config.Config(str(path)).check_updates
