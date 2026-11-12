import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from video_downloader.app import (
    FAILED_COLOR,
    LOOKING_UP,
    PASTE_A_LINK,
    PLAYLIST_NOTE,
    QUALITIES,
    TITLE,
    WIDTH,
    App,
    done_message,
    window_width,
)
from video_downloader.downloader import Done, Event, Failed, Kind, Progress, Report

LINK = "https://example.com/video"


class FakeDownload:
    """Stands in for yt-dlp: reports `events` at once and remembers the calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Kind, Path, int | None]] = []
        self.events: list[Event] = [
            Progress("Downloading video: 40% of 12 MB", 40.0),
            Done(Path("Test video.mp4"), already_there=False),
        ]

    def __call__(
        self, link: str, kind: Kind, folder: Path, report: Report, height: int | None
    ) -> None:
        self.calls.append((link, kind, folder, height))
        for event in self.events:
            report(event)


@pytest.fixture
def fake() -> FakeDownload:
    return FakeDownload()


@pytest.fixture
def app(fake: FakeDownload, tmp_path: Path) -> Iterator[App]:
    root = tk.Tk()
    root.withdraw()  # build the window without showing it
    try:
        yield App(root, fake, tmp_path)
    finally:
        root.destroy()


def wait_until_done(app: App) -> None:
    """Let the window run until the download has ended."""
    deadline = time.monotonic() + 5
    while app.busy:
        assert time.monotonic() < deadline, "the download never ended"
        app.root.update()
        time.sleep(0.01)


def test_window_has_its_parts(app: App) -> None:
    assert app.root.title() == TITLE
    assert app.download_button.cget("text") == "Download"
    assert app.kind.get() == Kind.MP4
    assert app.status.get() == ""
    assert app.root.minsize()[0] == window_width(app.root)


def test_window_width_follows_the_display_scaling(
    app: App, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.root, "winfo_fpixels", lambda _: 96.0)
    assert window_width(app.root) == WIDTH == 600
    monkeypatch.setattr(app.root, "winfo_fpixels", lambda _: 144.0)  # 150%
    assert window_width(app.root) == 900


def test_download_shows_progress_then_done(
    app: App, fake: FakeDownload, tmp_path: Path
) -> None:
    app.link.set(f"  {LINK} ")
    app.download_button.invoke()
    assert app.busy
    assert app.status.get() == LOOKING_UP
    assert app.download_button.instate(["disabled"])
    wait_until_done(app)
    assert fake.calls == [(LINK, Kind.MP4, tmp_path, None)]
    assert app.status.get() == done_message(Done(Path("Test video.mp4"), False))
    assert app.progress_bar.cget("value") == 100
    assert not app.download_button.instate(["disabled"])


def test_mp3_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    app.mp3_button.invoke()
    app.link.set(LINK)
    app.download_button.invoke()
    wait_until_done(app)
    assert fake.calls[0][1] == Kind.MP3


def test_quality_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    labels = [str(button.cget("text")) for button in app.quality_buttons]
    assert labels == list(QUALITIES) == ["Best", "720p", "480p"]
    assert QUALITIES[app.quality.get()] is None, "starts at Best"
    app.quality_buttons[1].invoke()
    app.link.set(LINK)
    app.download_button.invoke()
    wait_until_done(app)
    assert fake.calls[0][3] == 720


def test_quality_is_greyed_out_for_mp3_and_while_busy(app: App) -> None:
    quality = [app.quality_label, *app.quality_buttons]

    def greyed() -> list[bool]:
        return [widget.instate(["disabled"]) for widget in quality]

    assert greyed() == [False] * 4
    app.mp3_button.invoke()
    assert greyed() == [True] * 4
    app.mp4_button.invoke()
    assert greyed() == [False] * 4
    app.link.set(LINK)
    app.download_button.invoke()
    assert greyed() == [True] * 4
    wait_until_done(app)
    assert greyed() == [False] * 4


def test_one_download_at_a_time(app: App, fake: FakeDownload) -> None:
    app.link.set(LINK)
    app.download_button.invoke()
    app.start_download()  # Enter in the link box while busy
    wait_until_done(app)
    assert len(fake.calls) == 1


def test_empty_link_asks_for_one(app: App, fake: FakeDownload) -> None:
    app.download_button.invoke()
    assert app.status.get() == PASTE_A_LINK
    assert fake.calls == []
    assert not app.busy


def test_failure_shows_the_message(app: App, fake: FakeDownload) -> None:
    fake.events = [Progress("Joining video and audio...", None), Failed("No.")]
    app.link.set(LINK)
    app.download_button.invoke()
    wait_until_done(app)
    assert app.status.get() == "No."
    assert str(app.status_label.cget("foreground")) == FAILED_COLOR
    assert app.progress_bar.cget("value") == 0
    assert not app.mp3_button.instate(["disabled"])

    # The next message is in the normal color again.
    app.download_button.invoke()
    assert app.status.get() == LOOKING_UP
    assert str(app.status_label.cget("foreground")) == ""
    wait_until_done(app)


def test_done_message_names_the_folder_from_home() -> None:
    path = Path.home() / "Downloads" / "Videos" / "Clip.mp4"
    folder = Path("Downloads") / "Videos"
    assert done_message(Done(path, False)) == f"Done: Clip.mp4 (in {folder})"
    assert done_message(Done(path, True)) == (
        f"Already there, not downloaded again: Clip.mp4 (in {folder})"
    )
    assert done_message(Done(path, False, playlist=True)) == (
        f"Done: Clip.mp4 (in {folder}). {PLAYLIST_NOTE}"
    )


def test_enter_is_bound_on_the_link_box(app: App) -> None:
    # A hidden window gets no key presses, so pressing Enter for real is
    # left to the GUI test (To do 2); here, check the binding is there.
    assert app.link_entry.bind("<Return>")
    assert not app.root.bind("<Return>")
