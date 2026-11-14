"""GUI test: opens the real window and uses it the way a user does.

Run it with: pytest tests/gui/window_gui.py
A plain `pytest` skips it (the file name doesn't start with test_), because the
windows pop up on top, on another screen if there is one (drive.py). A fake
download stands in for yt-dlp, so nothing touches the internet.
"""

import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest
from drive import (
    LINK,
    LINK2,
    PAST,
    PROGRESS,
    TITLES,
    VIDEO_TITLE,
    FakeDownload,
    FakeFiles,
    Screen,
    assert_inside_window,
    box,
    click,
    click_row,
    open_window,
    pick_screen,
    press,
    screens,
    type_text,
    wait_until,
    write_history,
)

from video_downloader import handoff
from video_downloader.app import (
    CANCELLED,
    FAILED_COLOR,
    LINK_RECEIVED,
    PASTE_A_LINK,
    TITLE,
    WAITING,
    App,
    load_history,
)
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
    request: pytest.FixtureRequest,
    fake: FakeDownload,
    files: FakeFiles,
    tmp_path: Path,
    pipe: str,
) -> Iterator[App]:
    history = tmp_path / "history.json"
    app = open_window(
        fake, history, request.param, folder=tmp_path, files=files, pipe=pipe
    )
    try:
        yield app
    finally:
        app.root.destroy()


def wait_for_progress(app: App, after: str) -> None:
    wait_until(app, lambda: app.status.get() == PROGRESS, f"progress after {after}")


def finish(app: App, fake: FakeDownload, failure: Failed | None = None) -> None:
    fake.finish(failure)
    wait_until(app, lambda: not app.busy, "the download to end")


def rows(app: App) -> list[tuple[str, ...]]:
    """The list's rows as shown: Video, As and State."""
    tree = app.downloads
    return [tuple(map(str, tree.item(row, "values"))) for row in tree.get_children()]


def test_enter_in_link_box_starts_download(app: App, fake: FakeDownload) -> None:
    assert app.root.title() == TITLE
    type_text(app.link_entry, LINK)
    assert app.link.get() == LINK, "the typed link should be in the link box"
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter in the link box")
    assert fake.calls == [(LINK, Kind.MP4, app.folder, None, False)]
    assert app.link.get() == "", "the box empties for the next link"
    finish(app, fake)


