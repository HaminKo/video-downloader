"""The built app's yt-dlp updater (ytdlp_update.py). A web server on this PC
stands in for yt-dlp's GitHub and a tiny fake yt-dlp for its release, so the
tests never touch the internet. The built app is faked as in test_places.py
(sys.frozen, and sys.executable in a temporary folder).

use_newest() runs in a Python of its own each time: it takes yt-dlp out of
sys.modules when a copy fails, which here would leave the other tests with a
second yt-dlp."""

import _winapi
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.client import HTTPMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yt_dlp
import yt_dlp.cookies

from video_downloader import places, ytdlp_update
from video_downloader.ytdlp_update import Notes, read_notes, write_notes

BUNDLED = "2026.10.26"  # the bundled yt-dlp's version in check()'s tests
NEWER = "2099.01.01"

# A tiny yt-dlp: what the app's downloader.py imports from it, and the
# zipapp's other parts.
FAKE_YTDLP = {
    "__main__.py": "import yt_dlp\n",
    "yt_dlp/__init__.py": "",
    "yt_dlp/cookies.py": "class CookieLoadError(Exception):\n    pass\n",
    "yt_dlp/utils.py": "class DownloadCancelled(Exception):\n    pass\n",
    "yt_dlp_ejs/__init__.py": "",
}


