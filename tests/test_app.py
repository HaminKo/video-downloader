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
    NO_END,
    NO_SUBTITLES,
    PASTE_A_LINK,
    PLAYLIST_NOTE,
    QUALITIES,
    TITLE,
    WAITING,
    WIDTH,
    App,
    Files,
    Job,
    State,
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
LINK2 = "https://example.com/second"
LINK3 = "https://example.com/third"


class FakeDownload:
    """Stands in for yt-dlp: reports the link's events in `results` (or else
    `events`) at once and remembers the calls. A link in `wait_for_cancel`
    reports only their progress, then waits for Cancel and reports
    Cancelled: one download's last report must be its only end."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Kind, Path, int | None, bool]] = []
        self.events: list[Event] = [
            Progress("Downloading video: 40% of 12 MB", 40.0),
            Done(Path("Test video.mp4"), already_there=False),
        ]
        self.results: dict[str, list[Event]] = {}
        self.wait_for_cancel: set[str] = set()

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
        until_cancelled = link in self.wait_for_cancel
        for event in self.results.get(link, self.events):
            if isinstance(event, Progress) or not until_cancelled:
                report(event)
        if until_cancelled and cancel.wait(timeout=5):
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
    """Let the window run until every download in the list has ended."""
    deadline = time.monotonic() + 5
    while app.busy:
        assert time.monotonic() < deadline, "the download never ended"
        app.root.update()
        time.sleep(0.01)


def add(app: App, link: str) -> str:
    """Paste `link` and click Download; returns its row in the list."""
    app.link.set(link)
    app.download_button.invoke()
    return app.downloads.get_children()[-1]


def select(app: App, row: str) -> None:
    """Select the row as a click does."""
    app.downloads.selection_set(row)
    app.root.update()  # the list says a row was selected


def rows(app: App) -> list[tuple[str, ...]]:
    """The list's rows as shown: Video, As and State."""
    tree = app.downloads
    return [tuple(map(str, tree.item(row, "values"))) for row in tree.get_children()]


def test_window_has_its_parts(app: App) -> None:
    assert app.root.title() == TITLE
    assert app.download_button.cget("text") == "Download"
    assert app.cancel_button.cget("text") == "Cancel"
    assert app.cancel_button.instate(["disabled"]), "nothing to cancel yet"
    assert app.kind.get() == Kind.MP4
    assert app.status.get() == ""
    assert app.root.minsize()[0] == window_width(app.root)
    headings = [app.downloads.heading(c, "text") for c in app.downloads["columns"]]
    assert headings == ["Video", "As", "State"]
    assert rows(app) == [], "no downloads yet"
    assert app.play_button.cget("text") == "Play"
    assert app.show_button.cget("text") == "Show in folder"
    assert app.remove_button.cget("text") == "Remove"
    assert app.play_button.instate(["disabled"]), "nothing to play yet"
    assert not app.show_button.instate(["disabled"])
    assert app.remove_button.instate(["disabled"]), "nothing to remove yet"


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
    fake.events = [
        Progress("Downloading video: 40% of 12 MB", 40.0, "Test video"),
        Done(Path("Test video.mp4"), already_there=False),
    ]
    row = add(app, f"  {LINK} ")
    assert app.busy
    assert app.status.get() == LOOKING_UP
    assert rows(app) == [(LINK, "MP4", "Downloading")], "the link until looked up"
    assert app.downloads.selection() == (row,)
    assert app.link.get() == "", "the box empties for the next link"
    wait_until_done(app)
    assert fake.calls == [(LINK, Kind.MP4, tmp_path, None, False)]
    assert app.status.get() == done_message(Done(Path("Test video.mp4"), False))
    assert app.progress_bar.cget("value") == 100
    assert rows(app) == [("Test video", "MP4", "Done")]


def test_mp3_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    app.mp3_button.invoke()
    add(app, LINK)
    wait_until_done(app)
    assert fake.calls[0][1] == Kind.MP3


def test_quality_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    labels = [str(button.cget("text")) for button in app.quality_buttons]
    assert labels == list(QUALITIES) == ["Best", "720p", "480p"]
    assert QUALITIES[app.quality.get()] is None, "starts at Best"
    app.quality_buttons[1].invoke()
    add(app, LINK)
    wait_until_done(app)
    assert fake.calls[0][3] == 720


