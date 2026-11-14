"""The Chrome button's popup (extension/popup.html) in headless Chrome, with
Chrome's extension functions faked (fake_chrome.js): shared by the popup's GUI
test and the screenshots.

The page is a copy of popup.html in a temp folder with the fake loaded before
popup.js, opened as a plain file, so nothing reaches the helper, the app or
the internet. Chrome runs with a profile of its own in that folder, so the
user's Chrome, its sign-ins and its extensions are never touched. Virtual
time (`--virtual-time-budget`) runs the page's timers at once: the popup's
1.5 s before closing takes no real time."""

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NotRequired, TypedDict
from urllib.parse import quote

from video_downloader.browser import EXTENSION_FOLDER

FAKE = Path(__file__).with_name("fake_chrome.js")
POPUP_SCRIPT = '<script src="popup.js"></script>'

# How long the page runs, in virtual milliseconds: after the fake's report.
RUN_FOR = 5000


class Case(TypedDict):
    """What Chrome gives the popup, and what is clicked in it."""

    url: str | None  # the tab's link; None: Chrome gives none (New Tab)
    stored: NotRequired[Mapping[str, object]]  # what chrome.storage.local holds
    reply: NotRequired[Mapping[str, object]]  # the helper's answer
    error: NotRequired[str]  # sendNativeMessage fails with this instead
    reply_after: NotRequired[int]  # ms before the answer or the failure
    clicks: NotRequired[list[str]]  # CSS selectors, clicked once it has started
    read_at: NotRequired[int]  # ms after the page loaded; 2500 if not given


def chrome() -> Path:
    """This PC's Chrome."""
    for folder in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if folder in os.environ:
            path = Path(os.environ[folder], "Google/Chrome/Application/chrome.exe")
            if path.is_file():
                return path
    raise FileNotFoundError("Chrome isn't installed: the popup runs in it.")


def run_chrome(case: Case, *options: str) -> subprocess.CompletedProcess[str]:
    """Open the popup with the case in headless Chrome; what Chrome printed
    (with --dump-dom: the page at the end, on stdout)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        folder = Path(temp)
        page = EXTENSION_FOLDER.joinpath("popup.html").read_text(encoding="utf-8")
        assert POPUP_SCRIPT in page, "popup.html no longer loads popup.js"
        fake = f'<script src="{FAKE.name}"></script>\n'
        page = page.replace(POPUP_SCRIPT, fake + POPUP_SCRIPT)
        (folder / "popup.html").write_text(page, encoding="utf-8")
        shutil.copy(EXTENSION_FOLDER / "popup.js", folder)
        shutil.copy(FAKE, folder)
        url = (folder / "popup.html").as_uri() + "?" + quote(json.dumps(case))
        result = subprocess.run(
            [
                chrome(),
                "--headless",
                f"--user-data-dir={folder / 'profile'}",
                "--no-first-run",
                f"--virtual-time-budget={RUN_FOR}",
                *options,
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    return result


def run(case: Case) -> dict[str, Any]:
    """What the popup shows and did at the end (fake_chrome.js's seen())."""
    chrome = run_chrome(case, "--dump-dom")
    found = re.search(r'data-seen="([^"]*)"', chrome.stdout)
    assert found, (
        f"The popup reported nothing. The page:\n{chrome.stdout[-2000:]}\n"
        f"Chrome ({chrome.returncode}):\n{chrome.stderr[-2000:]}"
    )
    return json.loads(html.unescape(found[1]))


def screenshot(case: Case, path: Path, scale: float) -> None:
    """The popup with the case, cut to its size, as a PNG; scale: the screen's
    (1.5 at 150%), so it looks as it does in Chrome on that screen."""
    width, height = run(case)["size"]
    run_chrome(
        case,
        f"--screenshot={path}",
        f"--window-size={width},{height}",
        f"--force-device-scale-factor={scale}",
        "--hide-scrollbars",
    )
    assert path.is_file(), f"Chrome made no screenshot at {path}"
