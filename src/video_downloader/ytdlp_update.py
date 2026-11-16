"""The built app keeps yt-dlp current by itself (yt-dlp's own updater refuses
a PyInstaller app: docs/research/yt-dlp-update.md). The copies it downloads
live in places.ytdlp_folder(), one folder per version, with the updater's
notes (NOTES) beside them:

- check(), in a background thread of the window, at most once a day: asks
  yt-dlp's GitHub for its newest stable release, and when that is newer
  than the bundled yt-dlp and every copy, reads the release's _update_spec
  (which names the last release for a Python yt-dlp no longer supports,
  then used instead), downloads the release's zipapp,
  checks it against the release's SHA2-256SUMS, unpacks it into
  VERSION.partial, compiles it and renames the folder to VERSION. Then it
  deletes the copies that won't be used again (clean_up()).
- use_newest(), at the start before the app is imported
  (installer/start_app.py): puts the newest copy first on sys.path and
  imports the app's downloader.py with it. When that fails, it undoes the
  import, writes the version down as failed and tries the next copy, and
  last the bundled yt-dlp.

From the project neither does anything: `pip install -U` updates yt-dlp
there. Whatever goes wrong never stops the app: the bundled yt-dlp stays.
Only the standard library and places: this runs before yt-dlp loads.
"""

import contextlib
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import platform
import py_compile
import re
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.client import HTTPMessage
from pathlib import Path
from typing import IO
from urllib.parse import urlsplit

from video_downloader import places

# yt-dlp's stable releases on GitHub, as yt-dlp's own updater asks for them.
LATEST = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
DOWNLOAD = "https://github.com/yt-dlp/yt-dlp/releases/download/{version}/{name}"
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
ZIPAPP = "yt-dlp"  # the release's Python zipapp: yt_dlp and yt_dlp_ejs
SUMS = "SHA2-256SUMS"  # one line per file: its SHA-256, then its name
SPEC = "_update_spec"  # lock lines: the last release for an old Python
REPOSITORY = "yt-dlp/yt-dlp"  # the stable channel, as lockV2 lines name it
VARIANT = "zip"  # the zipapp, as the lock lines name it
TIMEOUT = 30  # seconds without an answer before a request fails
RENAME_TRIES = 10  # a copy's rename, once complete, RENAME_WAIT seconds apart
RENAME_WAIT = 0.5

EVERY = timedelta(days=1)  # how often to ask GitHub
NOTES = "update.json"  # the updater's notes, in the copies' folder
PARTIAL = ".partial"  # a copy being unpacked and compiled
# Release versions (GitHub's tags) and the copies' folders: 2026.10.26, or
# with a fourth number; pip writes the bundled one as 2026.1.5.
VERSION = re.compile(r"\d{4}\.\d{1,2}\.\d{1,2}(\.\d+)?")
# What a copy must import: the app's module that imports yt-dlp, and with it
# the names it takes from yt-dlp. The import's modules that a failure
# undoes: those, and every module of the zipapp's packages.
CHECK = "video_downloader.downloader"
PACKAGES = ("yt_dlp", "yt_dlp_ejs")

in_use: str | None = None  # the copy use_newest() loaded; None: the bundled


class Broken(Exception):
    """A release that is what yt-dlp published (its checksum matched) but
    doesn't unpack or compile here: never downloaded again."""


@dataclass
class Notes:
    """What the updater keeps between starts, in NOTES."""

    checked: datetime | None = None  # when GitHub last named its newest release
    failed: list[str] = field(default_factory=list)  # versions never to use
    error: str | None = None  # why the last check went wrong, to look into


def parse(version: str) -> tuple[int, ...] | None:
    """A version as numbers, to compare; None when it isn't one."""
    if not VERSION.fullmatch(version):
        return None
    return tuple(int(number) for number in version.split("."))


def bundled_version() -> str | None:
    """The bundled yt-dlp's version, without importing it: from its
    dist-info (the spec's copy_metadata()); None when that's missing."""
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return None