def test_subtitles_choice_reaches_the_download(app: App, fake: FakeDownload) -> None:
    assert str(app.subtitles_box.cget("text")) == "English subtitles"
    assert not app.subtitles.get(), "starts unticked"
    add(app, LINK)
    wait_until_done(app)
    app.subtitles_box.invoke()
    add(app, LINK)
    wait_until_done(app)
    assert [call[4] for call in fake.calls] == [False, True]


def test_video_choices_are_greyed_out_for_mp3_only(app: App) -> None:
    choices = [app.quality_label, *app.quality_buttons, app.subtitles_box]

    def greyed() -> list[bool]:
        return [widget.instate(["disabled"]) for widget in choices]

    assert greyed() == [False] * 5
    app.mp3_button.invoke()
    assert greyed() == [True] * 5
    app.mp4_button.invoke()
    assert greyed() == [False] * 5
    add(app, LINK)
    assert greyed() == [False] * 5, "usable for the next link"
    wait_until_done(app)


def test_links_download_one_after_another(app: App, fake: FakeDownload) -> None:
    fake.results[LINK] = [Failed("No.")]  # a failure doesn't stop the next one
    first = add(app, LINK)
    app.quality_buttons[1].invoke()
    app.subtitles_box.invoke()
    second = add(app, LINK2)  # while the first one runs
    app.mp3_button.invoke()  # for MP3, the quality and subtitles don't count
    third = add(app, LINK3)
    assert rows(app) == [
        (LINK, "MP4", "Downloading"),
        (LINK2, "MP4 720p, subtitles", "Waiting"),
        (LINK3, "MP3", "Waiting"),
    ]
    assert app.downloads.selection() == (first,), "the running one stays selected"
    wait_until_done(app)
    assert [call[:2] + call[3:] for call in fake.calls] == [
        (LINK, Kind.MP4, None, False),
        (LINK2, Kind.MP4, 720, True),
        (LINK3, Kind.MP3, None, False),
    ]
    assert [row[2] for row in rows(app)] == ["Failed", "Done", "Done"]
    assert app.downloads.tag_has("failed", first)
    assert not app.downloads.tag_has("failed", second)
    assert app.downloads.selection() == (third,), "each one selected as it starts"


def test_empty_link_asks_for_one(app: App, fake: FakeDownload) -> None:
    app.download_button.invoke()
    assert app.status.get() == PASTE_A_LINK
    assert fake.calls == []
    assert rows(app) == []
    assert not app.busy


def test_failure_shows_the_message(app: App, fake: FakeDownload) -> None:
    fake.events = [Progress("Joining video and audio...", None), Failed("No.")]
    add(app, LINK)
    wait_until_done(app)
    assert app.status.get() == "No."
    assert str(app.status_label.cget("foreground")) == FAILED_COLOR
    assert app.progress_bar.cget("value") == 0

    # The next message is in the normal color again.
    add(app, LINK)
    assert app.status.get() == LOOKING_UP
    assert str(app.status_label.cget("foreground")) == ""
    wait_until_done(app)


def test_selecting_a_row_shows_its_message(app: App, fake: FakeDownload) -> None:
    fake.results[LINK] = [Failed("No.")]
    fake.wait_for_cancel = {LINK2}
    failed = add(app, LINK)
    running = add(app, LINK2)
    waiting = add(app, LINK3)
    deadline = time.monotonic() + 5
    while app.status.get() != "Downloading video: 40% of 12 MB":
        assert time.monotonic() < deadline, "the second download never started"
        app.root.update()
        time.sleep(0.01)

    select(app, failed)
    assert app.status.get() == "No."
    assert str(app.status_label.cget("foreground")) == FAILED_COLOR
    assert app.progress_bar.cget("value") == 0
    select(app, waiting)
    assert app.status.get() == WAITING
    assert str(app.status_label.cget("foreground")) == ""
    select(app, running)
    assert app.progress_bar.cget("value") == 40

    select(app, failed)  # the user looks at another row
    app.cancel_button.invoke()  # selects the cancelled one, to say so
    assert app.downloads.selection() == (running,)
    assert app.status.get() == CANCELLING
    wait_until_done(app)
    assert [row[2] for row in rows(app)] == ["Failed", "Cancelled", "Done"]


