"""Build the app as .exe files and its Setup.exe, from the project folder
with the .venv active:

    python installer/build.py

It updates yt-dlp first (YouTube changes often; the built app then fetches
newer releases by itself, ytdlp_update.py; --no-update skips this), makes
the icon from the window's PNGs, runs PyInstaller
(installer/video-downloader.spec), adds the
Chrome extension's folder, the helper's manifest (host.json) and the
licenses (the app's own and those of what it includes) next to the .exe
files, and makes the installer with Inno Setup (installer/setup.iss), whose
version is pyproject.toml's.
The app ends up in dist/Video Downloader/, its installer in
dist/Video Downloader Setup.exe; build/ holds PyInstaller's work files.
"""

import argparse
import contextlib
import importlib.metadata
import platform
import re
import shutil
import subprocess
import sys
import tomllib
import winreg
from collections.abc import Iterable
from pathlib import Path

from PIL import Image

# Only places and browser, never the app's other modules: they load yt-dlp,
# whose compiled parts pip couldn't replace while this script has them open
# (tests/test_installer.py checks this).
from video_downloader import browser
from video_downloader.places import APP_EXE, APP_NAME, HELPER_EXE

PROJECT = Path(__file__).resolve().parents[1]
EXTENSION = PROJECT / "extension"
SPEC = PROJECT / "installer" / "video-downloader.spec"
SETUP_SCRIPT = PROJECT / "installer" / "setup.iss"
BUILD = PROJECT / "build"
DIST = PROJECT / "dist"
ICON = BUILD / "icon.ico"  # the spec and setup.iss read it from here
MODULES = BUILD / "modules.txt"  # the spec writes it
SETUP = DIST / f"{APP_NAME} Setup.exe"  # setup.iss's OutputBaseFilename
PYPROJECT = PROJECT / "pyproject.toml"
LICENSE = PROJECT / "LICENSE"
THIRD_PARTY = "THIRD-PARTY-LICENSES.txt"

# A library's license files, in its .dist-info folder (also in licenses\
# there, PEP 639): pycryptodomex's license names its AUTHORS file.
LICENSE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)\b", re.IGNORECASE)
RULE = "=" * 78

# Inno Setup's own entry in Settings > Apps, for this user or all users (for
# all users in the registry's 32-bit part when its Setup was 32-bit).
INNO_SETUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"

NO_INNO_SETUP = """\
Inno Setup is missing (it makes the Setup.exe). Install it, then run this
again:
    winget install --id JRSoftware.InnoSetup -e"""


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def inno_setup() -> Path | None:
    """Inno Setup's compiler, ISCC.exe: in the folder Inno Setup's own entry
    names (it can be installed anywhere, and isn't on PATH by itself), else
    on PATH; None when it's in neither."""
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            access = winreg.KEY_READ | view
            with (
                contextlib.suppress(OSError),  # no such entry
                winreg.OpenKey(root, INNO_SETUP_KEY, 0, access) as key,
            ):
                folder, _ = winreg.QueryValueEx(key, "InstallLocation")
                compiler = Path(folder) / "ISCC.exe"
                if compiler.is_file():
                    return compiler
    found = shutil.which("ISCC")
    return Path(found) if found else None


def add_files(app: Path) -> None:
    """What PyInstaller doesn't put into the built app, next to its .exe
    files: the Chrome extension's folder, and the manifest Chrome finds the
    helper by, with the helper's path relative to it, so it holds wherever
    Setup installs the app."""
    shutil.copytree(EXTENSION, app / "extension")
    browser.write_manifest(app, Path(HELPER_EXE))


def app_version() -> str:
    """The app's version, pyproject.toml's (CHANGELOG.md's newest)."""
    with PYPROJECT.open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def bundled_libraries(
    modules: Iterable[str],
) -> list[importlib.metadata.Distribution]:
    """The installed libraries these top-level modules come from, by name.
    The standard library's modules and the app's own come from none."""
    owners = importlib.metadata.packages_distributions()
    names = {name for module in modules for name in owners.get(module, [])}
    names.discard("video-downloader")
    return [
        importlib.metadata.distribution(name) for name in sorted(names, key=str.lower)
    ]


