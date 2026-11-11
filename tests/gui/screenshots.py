"""Screenshots of the window, for Claude to read.

    python tests/gui/screenshots.py           every screen
    python tests/gui/screenshots.py done      one screen by name

Saved to the temp folder (video-downloader-screenshots), never the project;
prints each file's path. The window pops up on top for a moment.
"""

import sys
from collections.abc import Callable

from drive import (
    LINK,
    PROGRESS,
    SCREENSHOT_DIR,
    FakeDownload,
    click,
    open_window,
    screenshot,
    type_text,
    wait_until,
)

from video_downloader.app import App
from video_downloader.downloader import FFMPEG_MISSING, Failed


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


SCREENS: dict[str, Callable[[App, FakeDownload], None]] = {
    "start": opened,
    "progress": downloading,
    "done": done,
    "error": failed,
}


def main(names: list[str]) -> int:
    unknown = [name for name in names if name not in SCREENS]
    if unknown:
        print(f"Unknown screen: {', '.join(unknown)}. Screens: {', '.join(SCREENS)}")
        return 2
    for name in names or SCREENS:
        fake = FakeDownload()
        app = open_window(fake)
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
