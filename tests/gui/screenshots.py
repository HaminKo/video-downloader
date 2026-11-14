"""Screenshots of the window and of the Chrome button's popup, for Claude to
read.

    python tests/gui/screenshots.py           every screen
    python tests/gui/screenshots.py done      one screen by name

Saved to the temp folder (video-downloader-screenshots), never the project;
prints each file's path. The window pops up on top for a moment, on another
screen if there is one (drive.py), without taking the keyboard. The popup is
drawn by headless Chrome (popup.py), at the main screen's scaling; nothing
shows.
"""

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import popup
from drive import (
    LINK,
    LINK2,
    PROGRESS,
    SCREENSHOT_DIR,
    FakeDownload,
    click,
    open_window,
    press,
    screens,
    screenshot,
    type_text,
    wait_until,
    write_history,
)

from video_downloader.app import App
from video_downloader.downloader import FFMPEG_MISSING, Failed, default_folder


def opened(app: App, fake: FakeDownload) -> None:
    """As the window opens: empty link box."""


def downloading(app: App, fake: FakeDownload) -> None:
    """A link typed and Download clicked: the bar and the status line show
    progress."""
    type_text(app.link_entry, LINK)
    click(app.download_button)
    wait_until(app, lambda: app.status.get() == PROGRESS, "the progress message")


def done(app: App, fake: FakeDownload) -> None:
    """The download has ended: the status line names the file and folder."""
    downloading(app, fake)
    fake.finish()
    wait_until(app, lambda: not app.busy, "the download to end")


def failed(app: App, fake: FakeDownload) -> None:
    """The download failed: a plain message in dark red (the longest one, so
    it wraps)."""
    downloading(app, fake)
    fake.finish(Failed(FFMPEG_MISSING))
    wait_until(app, lambda: not app.busy, "the download to end")


def cancelled(app: App, fake: FakeDownload) -> None:
    """Cancel clicked during a download: "Cancelled." in the normal color."""
    downloading(app, fake)
    click(app.cancel_button)
    wait_until(app, lambda: not app.busy, "the download to stop")


def queued(app: App, fake: FakeDownload) -> None:
    """Three links in the list: one done, one downloading, one waiting."""
    done(app, fake)
    type_text(app.link_entry, LINK2)
    press(app.link_entry, "Return")
    wait_until(app, lambda: app.status.get() == PROGRESS, "the second download")
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")


def with_history(app: App, fake: FakeDownload) -> None:
    """Opened with past downloads in the history (PAST), then a link typed:
    it downloads below them, in view."""
    downloading(app, fake)


def received(app: App, fake: FakeDownload) -> None:
    """A link sent from outside (python -m video_downloader LINK): in the box,
    the hint under the list. The window isn't really brought to the front:
    that would take the user's keyboard."""
    with mock.patch("video_downloader.app.bring_to_front"):
        app.receive_link(LINK)
    app.root.update()


SCREENS: dict[str, Callable[[App, FakeDownload], None]] = {
    "start": opened,
    "progress": downloading,
    "done": done,
    "error": failed,
    "cancelled": cancelled,
    "queue": queued,
    "history": with_history,
    "received": received,
}

# The screens whose window opens with past downloads; the others with none.
WITH_HISTORY = {"history"}

# The Chrome button's popup: on a video's page, and on the New Tab page.
POPUP_SCREENS: dict[str, popup.Case] = {
    "popup": {"url": LINK},
    "popup-error": {"url": None},
}


def popup_screenshot(name: str) -> Path:
    main_dpi = next((screen.dpi for screen in screens() if screen.main), 96)
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    popup.screenshot(POPUP_SCREENS[name], path, scale=main_dpi / 96)
    return path


def main(names: list[str]) -> int:
    known = [*SCREENS, *POPUP_SCREENS]
    unknown = [name for name in names if name not in known]
    if unknown:
        print(f"Unknown screen: {', '.join(unknown)}. Screens: {', '.join(known)}")
        return 2
    for name in names or known:
        if name in POPUP_SCREENS:
            print(popup_screenshot(name))
            continue
        fake = FakeDownload()
        # A history of its own, so the real one is never read or changed.
        with tempfile.TemporaryDirectory() as data:
            history = Path(data) / "history.json"
            if name in WITH_HISTORY:
                write_history(history, default_folder())
            app = open_window(fake, history)
            try:
                SCREENS[name](app, fake)
                path = screenshot(app, name)
            finally:
                fake.finish()
                app.root.destroy()
        print(path)
    print(f"Folder: {SCREENSHOT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