def test_a_sent_link_fills_the_box_and_enter_starts_it(
    app: App, fake: FakeDownload, pipe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Recorded: really bringing the window to the front would take the user's
    # keyboard. That part was checked by hand (To do 10).
    to_front: list[tk.Tk] = []
    monkeypatch.setattr("video_downloader.app.bring_to_front", to_front.append)
    type_text(app.link_entry, "half")
    assert handoff.send(LINK2, pipe), "the window listens on its pipe"
    wait_until(app, lambda: app.link.get() == LINK2, "the sent link in the box")
    assert to_front == [app.root], "the window is brought to the front"
    assert app.status.get() == LINK_RECEIVED
    assert fake.calls == [], "it waits for Download"
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter after a sent link")
    assert fake.calls == [(LINK2, Kind.MP4, app.folder, None, False)]
    finish(app, fake)


def test_download_button_shows_progress_then_done(app: App, fake: FakeDownload) -> None:
    type_text(app.link_entry, LINK)
    click(app.download_button)
    wait_for_progress(app, "clicking Download")
    assert app.progress_bar.cget("value") == 40
    assert rows(app) == [(VIDEO_TITLE, "MP4", "Downloading 40%")]
    click(app.download_button)  # the box is empty now
    assert app.status.get() == PASTE_A_LINK
    finish(app, fake)
    assert len(fake.calls) == 1, "an empty box should add nothing"
    assert app.status.get().startswith(f"Done: {VIDEO_TITLE}.mp4"), app.status.get()
    assert app.progress_bar.cget("value") == 100
    assert rows(app) == [(VIDEO_TITLE, "MP4", "Done")]


def test_second_link_waits_its_turn(app: App, fake: FakeDownload) -> None:
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    wait_for_progress(app, "Enter in the link box")
    first, second = TITLES[LINK], TITLES[LINK2]
    click(app.mp3_button)  # the next link's choice; the running one stays MP4
    type_text(app.link_entry, LINK2)
    click(app.download_button)
    assert rows(app) == [
        (first, "MP4", "Downloading 40%"),
        (LINK2, "MP3", "Waiting"),
    ]
    assert app.status.get() == PROGRESS, "the running one stays selected"
    click_row(app.downloads, app.downloads.get_children()[1])
    assert app.status.get() == WAITING
    click_row(app.downloads, app.downloads.get_children()[0])

    fake.finish()  # the first ends: the second starts and is selected
    wait_until(app, lambda: len(fake.calls) == 2, "the second download to start")
    wait_for_progress(app, "the first download ended")
    assert fake.calls[1] == (LINK2, Kind.MP3, app.folder, None, False)
    assert rows(app)[0] == (first, "MP4", "Done")
    finish(app, fake)
    assert app.status.get().startswith(f"Done: {second}.mp3"), app.status.get()
    assert rows(app) == [(first, "MP4", "Done"), (second, "MP3", "Done")]


def test_remove_a_waiting_link(app: App, fake: FakeDownload) -> None:
    type_text(app.link_entry, LINK)
    press(app.link_entry, "Return")
    type_text(app.link_entry, LINK2)
    press(app.link_entry, "Return")
    wait_for_progress(app, "two links")
    running, waiting = app.downloads.get_children()
    assert app.remove_button.instate(["disabled"]), "not the running one"
    click_row(app.downloads, waiting)
    assert not app.remove_button.instate(["disabled"])
    click(app.remove_button)
    assert app.downloads.get_children() == (running,)
    assert app.status.get() == PROGRESS, "the running one is selected again"
    finish(app, fake)
    assert [call[0] for call in fake.calls] == [LINK], "the removed one never starts"


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
    assert rows(app)[0][1] == "MP4 720p"
    assert not best.instate(["disabled"]), "usable for the next link"
    finish(app, fake)


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
    assert rows(app)[0][1] == "MP4, subtitles"
    assert not box.instate(["disabled"]), "usable for the next link"
    finish(app, fake)
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
    assert rows(app) == [(VIDEO_TITLE, "MP4", "Failed")]

    type_text(app.link_entry, LINK)  # the next try: progress in the normal color
    click(app.download_button)
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
    assert app.play_button.instate(["disabled"]), "nothing to play yet"
    finish(app, fake)
    click(app.play_button)
    click(app.show_button)
    assert files.calls[1:] == [("play", video), ("show", video)]

    # During the next download, the finished one still plays: a double click
    # on its row, or selecting it and clicking Play.
    type_text(app.link_entry, LINK2)
    press(app.link_entry, "Return")
    wait_for_progress(app, "a second link")
    done, running = app.downloads.get_children()
    assert app.play_button.instate(["disabled"]), "the running one has no file yet"
    click_row(app.downloads, done, double=True)
    assert files.calls[3:] == [("play", video)]
    assert app.downloads.selection() == (done,)
    click(app.show_button)
    assert files.calls[4:] == [("show", video)]
    finish(app, fake)
    assert app.downloads.selection() == (done,), "the user's choice stays"


def test_past_downloads_are_listed_first(
    fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    history = tmp_path / "history.json"
    write_history(history, tmp_path)
    app = open_window(fake, history, folder=tmp_path, files=files)
    try:
        tree = app.downloads
        first, *_, newest = tree.get_children()
        title = PAST[-1][0]
        assert len(rows(app)) == len(PAST)
        assert rows(app)[-1] == (title, "MP4 720p, subtitles", "Done")
        assert tree.bbox(newest) and not tree.bbox(first), "the newest in view"
        assert (app.status.get(), tree.selection()) == ("", ())
        assert app.remove_button.instate(["disabled"]), "nothing selected"
        video = tmp_path / f"{title}.mp4"
        video.write_bytes(b"")
        click_row(tree, newest)
        assert app.status.get().startswith(f"Done: {title}.mp4"), app.status.get()
        click(app.play_button)
        assert files.calls == [("play", video)]

        type_text(app.link_entry, LINK)  # this session's go below the past
        press(app.link_entry, "Return")
        wait_for_progress(app, "Enter in the link box")
        finish(app, fake)
        assert rows(app)[-1] == (VIDEO_TITLE, "MP4", "Done")
        assert len(load_history(history) or []) == len(PAST) + 1, "saved at once"

        tree.see(first)  # scrolled up
        click_row(tree, first)
        press(tree, "Delete")
        assert first not in tree.get_children()
        titles = [job.title for job in load_history(history) or []]
        assert titles == [past[0] for past in PAST[1:]] + [VIDEO_TITLE]
    finally:
        app.root.destroy()


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
    assert rows(app) == [(VIDEO_TITLE, "MP3", "Cancelled")]
    assert app.kind.get() == Kind.MP3, "choices kept"

    type_text(app.link_entry, LINK)  # the next download works
    click(app.download_button)
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
        app.downloads,
        app.scrollbar,
        app.progress_bar,
        app.play_button,
        app.show_button,
        app.remove_button,
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


def test_the_topmost_other_screen_is_picked() -> None:
    main = Screen(0, 0, 2560, 1528, main=True, dpi=144)
    above = Screen(960, -1620, 3840, -72, main=False, dpi=144)
    right = Screen(3840, -1298, 7680, 790, main=False, dpi=144)
    assert pick_screen([right, main, above]) == above
    assert pick_screen([main, right]) == right
    other_scaling = above._replace(dpi=96)
    assert pick_screen([main, other_scaling]) is None, "it would be stretched"
    assert pick_screen([main]) is None


def test_the_window_opens_on_the_picked_screen(app: App) -> None:
    screen = pick_screen(screens())
    if screen is None:
        pytest.skip("no other screen with the main screen's scaling")
    # Tk's own position: in the same pixels as the screen's edges (with a
    # screen at another scaling, window_frame()'s pixels differ).
    root = app.root
    left, top = root.winfo_rootx(), root.winfo_rooty()
    right, bottom = left + root.winfo_width(), top + root.winfo_height()
    inside = (
        screen.left <= left
        and screen.top <= top
        and right <= screen.right
        and bottom <= screen.bottom
    )
    assert inside, f"window at {(left, top, right, bottom)}, screen {screen}"
