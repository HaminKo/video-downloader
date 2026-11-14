"""Build the app as .exe files and its Setup.exe, from the project folder
with the .venv active:

    python installer/build.py

It updates yt-dlp first (YouTube changes often, and the built app can't
update it by itself; --no-update skips this), makes the icon from the
window's PNGs, runs PyInstaller (installer/video-downloader.spec), adds the
Chrome extension's folder and the helper's manifest (host.json) next to the
.exe files, and makes the installer with Inno Setup (installer/setup.iss).
The app ends up in dist/Video Downloader/, its installer in
dist/Video Downloader Setup.exe; build/ holds PyInstaller's work files.
"""

import argparse
import contextlib
import shutil
import subprocess
import sys
import winreg
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
SETUP = DIST / f"{APP_NAME} Setup.exe"  # setup.iss's OutputBaseFilename

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
    megabytes = folder_size(app) / 1_000_000
    print(f"Built {app / APP_EXE} ({megabytes:.0f} MB in all)")
    run(str(compiler), "/Q", str(SETUP_SCRIPT))  # /Q: only errors
    megabytes = SETUP.stat().st_size / 1_000_000
    print(f"Built {SETUP} ({megabytes:.0f} MB); run it to install the app")


if __name__ == "__main__":
    main()
