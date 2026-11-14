"""Screenshots of the window, for Claude to read.

    python tests/gui/screenshots.py           every screen
    python tests/gui/screenshots.py done      one screen by name

Saved to the temp folder (video-downloader-screenshots), never the project;
prints each file's path. The window pops up on top for a moment.
"""

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from drive import (
    LINK,
    LINK2,
    PROGRESS,
    SCREENSHOT_DIR,
    FakeDownload,
    click,
    open_window,
    press,
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


SCREENS: dict[str, Callable[[App, FakeDownload], None]] = {
    "start": opened,
    "progress": downloading,
    "done": done,
    "error": failed,
    "cancelled": cancelled,
    "queue": queued,
    "history": with_history,
}

# The screens whose window opens with past downloads; the others with none.
WITH_HISTORY = {"history"}


def main(names: list[str]) -> int:
    unknown = [name for name in names if name not in SCREENS]
    if unknown:
        print(f"Unknown screen: {', '.join(unknown)}. Screens: {', '.join(SCREENS)}")
        return 2
    for name in names or SCREENS:
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
