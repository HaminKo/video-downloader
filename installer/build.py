"""Build the app as .exe files, from the project folder with the .venv
active:

    python installer/build.py

It updates yt-dlp first (YouTube changes often, and the built app can't
update it by itself; --no-update skips this), makes the icon from the
window's PNGs, runs PyInstaller (installer/video-downloader.spec) and copies
the Chrome extension's folder next to the .exe files. The app ends up in
dist/Video Downloader/; build/ holds PyInstaller's work files.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

# Only places, never the app's other modules: they load yt-dlp, whose
# compiled parts pip couldn't replace while this script has them open.
from video_downloader.places import APP_EXE, APP_NAME

PROJECT = Path(__file__).resolve().parents[1]
EXTENSION = PROJECT / "extension"
SPEC = PROJECT / "installer" / "video-downloader.spec"
BUILD = PROJECT / "build"
DIST = PROJECT / "dist"
ICON = BUILD / "icon.ico"  # the spec reads it from here


def run(*command: str) -> None:
    subprocess.run(command, check=True)


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
        description="Build the app as .exe files, into dist/.",
    )
    parser.add_argument(
        "--no-update", action="store_true", help="don't update yt-dlp first"
    )
    options = parser.parse_args(arguments)
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
    shutil.copytree(EXTENSION, app / "extension")
    megabytes = folder_size(app) / 1_000_000
    print(f"Built {app / APP_EXE} ({megabytes:.0f} MB in all)")


if __name__ == "__main__":
    main()