def test_the_next_download_leaves_another_selected_row(
    app: App, fake: FakeDownload
) -> None:
    fake.wait_for_cancel = {LINK}
    fake.events = [Done(Path("Test video.mp4"), already_there=False)]
    done = add(app, LINK2)
    wait_until_done(app)
    add(app, LINK)
    add(app, LINK2)
    app.cancel_button.invoke()
    select(app, done)  # the user looks at the finished one
    wait_until_done(app)
    assert app.downloads.selection() == (done,), "not moved to the next one"


def test_cancel_stops_the_download(app: App, fake: FakeDownload) -> None:
    fake.events = [Progress("Downloading video: 40% of 12 MB", 40.0)]
    fake.wait_for_cancel = {LINK}
    app.mp3_button.invoke()
    add(app, LINK)
    assert not app.cancel_button.instate(["disabled"])
    # Progress reported before Cancel is still waiting to be shown: it must
    # not replace "Cancelling...".
    deadline = time.monotonic() + 5
    while app.events.empty():
        assert time.monotonic() < deadline, "the fake never reported progress"
        time.sleep(0.01)
    app.cancel_button.invoke()
    assert app.status.get() == CANCELLING
    assert rows(app)[0][2] == "Cancelling"
    assert app.cancel_button.instate(["disabled"]), "once is enough"
    wait_until_done(app)
    assert app.status.get() == CANCELLED
    assert str(app.status_label.cget("foreground")) == "", "not a failure"
    assert app.progress_bar.cget("value") == 0
    assert app.cancel_button.instate(["disabled"])
    assert app.play_button.instate(["disabled"]), "nothing to play"
    assert app.kind.get() == Kind.MP3, "choices kept"


def test_cancel_moves_on_to_the_next_link(app: App, fake: FakeDownload) -> None:
    fake.wait_for_cancel = {LINK}
    add(app, LINK)
    add(app, LINK2)
    app.cancel_button.invoke()
    wait_until_done(app)
    assert [call[0] for call in fake.calls] == [LINK, LINK2]
    assert [row[2] for row in rows(app)] == ["Cancelled", "Done"]


def test_a_broken_download_doesnt_stop_the_queue(app: App) -> None:
    def broken(
        link: str,
        kind: Kind,
        folder: Path,
        report: Report,
        height: int | None,
        subtitles: bool,
        cancel: threading.Event,
    ) -> None:
        if link == LINK:
            raise RuntimeError("boom")
        if link == LINK2:
            return  # without saying how it ended
        report(Done(Path("Test video.mp4"), already_there=False))
        if link == LINK3:
            report(Failed("A second end."))  # must not reach the next one

    app.run_download = broken
    for link in (LINK, LINK2, LINK3, "https://example.com/fourth"):
        add(app, link)
    wait_until_done(app)
    assert [row[2] for row in rows(app)] == ["Failed", "Failed", "Done", "Done"]
    select(app, app.downloads.get_children()[0])
    assert app.status.get() == "Something went wrong: boom"
    select(app, app.downloads.get_children()[1])
    assert app.status.get() == NO_END


def test_remove_takes_a_row_out_of_the_list(
    app: App, fake: FakeDownload, tmp_path: Path
) -> None:
    video = tmp_path / "Test video.mp4"
    video.write_bytes(b"")
    fake.events = [Done(video, already_there=False)]
    fake.wait_for_cancel = {LINK}
    done = add(app, LINK2)
    wait_until_done(app)
    running = add(app, LINK)
    waiting = add(app, LINK2)
    assert app.remove_button.instate(["disabled"]), "not the running one"
    app.remove_button.invoke()
    assert len(rows(app)) == 3

    select(app, waiting)
    app.remove_button.invoke()
    assert app.downloads.get_children() == (done, running)
    assert app.downloads.selection() == (running,), "the running one again"
    select(app, done)
    app.remove_button.invoke()
    assert video.is_file(), "the file stays"
    app.cancel_button.invoke()
    wait_until_done(app)
    assert [call[0] for call in fake.calls] == [LINK2, LINK], "the removed one waits"

    select(app, running)  # nothing runs now: nothing selected afterwards
    app.remove_button.invoke()
    assert (rows(app), app.downloads.selection()) == ([], ())
    assert app.status.get() == ""
    assert app.remove_button.instate(["disabled"])


