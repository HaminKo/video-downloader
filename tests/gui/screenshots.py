"""Screenshots of the window, for Claude to read.

    python tests/gui/screenshots.py           every screen
    python tests/gui/screenshots.py status    one screen by name

Saved to the temp folder (video-downloader-screenshots), never the project;
prints each file's path. The window pops up on top for a moment.
"""

import sys
from collections.abc import Callable

from drive import LINK, SCREENSHOT_DIR, click, open_window, screenshot, type_text

from video_downloader.app import App


def opened(app: App) -> None:
    """As the window opens: empty link box."""


def after_download(app: App) -> None:
    """A link typed and Download clicked: the status line shows a message."""
    type_text(app.link_entry, LINK)
    click(app.download_button)


SCREENS: dict[str, Callable[[App], None]] = {
    "start": opened,
    "status": after_download,
}


def main(names: list[str]) -> int:
    unknown = [name for name in names if name not in SCREENS]
    if unknown:
        print(f"Unknown screen: {', '.join(unknown)}. Screens: {', '.join(SCREENS)}")
        return 2
    for name in names or SCREENS:
        app = open_window()
        try:
            SCREENS[name](app)
            path = screenshot(app, name)
        finally:
            app.root.destroy()
        print(path)
    print(f"Folder: {SCREENSHOT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