def read_notes(folder: Path) -> Notes:
    """The notes in the folder; as far as they can be read, so a missing or
    broken file gives empty ones."""
    notes = Notes()
    with contextlib.suppress(Exception):
        data = json.loads((folder / NOTES).read_text(encoding="utf-8"))
        notes.failed = [version for version in data["failed"] if parse(version)]
        notes.error = data["error"] if isinstance(data["error"], str) else None
        # A time without a time zone counts as this PC's.
        notes.checked = datetime.fromisoformat(data["checked"]).astimezone(UTC)
    return notes


def write_notes(folder: Path, notes: Notes) -> None:
    """Replace the folder's notes in one step (a new file, renamed), so a
    reader never sees half of them."""
    folder.mkdir(parents=True, exist_ok=True)
    data = {
        "checked": notes.checked.isoformat() if notes.checked else None,
        "failed": notes.failed,
        "error": notes.error,
    }
    new = folder / f"{NOTES}.new"
    new.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(new, folder / NOTES)


def copies(folder: Path) -> list[tuple[tuple[int, ...], str]]:
    """The complete copies in the folder, newest first: each one's version
    as numbers and its folder's name. Only folders named like a version
    (VERSION.partial is unfinished), not links to another place."""
    found = []
    with contextlib.suppress(OSError):  # no folder yet
        for path in folder.iterdir():
            number = parse(path.name)
            if number and path.is_dir() and not is_link(path):
                found.append((number, path.name))
    return sorted(found, reverse=True)


def is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def usable(folder: Path, notes: Notes) -> list[str]:
    """The complete copies newer than the bundled yt-dlp that haven't failed,
    newest first. None when the bundled version is unknown."""
    bundled = parse(bundled_version() or "")
    if bundled is None:
        return []
    return [
        name
        for number, name in copies(folder)
        if number > bundled and name not in notes.failed
    ]


def use_newest() -> None:
    """In the built app, before the app is imported: load yt-dlp from the
    newest copy that imports, else the bundled one."""
    global in_use
    if not places.built():
        return
    folder = places.ytdlp_folder()
    try:
        notes = read_notes(folder)
        versions = usable(folder, notes)
    except Exception:  # never stop the app: the bundled yt-dlp
        return
    for version in versions:
        path = str(folder / version)
        sys.path.insert(0, path)
        try:
            importlib.import_module(CHECK)
        except Exception:
            forget(path)
            notes.failed.append(version)
            with contextlib.suppress(OSError):
                write_notes(folder, notes)
        else:
            in_use = version
            return


def forget(path: str) -> None:
    """Undo a copy's failed import, so the next import looks in the next
    place on sys.path: the copy off sys.path, and the modules the import
    loaded out of sys.modules (docs/research/yt-dlp-update.md)."""
    with contextlib.suppress(ValueError):
        sys.path.remove(path)
    for name in list(sys.modules):
        if name == CHECK or name.partition(".")[0] in PACKAGES:
            del sys.modules[name]
    importlib.invalidate_caches()


def check() -> str | None:
    """In the built app: once a day, download yt-dlp's newest release (for
    this Python: locked()) when it's newer than the bundled yt-dlp and every
    copy that hasn't failed, for the next start; then delete the copies that
    won't be used again. The version just downloaded, else None. Never
    raises: what went wrong goes into the notes."""
    if not places.built():
        return None
    folder = places.ytdlp_folder()
    notes = read_notes(folder)
    ready = None
    now = datetime.now(UTC)
    # Due a day after GitHub last answered, or when the clock went back.
    if notes.checked is None or not (notes.checked <= now < notes.checked + EVERY):
        ready = update(folder, notes)
    with contextlib.suppress(Exception):  # never stop the app
        clean_up(folder, notes)
    return ready