def zipapp(files: dict[str, str]) -> bytes:
    """A zipapp as yt-dlp's releases have it: a #! line, then a zip."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, text in files.items():
            zipped.writestr(name, text)
    return b"#!/usr/bin/env python3\n" + archive.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeGitHub:
    """yt-dlp's GitHub on this PC: the files it serves by path, the paths
    asked for, and the paths whose answer stops halfway (a cut connection)."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.asked: list[str] = []
        self.cut: set[str] = set()

    def release(
        self, version: str, files: dict[str, str] | None = None, sums: str = ""
    ) -> None:
        """Make `version` the newest release, with a zipapp of these files
        (FAKE_YTDLP's by default) and this SHA2-256SUMS (the right one by
        default)."""
        app = zipapp(FAKE_YTDLP if files is None else files)
        sums = sums or f"{sha256(b'other')}  yt-dlp.exe\n{sha256(app)}  yt-dlp\n"
        self.files["/latest"] = json.dumps({"tag_name": version}).encode()
        self.files[f"/download/{version}/yt-dlp"] = app
        self.files[f"/download/{version}/SHA2-256SUMS"] = sums.encode()


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGitHub]:
    """A fake GitHub the updater asks instead of the real one."""
    fake = FakeGitHub()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            fake.asked.append(self.path)
            body = fake.files.get(self.path)
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.path in fake.cut:
                body = body[: len(body) // 2]  # then the connection closes
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    # A short poll interval makes shutdown() quick (the default waits 0.5 s).
    threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(ytdlp_update, "LATEST", f"{base}/latest")
    download = f"{base}/download/{{version}}/{{name}}"
    monkeypatch.setattr(ytdlp_update, "DOWNLOAD", download)
    try:
        yield fake
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Run as the built app in a temporary folder, with BUNDLED as its
    bundled yt-dlp and no copy in use; the copies' folder (not made yet)."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / places.APP_EXE))
    monkeypatch.setattr(ytdlp_update, "bundled_version", lambda: BUNDLED)
    monkeypatch.setattr(ytdlp_update, "in_use", None)
    return places.ytdlp_folder()


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def test_a_newer_release_is_ready_for_the_next_start(
    github: FakeGitHub, folder: Path
) -> None:
    github.release(NEWER)
    assert ytdlp_update.check() == NEWER
    assert names(folder) == [NEWER, "update.json"], "no .partial left"
    copy = folder / NEWER
    sources = sorted(copy.rglob("*.py"))
    unpacked = [source.relative_to(copy).as_posix() for source in sources]
    assert sorted(unpacked) == sorted(FAKE_YTDLP)
    for source in sources:  # compiled, so it starts as fast as the bundled one
        assert Path(importlib.util.cache_from_source(str(source))).is_file()
    assert github.asked == [
        "/latest",
        f"/download/{NEWER}/SHA2-256SUMS",
        f"/download/{NEWER}/yt-dlp",
    ]
    notes = read_notes(folder)
    assert (notes.failed, notes.error) == ([], None)
    assert notes.checked and datetime.now(UTC) - notes.checked < timedelta(minutes=1)


@pytest.mark.parametrize("fault", ["wrong checksum", "cut off", "no checksum"])
def test_a_broken_download_is_not_kept(
    github: FakeGitHub, folder: Path, fault: str
) -> None:
    if fault == "wrong checksum":
        github.release(NEWER, sums=f"{sha256(b'other')}  yt-dlp\n")
    elif fault == "cut off":
        github.release(NEWER)
        github.cut.add(f"/download/{NEWER}/yt-dlp")
    else:
        github.release(NEWER, sums=f"{sha256(b'other')}  yt-dlp.exe\n")
    assert ytdlp_update.check() is None
    assert names(folder) == ["update.json"], "no copy, finished or not"
    notes = read_notes(folder)
    assert notes.error, "why, to look into"
    assert notes.failed == [], "tried again tomorrow"
    assert notes.checked, "GitHub answered"


def test_asks_github_at_most_once_a_day(github: FakeGitHub, folder: Path) -> None:
    github.release(BUNDLED)  # nothing newer
    assert ytdlp_update.check() is None
    assert ytdlp_update.check() is None
    assert github.asked == ["/latest"], "the second start asks nothing"
    notes = read_notes(folder)
    assert notes.checked
    notes.checked -= timedelta(hours=25)
    write_notes(folder, notes)
    github.release(NEWER)
    assert ytdlp_update.check() == NEWER, "a day later"


def test_a_start_without_internet_asks_again_at_the_next(
    github: FakeGitHub, folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline(link: str, headers: dict[str, str] | None = None) -> bytes:
        raise urllib.error.URLError("no internet")

    online = ytdlp_update.fetch
    monkeypatch.setattr(ytdlp_update, "fetch", offline)
    assert ytdlp_update.check() is None
    notes = read_notes(folder)
    assert notes.checked is None
    assert notes.error == "URLError: <urlopen error no internet>"
    monkeypatch.setattr(ytdlp_update, "fetch", online)
    github.release(NEWER)
    assert ytdlp_update.check() == NEWER
    assert read_notes(folder).error is None


@pytest.mark.parametrize("why", ["the bundled one", "downloaded already", "failed"])
def test_downloads_only_a_version_it_can_use(
    github: FakeGitHub, folder: Path, why: str
) -> None:
    github.release(BUNDLED if why == "the bundled one" else NEWER)
    if why == "downloaded already":
        (folder / NEWER).mkdir(parents=True)
    elif why == "failed":
        write_notes(folder, Notes(failed=[NEWER]))
    assert ytdlp_update.check() is None
    assert github.asked == ["/latest"]


def test_a_release_that_does_not_compile_is_never_downloaded_again(
    github: FakeGitHub, folder: Path
) -> None:
    github.release(NEWER, FAKE_YTDLP | {"yt_dlp/new.py": "match = (\n"})
    assert ytdlp_update.check() is None
    assert names(folder) == ["update.json"], "no copy, finished or not"
    notes = read_notes(folder)
    assert notes.failed == [NEWER]
    assert notes.error and notes.error.startswith(f"{NEWER}: ")
    assert notes.checked
    notes.checked -= timedelta(days=2)
    write_notes(folder, notes)
    github.asked.clear()
    assert ytdlp_update.check() is None
    assert github.asked == ["/latest"]


def test_clean_up_keeps_the_copy_in_use_and_the_newest(
    github: FakeGitHub, folder: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in [
        "2099.01.01",  # in use
        "2099.02.01",  # older than the newest, not in use
        "2099.03.01",  # the newest usable one, for the next start
        "2099.04.01",  # failed
        "2020.01.01",  # older than the bundled yt-dlp
        "2099.05.01.partial",  # unfinished
        "notes",  # not named like a version
    ]:
        (folder / name / "yt_dlp").mkdir(parents=True)
    (folder / "2098.01.01").write_text("a file named like a version")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("not the updater's")
    _winapi.CreateJunction(str(outside), str(folder / "2099.01.15"))
    monkeypatch.setattr(ytdlp_update, "in_use", "2099.01.01")
    write_notes(folder, Notes(checked=datetime.now(UTC), failed=["2099.04.01"]))
    assert ytdlp_update.check() is None
    assert github.asked == [], "not due"
    assert names(folder) == [
        "2098.01.01",
        "2099.01.01",
        "2099.01.15",
        "2099.03.01",
        "notes",
        "update.json",
    ]
    assert (outside / "keep.txt").is_file(), "a link isn't followed"


def test_from_the_project_nothing_happens(github: FakeGitHub) -> None:
    github.release(NEWER)
    path = sys.path.copy()
    ytdlp_update.use_newest()
    assert ytdlp_update.check() is None
    assert (sys.path, ytdlp_update.in_use) == (path, None)
    assert github.asked == []
    assert not places.ytdlp_folder().exists()


def test_a_redirect_from_https_goes_only_to_https() -> None:
    handler = ytdlp_update.HttpsOnly()
    asked = urllib.request.Request(
        "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
    )
    to = "https://release-assets.githubusercontent.com/yt-dlp"
    followed = handler.redirect_request(
        asked, io.BytesIO(), 302, "Found", HTTPMessage(), to
    )
    assert followed is not None and followed.full_url == to
    with pytest.raises(ValueError, match="redirected to http:"):
        handler.redirect_request(
            asked, io.BytesIO(), 302, "Found", HTTPMessage(), "http://example.com/x"
        )
    redirects = [
        type(handler)
        for handler in vars(ytdlp_update.OPENER)["handlers"]  # not in its types
        if isinstance(handler, urllib.request.HTTPRedirectHandler)
    ]
    assert redirects == [ytdlp_update.HttpsOnly], "the one fetch() uses"


def test_a_copy_windows_holds_on_to_is_left_whole(
    github: FakeGitHub, folder: Path
) -> None:
    """An older copy with a file open (an antivirus program reading it, say)
    can't be renamed, so it stays as it is, complete, until the next start;
    deleting it bit by bit could leave a copy with files missing."""
    for name in ["2099.01.01", "2099.02.01"]:
        write_copy(folder / name, FAKE_YTDLP)
    write_notes(folder, Notes(checked=datetime.now(UTC)))  # not due
    older = folder / "2099.01.01"
    with (older / "yt_dlp" / "utils.py").open():
        assert ytdlp_update.check() is None
    assert names(folder) == ["2099.01.01", "2099.02.01", "update.json"]
    left = sorted(path.relative_to(older).as_posix() for path in older.rglob("*.py"))
    assert left == sorted(FAKE_YTDLP)
    assert ytdlp_update.check() is None
    assert names(folder) == ["2099.02.01", "update.json"], "once let go of"
    assert github.asked == []


# The built app's start (installer/start_app.py) up to importing downloader.py,
# in a Python of its own, with the project's yt-dlp as the bundled one; what
# it loaded.
START = """\
import json, sys
sys.frozen = True
sys.executable = sys.argv[1]
from video_downloader import ytdlp_update
ytdlp_update.use_newest()
from video_downloader import downloader
print(json.dumps({
    "in use": ytdlp_update.in_use,
    "yt_dlp": sys.modules["yt_dlp"].__file__,
    "CookieLoadError": sys.modules[downloader.CookieLoadError.__module__].__file__,
}))
"""


def start(app: Path) -> dict[str, str | None]:
    """Start the built app (faked) in the folder `app`: what it loaded."""
    done = subprocess.run(
        [sys.executable, "-c", START, str(app / places.APP_EXE)],
        capture_output=True,
        text=True,
        cwd=app,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def write_copy(copy: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = copy / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def loaded_from(copy: Path, version: str) -> dict[str, str | None]:
    return {
        "in use": version,
        "yt_dlp": str(copy / "yt_dlp" / "__init__.py"),
        "CookieLoadError": str(copy / "yt_dlp" / "cookies.py"),
    }


def test_the_newest_copy_is_loaded(tmp_path: Path) -> None:
    folder = tmp_path / "yt-dlp"
    write_copy(folder / "2099.01.01", FAKE_YTDLP)
    write_copy(folder / "2099.02.01", FAKE_YTDLP)
    assert start(tmp_path) == loaded_from(folder / "2099.02.01", "2099.02.01")


def test_a_copy_that_fails_gives_way_to_the_next(tmp_path: Path) -> None:
    folder = tmp_path / "yt-dlp"
    write_copy(folder / "2099.01.01", FAKE_YTDLP)
    # A newer copy without a module the app imports from yt-dlp (as if
    # renamed), which leaves a mark each time it is imported.
    mark_it = "open(__file__ + '.mark', 'a').close()\n"
    broken = FAKE_YTDLP | {"yt_dlp/__init__.py": mark_it}
    del broken["yt_dlp/utils.py"]
    write_copy(folder / "2099.02.01", broken)
    mark = folder / "2099.02.01" / "yt_dlp" / "__init__.py.mark"
    assert start(tmp_path) == loaded_from(folder / "2099.01.01", "2099.01.01")
    assert read_notes(folder).failed == ["2099.02.01"]
    assert mark.is_file(), "tried first"
    mark.unlink()
    assert start(tmp_path) == loaded_from(folder / "2099.01.01", "2099.01.01")
    assert not mark.exists(), "not tried again"


def test_with_no_copy_to_use_the_bundled_yt_dlp_loads(tmp_path: Path) -> None:
    folder = tmp_path / "yt-dlp"
    write_copy(folder / "2099.03.01.partial", FAKE_YTDLP)  # unfinished
    write_copy(folder / "2020.01.01", FAKE_YTDLP)  # older than the bundled one
    write_copy(folder / "2099.02.01", {"yt_dlp/__init__.py": "raise ImportError\n"})
    assert start(tmp_path) == {
        "in use": None,
        "yt_dlp": yt_dlp.__file__,
        "CookieLoadError": yt_dlp.cookies.__file__,
    }
    assert read_notes(folder).failed == ["2099.02.01"]