def license_texts(library: importlib.metadata.Distribution) -> list[str]:
    files = sorted(
        file
        for file in library.files or []
        if file.parts[0].endswith(".dist-info") and LICENSE_FILE.match(file.name)
    )
    if not files:
        # A new library yt-dlp needs: look up its license, then list it here.
        raise SystemExit(
            f"{library.name} has no license file in its .dist-info folder, so "
            f"{THIRD_PARTY} can't include it (installer/build.py)."
        )
    return [file.read_text(encoding="utf-8").strip() for file in files]


def third_party_licenses(libraries: list[importlib.metadata.Distribution]) -> str:
    """The text of THIRD-PARTY-LICENSES.txt: the licenses of Python (with
    the parts python.org's build includes), Tcl/Tk (tkinter's) and each
    library, in full."""
    python = Path(sys.base_prefix)
    tk = next(python.glob("tcl/tk*/license.terms"), None)
    if tk is None:
        raise SystemExit(f"Tcl/Tk's license.terms isn't in {python / 'tcl'}.")
    sections = [
        (
            f"Python {platform.python_version()}",
            [(python / "LICENSE.txt").read_text(encoding="utf-8").strip()],
        ),
        (
            f"Tcl/Tk {tk.parent.name.removeprefix('tk')}",
            [tk.read_text(encoding="utf-8").strip()],
        ),
        *(
            (f"{library.name} {library.version}", license_texts(library))
            for library in libraries
        ),
    ]
    parts = [
        f"{APP_NAME} includes the software below, each under its own license.\n"
        "The app's own license is in LICENSE.txt."
    ]
    for title, texts in sections:
        parts.append(f"{RULE}\n{title}\n{RULE}")
        parts.extend(texts)
    return "\n\n".join(parts) + "\n"


def add_licenses(app: Path, modules: Iterable[str]) -> None:
    """The app's own license, and those of what it includes (the modules'
    libraries, Python and Tcl/Tk), next to the .exe files."""
    shutil.copyfile(LICENSE, app / "LICENSE.txt")
    libraries = bundled_libraries(modules)
    (app / THIRD_PARTY).write_text(third_party_licenses(libraries), encoding="utf-8")
    names = ", ".join(library.name for library in libraries)
    print(f"Licenses in {THIRD_PARTY}: Python, Tcl/Tk, {names}")


def make_icon(path: Path) -> None:
    """The .exe files' icon: the window's PNGs (extension/icons, named by
    their size), one per size, in one .ico: each size as drawn, not scaled
    down from the biggest."""
    pngs = sorted((EXTENSION / "icons").glob("*.png"), key=lambda png: int(png.stem))
    images = [Image.open(png) for png in pngs]
    path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        path, sizes=[image.size for image in images], append_images=images[:-1]
    )


def folder_size(folder: Path) -> int:
    return sum(file.stat().st_size for file in folder.rglob("*") if file.is_file())


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python installer/build.py",
        description="Build the app as .exe files and its Setup.exe, into dist/.",
    )
    parser.add_argument(
        "--no-update", action="store_true", help="don't update yt-dlp first"
    )
    options = parser.parse_args(arguments)
    compiler = inno_setup()  # before the slow part, which would be for nothing
    if compiler is None:
        raise SystemExit(NO_INNO_SETUP)
    if not options.no_update:
        run(sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]")
    make_icon(ICON)
    MODULES.unlink(missing_ok=True)  # never an older build's
    # PyInstaller empties dist/Video Downloader/ first (--noconfirm: without
    # asking).
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--log-level=WARN",
        f"--distpath={DIST}",
        f"--workpath={BUILD / 'pyinstaller'}",
        str(SPEC),
    )
    app = DIST / APP_NAME
    add_files(app)
    add_licenses(app, MODULES.read_text(encoding="utf-8").split())
    megabytes = folder_size(app) / 1_000_000
    print(f"Built {app / APP_EXE} ({megabytes:.0f} MB in all)")
    # /Q: only errors. setup.iss adds the build's date and time to the version.
    run(str(compiler), "/Q", f"/DAppNumber={app_version()}", str(SETUP_SCRIPT))
    megabytes = SETUP.stat().st_size / 1_000_000
    print(f"Built {SETUP} ({megabytes:.0f} MB); run it to install the app")


if __name__ == "__main__":
    main()
