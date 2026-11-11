"""GUI test: opens the real window and uses it the way a user does.

Run it with: pytest tests/gui/window_gui.py
A plain `pytest` skips it (the file name doesn't start with test_), because the
window pops up on top and takes the keyboard focus for a moment. A fake
download stands in for yt-dlp, so nothing touches the internet.
"""

from collections.abc import Iterator

import pytest
from drive import (
    LINK,
    PROGRESS,
    VIDEO_TITLE,
    FakeDownload,
    assert_inside_window,
    box,
    click,
    open_window,
    press,
    type_text,
    wait_until,
)

from video_downloader.app import TITLE, App
from video_downloader.downloader import Kind

# The window's sizes, in screen pixels: None is the size it opens with, which
# is also its smallest.
SIZES = {"opening size": None, "wide": 1200}


@pytest.fixture
def fake() -> Iterator[FakeDownload]:
    fake = FakeDownload()
    yield fake
    fake.finish()  # never leave the download's thread waiting


@pytest.fixture(params=list(SIZES.values()), ids=list(SIZES))
def app(request: pytest.FixtureRequest, fake: FakeDownload) -> Iterator[App]:
    app = open_window(fake, width=request.param)
    try:
        yield app
    finally:
        app.root.destroy()


def wait_for_progress(app: App, after: str) -> None:
    wait_until(app, lambda: app.status.get() == PROGRESS, f"progress after {after}")


def finish(app: App, fake: FakeDownload) -> None:
    fake.finish()
    wait_until(app, lambda: not app.busy, "the download to end")


def test_enter_in_link_box_starts_download(app: App, fake: FakeDownload) -> None:
    assert app.root.title() == TITLE
    type_text(app.link_entry, LINK)
    assert app.link.get() == LINK, "the typed link should be in the link box"
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter in the link box")
    assert fake.calls == [(LINK, Kind.MP4, app.folder)]
    finish(app, fake)


def test_download_button_shows_progress_then_done(app: App, fake: FakeDownload) -> None:
    type_text(app.link_entry, LINK)
    click(app.download_button)
    wait_for_progress(app, "clicking Download")
    assert app.progress_bar.cget("value") == 40
    assert app.download_button.instate(["disabled"]), "one download at a time"
    click(app.download_button)
    finish(app, fake)
    assert len(fake.calls) == 1, "a greyed-out Download should do nothing"
    assert app.status.get().startswith(f"Done: {VIDEO_TITLE}.mp4"), app.status.get()
    assert app.progress_bar.cget("value") == 100
    assert not app.download_button.instate(["disabled"])


def test_mp3_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    click(app.mp3_button)
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    wait_for_progress(app, "choosing MP3 and pressing Enter")
    assert fake.calls[0][1] == Kind.MP3
    finish(app, fake)
    assert app.status.get().startswith(f"Done: {VIDEO_TITLE}.mp3"), app.status.get()


def test_everything_fits_the_window(app: App) -> None:
    for widget in (
        app.link_entry,
        app.download_button,
        app.mp4_button,
        app.mp3_button,
        app.progress_bar,
    ):
        assert_inside_window(widget)
    entry_left, _, entry_right, _ = box(app.link_entry)
    button_left, _, _, _ = box(app.download_button)
    assert entry_right <= button_left, "the link box overlaps the Download button"
    window_width = app.root.winfo_width()
    assert entry_right - entry_left >= window_width / 2, (
        f"the link box should take most of the width: it is "
        f"{entry_right - entry_left} of {window_width} pixels"
    )
    type_text(app.link_entry, LINK)
    assert app.link_entry.xview() == (0.0, 1.0), (
        f"a typical YouTube link ({len(LINK)} characters) should fit in the "
        f"link box; it shows {app.link_entry.xview()} of it"
    )


def test_long_message_wraps_instead_of_widening(app: App) -> None:
    width = app.root.winfo_width()
    app.status.set("A long message from yt-dlp, " * 12)
    app.root.update()
    assert app.root.winfo_width() == width, "a long message widened the window"
    assert_inside_window(app.status_label)
