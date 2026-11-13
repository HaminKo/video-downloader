"""GUI test: opens the real window and uses it the way a user does.

Run it with: pytest tests/gui/window_gui.py
A plain `pytest` skips it (the file name doesn't start with test_), because the
window pops up on top and takes the keyboard focus for a moment. A fake
download stands in for yt-dlp, so nothing touches the internet.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from drive import (
    LINK,
    PROGRESS,
    VIDEO_TITLE,
    FakeDownload,
    FakeFiles,
    assert_inside_window,
    box,
    click,
    open_window,
    press,
    type_text,
    wait_until,
)

from video_downloader.app import CANCELLED, FAILED_COLOR, TITLE, App
from video_downloader.downloader import FFMPEG_MISSING, Failed, Kind

# The window's sizes, in screen pixels: None is the size it opens with, which
# is also its smallest.
SIZES = {"opening size": None, "wide": 1200}


@pytest.fixture
def fake() -> Iterator[FakeDownload]:
    fake = FakeDownload()
    yield fake
    fake.finish()  # never leave the download's thread waiting


@pytest.fixture
def files() -> FakeFiles:
    return FakeFiles()


@pytest.fixture(params=list(SIZES.values()), ids=list(SIZES))
def app(
    request: pytest.FixtureRequest, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> Iterator[App]:
    app = open_window(fake, width=request.param, folder=tmp_path, files=files)
    try:
        yield app
    finally:
        app.root.destroy()


def wait_for_progress(app: App, after: str) -> None:
    wait_until(app, lambda: app.status.get() == PROGRESS, f"progress after {after}")


def finish(app: App, fake: FakeDownload, failure: Failed | None = None) -> None:
    fake.finish(failure)
    wait_until(app, lambda: not app.busy, "the download to end")


def test_enter_in_link_box_starts_download(app: App, fake: FakeDownload) -> None:
    assert app.root.title() == TITLE
    type_text(app.link_entry, LINK)
    assert app.link.get() == LINK, "the typed link should be in the link box"
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter in the link box")
    assert fake.calls == [(LINK, Kind.MP4, app.folder, None, False)]
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


def test_quality_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    best, p720, p480 = app.quality_buttons
    quality = [app.quality_label, *app.quality_buttons]
    click(app.mp3_button)
    assert all(w.instate(["disabled"]) for w in quality), "no quality for MP3"
    click(p480)
    assert app.quality.get() == "Best", "a greyed-out choice was taken"
    click(app.mp4_button)
    assert not any(w.instate(["disabled"]) for w in quality)
    click(p720)
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    wait_for_progress(app, "choosing 720p and pressing Enter")
    assert fake.calls == [(LINK, Kind.MP4, app.folder, 720, False)]
    assert best.instate(["disabled"]), "no other quality during a download"
    finish(app, fake)
    assert not best.instate(["disabled"])


def test_subtitles_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    box = app.subtitles_box
    click(app.mp3_button)
    assert box.instate(["disabled"]), "no subtitles for MP3"
    click(box)
    assert not app.subtitles.get(), "a greyed-out box was ticked"
    click(app.mp4_button)
    click(box)
    assert app.subtitles.get(), "clicking the box should tick it"
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    wait_for_progress(app, "ticking subtitles and pressing Enter")
    assert fake.calls == [(LINK, Kind.MP4, app.folder, None, True)]
    assert box.instate(["disabled"]), "no other choice during a download"
    finish(app, fake)
    assert not box.instate(["disabled"])
    click(box)
    assert not app.subtitles.get(), "clicking again should untick it"


def test_failure_shows_a_plain_message_in_red(app: App, fake: FakeDownload) -> None:
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter in the link box")
    finish(app, fake, Failed(FFMPEG_MISSING))  # the longest plain message
    assert app.status.get() == FFMPEG_MISSING
    assert str(app.status_label.cget("foreground")) == FAILED_COLOR
    assert_inside_window(app.status_label)
    assert_inside_window(app.show_button)  # the window grew to fit the message
    assert app.progress_bar.cget("value") == 0
    assert not app.download_button.instate(["disabled"]), "can try again"

    click(app.download_button)  # the next try shows progress in the normal color
    wait_for_progress(app, "clicking Download again")
    assert str(app.status_label.cget("foreground")) == ""
    finish(app, fake)


def test_play_and_show_in_folder(
    app: App, fake: FakeDownload, files: FakeFiles
) -> None:
    assert app.play_button.instate(["disabled"]), "nothing to play yet"
    click(app.play_button)
    click(app.show_button)
    assert files.calls == [("open_folder", app.folder)], "no download yet: the folder"

    video = app.folder / f"{VIDEO_TITLE}.mp4"
    video.write_bytes(b"")  # the fake download saves nothing
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter in the link box")
    assert app.show_button.instate(["disabled"]), "nothing opens during a download"
    finish(app, fake)
    click(app.play_button)
    click(app.show_button)
    assert files.calls[1:] == [("play", video), ("show", video)]


def test_cancel_stops_the_download(app: App, fake: FakeDownload) -> None:
    assert app.cancel_button.instate(["disabled"]), "nothing to cancel yet"
    click(app.mp3_button)
    type_text(app.link_entry, LINK)
    click(app.download_button)
    wait_for_progress(app, "clicking Download")
    assert not app.cancel_button.instate(["disabled"])
    click(app.cancel_button)
    wait_until(app, lambda: not app.busy, "the download to stop")
    assert app.status.get() == CANCELLED
    assert str(app.status_label.cget("foreground")) == "", "not a failure"
    assert app.progress_bar.cget("value") == 0
    assert app.cancel_button.instate(["disabled"])
    assert app.play_button.instate(["disabled"]), "nothing to play"
    assert (app.link.get(), app.kind.get()) == (LINK, Kind.MP3), "choices kept"

    click(app.download_button)  # the next download works
    wait_for_progress(app, "clicking Download after Cancel")
    finish(app, fake)
    assert app.status.get().startswith(f"Done: {VIDEO_TITLE}.mp3"), app.status.get()


def test_everything_fits_the_window(app: App) -> None:
    for widget in (
        app.link_entry,
        app.download_button,
        app.cancel_button,
        app.mp4_button,
        app.mp3_button,
        app.quality_label,
        *app.quality_buttons,
        app.subtitles_box,
        app.progress_bar,
        app.play_button,
        app.show_button,
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
    assert_inside_window(app.show_button)
