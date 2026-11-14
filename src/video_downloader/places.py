"""Where the app's parts are: in the project, run with Python, or in the app
built by installer/build.py (PyInstaller, which sets sys.frozen). The built
app is one folder: the two .exe files, PyInstaller's _internal folder, and
the Chrome extension's folder. Imports nothing slow: Chrome's helper
(host.py) uses it at every click.
"""

import sys
from pathlib import Path

# The built app's folder and .exe files (installer/video-downloader.spec).
APP_NAME = "Video Downloader"
APP_EXE = f"{APP_NAME}.exe"  # the window, no console
HELPER_EXE = "chrome-helper.exe"  # Chrome's helper, a console program


def built() -> bool:
    """True in the built app, False when run from the project."""
    return bool(getattr(sys, "frozen", False))


def extension_folder() -> Path:
    """The Chrome extension's folder: next to the .exe files in the built
    app, next to src/ in the project. The window's icon is read from it."""
    if built():
        return Path(sys.executable).parent / "extension"
    return Path(__file__).resolve().parents[2] / "extension"


def app_command() -> list[str]:
    """The command that starts the window, without a console: the built
    app's .exe (next to this one), or the project's pythonw.exe (next to the
    Python running this) with `-m video_downloader`."""
    executable = Path(sys.executable)
    if built():
        return [str(executable.with_name(APP_EXE))]
    return [str(executable.with_name("pythonw.exe")), "-m", "video_downloader"]
