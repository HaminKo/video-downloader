"""Set up the Chrome button (extension/) on this PC, or take it away:

    python -m video_downloader.browser install
    python -m video_downloader.browser uninstall

install writes the helper Chrome starts for each click (host.bat, which runs
host.py with this Python) and its manifest (host.json) into the app's own
folder, and points Chrome's registry key at the manifest. Only the extension
with EXTENSION_ID may start the helper. The extension itself is loaded by
hand in chrome://extensions ("Load unpacked"; docs/using.md).
"""

import argparse
import contextlib
import json
import sys
import winreg
from pathlib import Path

from video_downloader.downloader import DATA_FOLDER

# Chrome's name for the helper; extension/background.js uses it too.
HOST_NAME = "video_downloader"

# The extension's ID, fixed by the "key" in extension/manifest.json (a test
# checks that they match). Without a key, the ID would come from the folder
# the extension is loaded from.
EXTENSION_ID = "ihppdkclbgnohioighdlmologiiggoah"

# Where Chrome looks up a helper's manifest (under HKEY_CURRENT_USER).
KEY = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"

# The extension's folder, for "Load unpacked": next to src/ in the project.
EXTENSION_FOLDER = Path(__file__).resolve().parents[2] / "extension"

BAT = "host.bat"
MANIFEST = "host.json"

INSTALLED = """\
The Chrome button's helper is installed in {folder}
It runs this Python: {python}

If the button isn't in Chrome yet:
1. Open chrome://extensions and turn on "Developer mode" (top right).
2. Click "Load unpacked" and choose this folder: {extension}
3. The extension's ID should be {id}
4. Pin it: the puzzle piece in Chrome's toolbar, then the pin next to
   Video Downloader.

Run this again after moving the project or making the .venv anew."""

UNINSTALLED = """\
The Chrome button's helper is removed. To remove the button too: open
chrome://extensions and click Remove under Video Downloader."""


def bat_text(python: Path) -> str:
    """host.bat: run the helper with this Python. The "@" keeps cmd.exe from
    echoing the line onto stdout, which Chrome reads as the reply."""
    return f'@"{python}" -m video_downloader.host\n'


def host_manifest(bat: Path) -> dict[str, object]:
    return {
        "name": HOST_NAME,
        "description": "Video Downloader: gets links from the Chrome button",
        "path": str(bat),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"],
    }


def write_key(manifest: Path) -> None:
    """Point Chrome's key at the manifest (the key's default value)."""
    winreg.SetValue(winreg.HKEY_CURRENT_USER, KEY, winreg.REG_SZ, str(manifest))


def delete_key() -> None:
    with contextlib.suppress(FileNotFoundError):  # not installed
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY)


def install(folder: Path, python: Path) -> None:
    """Write host.bat and host.json into folder, and Chrome's key."""
    folder.mkdir(parents=True, exist_ok=True)
    bat = folder / BAT
    # cmd.exe reads a .bat in the OEM code page.
    bat.write_text(bat_text(python), encoding="oem")
    manifest = folder / MANIFEST
    text = json.dumps(host_manifest(bat), indent=2)
    manifest.write_text(text + "\n", encoding="utf-8")
    write_key(manifest)


def uninstall(folder: Path) -> None:
    """Remove Chrome's key, host.bat and host.json; nothing else in the
    folder (the sign-in file and the history stay)."""
    delete_key()
    for name in (BAT, MANIFEST):
        (folder / name).unlink(missing_ok=True)


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m video_downloader.browser",
        description="Set up the Chrome button on this PC, or take it away.",
    )
    parser.add_argument("action", choices=["install", "uninstall"])
    if parser.parse_args(arguments).action == "install":
        python = Path(sys.executable)
        install(DATA_FOLDER, python)
        print(
            INSTALLED.format(
                folder=DATA_FOLDER,
                python=python,
                extension=EXTENSION_FOLDER,
                id=EXTENSION_ID,
            )
        )
    else:
        uninstall(DATA_FOLDER)
        print(UNINSTALLED)


if __name__ == "__main__":
    main()
