import tkinter as tk
from collections.abc import Iterator

import pytest

from video_downloader.app import NOT_BUILT_YET, TITLE, App


@pytest.fixture
def app() -> Iterator[App]:
    root = tk.Tk()
    root.withdraw()  # build the window without showing it
    try:
        yield App(root)
    finally:
        root.destroy()


def test_window_has_link_box_and_download_button(app: App) -> None:
    assert app.root.title() == TITLE
    assert app.download_button.cget("text") == "Download"
    assert app.status.get() == ""


def test_download_says_not_built_yet(app: App) -> None:
    app.link.set("https://example.com/video")
    app.download_button.invoke()
    assert app.status.get() == NOT_BUILT_YET


def test_enter_is_bound_on_the_link_box(app: App) -> None:
    # A hidden window gets no key presses, so pressing Enter for real is
    # left to the GUI test (To do 2); here, check the binding is there.
    assert app.link_entry.bind("<Return>")
    assert not app.root.bind("<Return>")