def update(folder: Path, notes: Notes) -> str | None:
    """Ask GitHub for the newest release and, if it is newer() than what is
    here, download it or the last release for this Python (locked()), when
    that is newer too and not a version that failed; its version then, else
    None. The notes are written afterwards."""
    version = None
    try:
        bundled = parse(bundled_version() or "")
        if bundled is None:
            raise LookupError("the bundled yt-dlp's version is unknown")
        version = newest_release()
        notes.checked = datetime.now(UTC)
        notes.error = None
        if not newer(version, bundled, folder, notes):
            return None
        # Also when the newest failed: it may need a newer Python, and its
        # _update_spec may name the last release for this one only now.
        version = locked(version)
        if version in notes.failed or not newer(version, bundled, folder, notes):
            return None
        install(version, folder)
        return version
    except Broken as error:
        if version:
            notes.failed.append(version)
        notes.error = f"{version}: {error}"
    except Exception as error:  # no internet, GitHub, the disk, ...
        notes.error = f"{type(error).__name__}: {error}"
    finally:
        with contextlib.suppress(OSError):
            write_notes(folder, notes)
    return None


class HttpsOnly(urllib.request.HTTPRedirectHandler):
    """Follows a redirect from an HTTPS link only to another HTTPS link, at
    every step, so no part of a download from GitHub goes over plain HTTP."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        schemes = (urlsplit(req.full_url).scheme, urlsplit(newurl).scheme)
        if schemes[0] == "https" and schemes[1] != "https":
            raise ValueError(f"redirected to {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# urlopen()'s handlers, with HttpsOnly in place of the redirect handler.
OPENER = urllib.request.build_opener(HttpsOnly)


def fetch(link: str, headers: dict[str, str] | None = None) -> bytes:
    """A file from the web; raises when it can't be had."""
    request = urllib.request.Request(link, headers=headers or {})
    with OPENER.open(request, timeout=TIMEOUT) as response:
        return response.read()


def newest_release() -> str:
    """The version (tag) of yt-dlp's newest stable release, from GitHub."""
    version = json.loads(fetch(LATEST, API_HEADERS))["tag_name"]
    # It becomes a folder's name and part of a link: digits and dots only.
    if not isinstance(version, str) or parse(version) is None:
        raise ValueError(f"not a version: {version!r}")
    return version


def newer(version: str, bundled: tuple[int, ...], folder: Path, notes: Notes) -> bool:
    """Whether a release is newer than the bundled yt-dlp and every complete
    copy that hasn't failed, as usable() counts them: a failed copy stays on
    disk until clean_up(), after update()."""
    number = parse(version)
    if number is None or number <= bundled:
        return False
    return all(
        copy < number for copy, name in copies(folder) if name not in notes.failed
    )


def locked(version: str) -> str:
    """The release to download instead of `version`, the newest: the last
    one for this Python when the newest's SPEC names one (yt-dlp no longer
    supports it), read as yt-dlp's own updater reads it, else `version`.
    Without a SPEC (a 404) `version` too: yt-dlp's updater would stop, but
    here use_newest()'s import check keeps a release that needs a newer
    Python from being used (docs/research/yt-dlp-update.md). Raises when
    the SPEC can't be had otherwise, as yt-dlp's updater stops then."""
    try:
        spec = fetch(DOWNLOAD.format(version=version, name=SPEC))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return version
        raise
    # GitHub can answer 200 with its error page (yt-dlp issue 17550).
    if b"<!DOCTYPE html>" in spec[:512]:
        raise ValueError(f"{SPEC} {version}: GitHub sent a web page")
    lines = spec.decode("utf-8", "replace").splitlines()
    # lockV2 lines name the channel: when there are any, only those count.
    v2 = any(line.startswith("lockV2 ") for line in lines)
    prefix = f"lockV2 {REPOSITORY} " if v2 else "lock "
    newest = parse(version)
    if newest is None:  # newest_release() checked it already
        raise ValueError(f"not a version: {version!r}")
    system = identifier()
    for line in lines:
        if not line.startswith(prefix):
            continue
        tag, _, pattern = line.removeprefix(prefix).partition(" ")
        number = parse(tag)  # it becomes a folder's name and part of a link
        if number is None or not pattern:
            continue
        try:
            matched = re.match(pattern, system)
        except re.error:  # a pattern Python can't read: as if it weren't there
            continue
        if matched:  # the first match wins, and only ever gives an older one
            return tag if number < newest else version
    return version


