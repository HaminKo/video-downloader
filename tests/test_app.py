import os
import subprocess
import threading
import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from video_downloader.app import (
    CANCELLED,
    CANCELLING,
    FAILED_COLOR,
    GONE,
    LOOKING_UP,
    NO_SUBTITLES,
    PASTE_A_LINK,
    PLAYLIST_NOTE,
    QUALITIES,
    TITLE,
    WIDTH,
    App,
    Files,
    done_message,
    show_command,
    shown_folder,
    window_width,
)
from video_downloader.downloader import (
    Cancelled,
    Done,
    Event,
    Failed,
    Kind,
    Progress,
    Report,
)

LINK = "https://example.com/video"


class FakeDownload:
    """Stands in for yt-dlp: reports `events` at once and remembers the calls.
    With `until_cancelled`, it then waits for Cancel and reports Cancelled."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Kind, Path, int | None, bool]] = []
        self.events: list[Event] = [
            Progress("Downloading video: 40% of 12 MB", 40.0),
            Done(Path("Test video.mp4"), already_there=False),
        ]
        self.until_cancelled = False

    def __call__(
        self,
        link: str,
        kind: Kind,
        folder: Path,
        report: Report,
        height: int | None,
        subtitles: bool,
        cancel: threading.Event,
    ) -> None:
        self.calls.append((link, kind, folder, height, subtitles))
        for event in self.events:
            report(event)
        if self.until_cancelled and cancel.wait(timeout=5):
            report(Cancelled())


class FakeFiles(Files):
    """Opens nothing: remembers what it was asked to open, as ("play", path),
    ("show", path) or ("open_folder", path)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def play(self, file: Path) -> None:
        self.calls.append(("play", file))

    def show(self, file: Path) -> None:
        self.calls.append(("show", file))

    def open_folder(self, folder: Path) -> None:
        self.calls.append(("open_folder", folder))


@pytest.fixture
def fake() -> FakeDownload:
    return FakeDownload()


@pytest.fixture
def files() -> FakeFiles:
    return FakeFiles()


@pytest.fixture
def app(fake: FakeDownload, files: FakeFiles, tmp_path: Path) -> Iterator[App]:
    root = tk.Tk()
    root.withdraw()  # build the window without showing it
    try:
        yield App(root, fake, tmp_path, files)
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
    assert app.cancel_button.cget("text") == "Cancel"
    assert app.cancel_button.instate(["disabled"]), "nothing to cancel yet"
    assert app.kind.get() == Kind.MP4
    assert app.status.get() == ""
    assert app.root.minsize()[0] == window_width(app.root)
    assert app.play_button.cget("text") == "Play"
    assert app.show_button.cget("text") == "Show in folder"
    assert app.play_button.instate(["disabled"]), "nothing to play yet"
    assert not app.show_button.instate(["disabled"])


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
    assert fake.calls == [(LINK, Kind.MP4, tmp_path, None, False)]
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


def test_subtitles_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    assert str(app.subtitles_box.cget("text")) == "English subtitles"
    assert not app.subtitles.get(), "starts unticked"
    app.link.set(LINK)
    app.download_button.invoke()
    wait_until_done(app)
    app.subtitles_box.invoke()
    app.download_button.invoke()
    wait_until_done(app)
    assert [call[4] for call in fake.calls] == [False, True]


def test_video_choices_are_greyed_out_for_mp3_and_while_busy(app: App) -> None:
    choices = [app.quality_label, *app.quality_buttons, app.subtitles_box]

    def greyed() -> list[bool]:
        return [widget.instate(["disabled"]) for widget in choices]

    assert greyed() == [False] * 5
    app.mp3_button.invoke()
    assert greyed() == [True] * 5
    app.mp4_button.invoke()
    assert greyed() == [False] * 5
    app.link.set(LINK)
    app.download_button.invoke()
    assert greyed() == [True] * 5
    wait_until_done(app)
    assert greyed() == [False] * 5


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