def test_play_and_show_in_folder_open_the_selected_row(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    app.play_button.invoke()  # greyed out: does nothing
    app.show_button.invoke()
    assert files.calls == [("open_folder", tmp_path)], "no download yet: the folder"

    video = tmp_path / "Test video.mp4"
    video.write_bytes(b"")
    fake.events = [Done(video, already_there=False)]
    fake.results[LINK2] = [Progress("Downloading video: 40% of 12 MB", 40.0)]
    fake.wait_for_cancel = {LINK2}
    done = add(app, LINK)
    assert app.play_button.instate(["disabled"]), "not downloaded yet"
    wait_until_done(app)
    app.play_button.invoke()
    app.show_button.invoke()
    assert files.calls[1:] == [("play", video), ("show", video)]

    add(app, LINK2)  # selected while it runs: nothing to play or show yet
    assert app.play_button.instate(["disabled"])
    app.show_button.invoke()
    assert files.calls[3:] == [("open_folder", tmp_path)]
    select(app, done)  # the finished one plays meanwhile
    app.play_button.invoke()
    assert files.calls[4:] == [("play", video)]
    app.cancel_button.invoke()
    wait_until_done(app)


def test_after_a_failure_play_is_greyed_out_again(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    video = tmp_path / "Test video.mp4"
    video.write_bytes(b"")
    fake.events = [Done(video, already_there=True)]
    there = add(app, LINK)
    wait_until_done(app)
    assert not app.play_button.instate(["disabled"]), "a file already there plays"
    assert rows(app) == [("Test video", "MP4", "Already there")], "no title: the name"
    fake.events = [Failed("No.")]
    add(app, LINK)
    wait_until_done(app)
    assert app.play_button.instate(["disabled"]), "the earlier file is not played"
    app.show_button.invoke()
    assert files.calls == [("open_folder", tmp_path)]
    select(app, there)
    assert not app.play_button.instate(["disabled"]), "its own row still plays"


def test_a_moved_or_deleted_file_is_not_opened(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    video = tmp_path / "Test video.mp4"  # never written: it is gone
    fake.events = [Done(video, already_there=False)]
    add(app, LINK)
    wait_until_done(app)
    app.play_button.invoke()
    folder = shown_folder(tmp_path)
    assert app.status.get() == GONE.format(name=video.name, folder=folder)
    assert app.status.get().startswith("Can't play Test video.mp4: it isn't in ")
    assert str(app.status_label.cget("foreground")) == FAILED_COLOR
    assert app.play_button.instate(["disabled"]), "said once, then greyed out"
    assert rows(app)[0][2] == "Done", "the download itself worked"
    app.show_button.invoke()
    assert files.calls == [("open_folder", tmp_path)], "the folder instead"


def test_a_row_names_the_video_and_its_choices() -> None:
    job = Job(LINK, Kind.MP4, 480, True)
    assert job.row() == (LINK, "MP4 480p, subtitles", "Waiting")
    job.state, job.percent, job.title = State.DOWNLOADING, 12.4, "A cat"
    assert job.row() == ("A cat", "MP4 480p, subtitles", "Downloading 12%")
    job.percent = None  # joining or converting
    assert job.row()[2] == "Downloading"
    assert Job(LINK, Kind.MP3, None, False).row() == (LINK, "MP3", "Waiting")


def test_a_title_with_odd_characters_shows_as_it_is(
    app: App, fake: FakeDownload
) -> None:
    title = 'Cats {and} "dogs" \\ [1] $x ; {'
    fake.events = [Progress("Downloading: 1%", 1.0, title), Failed("No.")]
    add(app, LINK)
    wait_until_done(app)
    assert rows(app) == [(title, "MP4", "Failed")]


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
    assert app.downloads.bind("<Delete>")  # Remove
    assert app.downloads.bind("<Double-Button-1>")  # Play