def identifier() -> str:
    """What the lock lines are matched against: the variant the app downloads
    and the system as yt-dlp's system_identifier() writes it, without the C
    library (Linux only; on Windows it would read through the whole .exe)."""
    python = platform.python_version()
    build = f"{platform.python_implementation()} {platform.machine()}"
    bits = platform.architecture()[0]
    system = f"{platform.platform()} ({ssl.OPENSSL_VERSION})"
    return f"{VARIANT} Python {python} ({build} {bits}) - {system}"


def install(version: str, folder: Path) -> None:
    """Download the release's zipapp, check it, unpack and compile it into
    VERSION.partial, and rename that to VERSION once it is complete."""
    sums = fetch(DOWNLOAD.format(version=version, name=SUMS))
    zipapp = fetch(DOWNLOAD.format(version=version, name=ZIPAPP))
    if hashlib.sha256(zipapp).hexdigest() != checksum(sums, ZIPAPP):
        raise ValueError(f"{ZIPAPP} {version}: the checksum doesn't match")
    partial = folder / f"{version}{PARTIAL}"
    remove(folder, partial.name)  # left by an app closed while compiling
    partial.mkdir(parents=True, exist_ok=True)  # in case Windows kept some
    try:
        unpack(zipapp, partial)
        rename(partial, folder / version)
    except BaseException:
        remove(folder, partial.name)
        raise


def checksum(sums: bytes, name: str) -> str:
    """The SHA-256 a SHA2-256SUMS file gives for a file name."""
    for line in sums.decode("utf-8", "replace").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line.strip())
        if match and match[2] == name:
            return match[1].lower()
    raise ValueError(f"{SUMS} has no line for {name}")


def unpack(zipapp: bytes, partial: Path) -> None:
    """Unpack the zipapp (a zip after a #! line) and compile its .py files,
    since the built app writes no .pyc files itself: with them the copy
    starts as fast as the bundled yt-dlp (docs/research/yt-dlp-update.md)."""
    try:
        with zipfile.ZipFile(io.BytesIO(zipapp)) as archive:
            archive.extractall(partial)  # keeps every file inside `partial`
        for source in sorted(partial.rglob("*.py")):
            py_compile.compile(str(source), doraise=True)
    except (zipfile.BadZipFile, py_compile.PyCompileError) as error:
        raise Broken(error) from error


def rename(path: Path, target: Path) -> None:
    """Rename a folder, trying again for a few seconds while Windows refuses:
    an antivirus program reading its new files can hold them open."""
    for _ in range(RENAME_TRIES - 1):
        try:
            path.rename(target)
            return
        except PermissionError:
            time.sleep(RENAME_WAIT)
    path.rename(target)


def clean_up(folder: Path, notes: Notes) -> None:
    """Delete the copies that won't be used again: unfinished ones, failed
    ones and older ones, all but the copy in use and the newest usable one,
    which the next start loads."""
    keep = {in_use, *usable(folder, notes)[:1]}
    for path in list(folder.iterdir()):
        if path.name not in keep:
            remove(folder, path.name)


def remove(folder: Path, name: str) -> None:
    """Delete a copy, or an unfinished one, as far as Windows lets it: only a
    folder directly inside the copies' folder and named like a version (or
    VERSION.partial), never a link to another place. A copy becomes
    VERSION.partial first, so files Windows won't let go of never look like
    a complete copy; when it can't be renamed, it stays as it is."""
    path = folder / name
    version = name.removesuffix(PARTIAL)
    if parse(version) is None or is_link(path) or not path.is_dir():
        return
    if path.resolve().parent != folder.resolve():
        return
    if name == version:
        partial = folder / f"{version}{PARTIAL}"
        remove(folder, partial.name)
        try:
            path.rename(partial)
        except OSError:
            return
        path = partial
    shutil.rmtree(path, ignore_errors=True)