def test_cancel_stops_the_download(app: App, fake: FakeDownload) -> None:
    fake.events = [Progress("Downloading video: 40% of 12 MB", 40.0)]
    fake.until_cancelled = True
    app.mp3_button.invoke()
    app.link.set(LINK)
    app.download_button.invoke()
    assert not app.cancel_button.instate(["disabled"])
    # Progress reported before Cancel is still waiting to be shown: it must
    # not replace "Cancelling...".
    deadline = time.monotonic() + 5
    while app.events.empty():
        assert time.monotonic() < deadline, "the fake never reported progress"
        time.sleep(0.01)
    app.cancel_button.invoke()
    assert app.status.get() == CANCELLING
    assert app.cancel_button.instate(["disabled"]), "once is enough"
    assert app.download_button.instate(["disabled"]), "until it has stopped"
    wait_until_done(app)
    assert app.status.get() == CANCELLED
    assert str(app.status_label.cget("foreground")) == "", "not a failure"
    assert app.progress_bar.cget("value") == 0
    assert not app.download_button.instate(["disabled"])
    assert app.cancel_button.instate(["disabled"])
    assert app.play_button.instate(["disabled"]), "nothing to play"
    assert (app.link.get(), app.kind.get()) == (LINK, Kind.MP3), "choices kept"


def test_play_and_show_in_folder_open_the_last_download(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    app.play_button.invoke()  # greyed out: does nothing
    app.show_button.invoke()
    assert files.calls == [("open_folder", tmp_path)], "no download yet: the folder"

    video = tmp_path / "Test video.mp4"
    video.write_bytes(b"")
    fake.events = [Done(video, already_there=False)]
    app.link.set(LINK)
    app.download_button.invoke()
    buttons = [app.play_button, app.show_button]
    assert all(b.instate(["disabled"]) for b in buttons), "greyed out while busy"
    wait_until_done(app)
    assert not any(b.instate(["disabled"]) for b in buttons)
    app.play_button.invoke()
    app.show_button.invoke()
    assert files.calls[1:] == [("play", video), ("show", video)]


def test_after_a_failure_play_is_greyed_out_again(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    video = tmp_path / "Test video.mp4"
    video.write_bytes(b"")
    fake.events = [Done(video, already_there=True)]
    app.link.set(LINK)
    app.download_button.invoke()
    wait_until_done(app)
    assert not app.play_button.instate(["disabled"]), "a file already there plays"
    fake.events = [Failed("No.")]
    app.download_button.invoke()
    wait_until_done(app)
    assert app.play_button.instate(["disabled"]), "the earlier file is not played"
    app.show_button.invoke()
    assert files.calls == [("open_folder", tmp_path)]


def test_a_moved_or_deleted_file_is_not_opened(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    video = tmp_path / "Test video.mp4"  # never written: it is gone
    fake.events = [Done(video, already_there=False)]
    app.link.set(LINK)
    app.download_button.invoke()
    wait_until_done(app)
    app.play_button.invoke()
    folder = shown_folder(tmp_path)
    assert app.status.get() == GONE.format(name=video.name, folder=folder)
    assert app.status.get().startswith("Can't play Test video.mp4: it isn't in ")
    assert str(app.status_label.cget("foreground")) == FAILED_COLOR
    assert app.play_button.instate(["disabled"]), "said once, then greyed out"
    app.show_button.invoke()
    assert files.calls == [("open_folder", tmp_path)], "the folder instead"


def test_files_opens_with_windows_own_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    opened: list[str | Path] = []
    monkeypatch.setattr(os, "startfile", opened.append)
    monkeypatch.setattr(subprocess, "Popen", opened.append)
    video = tmp_path / "Clip.mp4"
    folder = tmp_path / "Videos"  # not there yet
    Files().play(video)
    Files().show(video)
    Files().open_folder(folder)
    assert opened == [video, show_command(video), folder]
    assert folder.is_dir(), "the folder is made first"


def test_show_command_quotes_the_path() -> None:
    # Unquoted, Explorer would split the path at its commas.
    path = Path(r"C:\Videos\Cats, dogs & más.mp4")
    explorer = Path(os.environ["WINDIR"]) / "explorer.exe"
    assert explorer.is_file()
    assert show_command(path) == (
        f'"{explorer}" ' + r'/select,"C:\Videos\Cats, dogs & más.mp4"'
    )


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
    assert done_message(Done(path, True, no_subtitles=True)) == (
        f"Already there, not downloaded again: Clip.mp4 (in {folder}). {NO_SUBTITLES}"
    )
    assert done_message(Done(path, False, playlist=True, no_subtitles=True)) == (
        f"Done: Clip.mp4 (in {folder}). {NO_SUBTITLES} {PLAYLIST_NOTE}"
    )


def test_enter_is_bound_on_the_link_box(app: App) -> None:
    # A hidden window gets no key presses, so pressing Enter for real is
    # left to the GUI test (To do 2); here, check the binding is there.
    assert app.link_entry.bind("<Return>")
    assert not app.root.bind("<Return>")
