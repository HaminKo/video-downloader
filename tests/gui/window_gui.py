"""GUI test: opens the real window and uses it the way a user does.

Run it with: pytest tests/gui/window_gui.py
A plain `pytest` skips it (the file name doesn't start with test_), because the
window pops up on top and takes the keyboard focus for a moment.
"""

from collections.abc import Iterator

import pytest
from drive import (
    LINK,
    assert_inside_window,
    box,
    click,
    open_window,
    press,
    type_text,
)

from video_downloader.app import NOT_BUILT_YET, TITLE, App

# The window's sizes, in screen pixels: None is the size it opens with, which
# is also its smallest.
SIZES = {"opening size": None, "wide": 1200}


@pytest.fixture(params=list(SIZES.values()), ids=list(SIZES))
def app(request: pytest.FixtureRequest) -> Iterator[App]:
    app = open_window(width=request.param)
    try:
        yield app
    finally:
        app.root.destroy()


def test_enter_in_link_box_starts_download(app: App) -> None:
    assert app.root.title() == TITLE
    type_text(app.link_entry, LINK)
    assert app.link.get() == LINK, "the typed link should be in the link box"
    press(app.link_entry, "Return")
    assert app.status.get() == NOT_BUILT_YET, (
        "Enter in the link box should start a download"
    )


def test_download_button_starts_download(app: App) -> None:
    type_text(app.link_entry, LINK)
    click(app.download_button)
    assert app.status.get() == NOT_BUILT_YET, (
        "clicking Download should start a download"
    )


def test_link_box_and_button_fit_the_window(app: App) -> None:
    assert_inside_window(app.link_entry)
    assert_inside_window(app.download_button)
    entry_left, _, entry_right, _ = box(app.link_entry)
    button_left, _, _, _ = box(app.download_button)
    assert entry_right <= button_left, "the link box overlaps the Download button"
    window_width = app.root.winfo_width()
    assert entry_right - entry_left >= window_width / 2, (
        f"the link box should take most of the width: it is "
        f"{entry_right - entry_left} of {window_width} pixels"
    )
