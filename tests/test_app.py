import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_downloader import handoff
from video_downloader.app import (
    ASK_ABOVE,
    CANCELLED,
    CANCELLING,
    CHECK_EVERY,
    FAILED_COLOR,
    GONE,
    HISTORY_SIZE,
    LINK_RECEIVED,
    LOOKING_UP,
    NO_END,
    NO_SUBTITLES,
    PASTE_A_LINK,
    QUALITIES,
    TITLE,
    WAITING,
    WIDTH,
    App,
    Files,
    Job,
    State,
    done_message,
    load_history,
    main,
    save_history,
    show_command,
    shown_folder,
    start,
    window_width,
)
from video_downloader.downloader import (
    NOT_AVAILABLE,
    Cancelled,
    Confirm,
    Done,
    Event,
    Failed,
    Kind,
    Playlist,
    Progress,
    Report,
)
from video_downloader.handoff import Answer, Choices, Message

LINK = "https://example.com/video"
LINK2 = "https://example.com/second"
LINK3 = "https://example.com/third"


class FakeDownload:
    """Stands in for yt-dlp: reports the link's events in `results` (or else
    `events`) at once and remembers the calls. A link in `wait_for_cancel`
    reports only their progress, then waits for Cancel and reports
    Cancelled (with a playlist's videos in `kept`): one download's last
    report must be its only end. A link in `playlists` (its title and number
    of videos) asks `confirm` first, remembering the answer in `answers`;
    after a no it reports Cancelled only."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Kind, Path, int | None, bool]] = []
        self.events: list[Event] = [
            Progress("Downloading video: 40% of 12 MB", 40.0),
            Done(Path("Test video.mp4"), already_there=False),
        ]
        self.results: dict[str, list[Event]] = {}
        self.wait_for_cancel: set[str] = set()
        self.kept: tuple[Path, ...] = ()
        self.playlists: dict[str, tuple[str, int]] = {}
        self.answers: list[bool] = []

    def __call__(
        self,
        link: str,
        kind: Kind,
        folder: Path,
        report: Report,
        height: int | None,
        subtitles: bool,
        cancel: threading.Event,
        confirm: Confirm,
    ) -> None:
        self.calls.append((link, kind, folder, height, subtitles))
        if link in self.playlists:
            self.answers.append(confirm(*self.playlists[link]))
            if not self.answers[-1]:
                report(Cancelled())
                return
        until_cancelled = link in self.wait_for_cancel
        for event in self.results.get(link, self.events):
            if isinstance(event, Progress) or not until_cancelled:
                report(event)
        if until_cancelled and cancel.wait(timeout=5):
            report(Cancelled(self.kept))


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


def saved(history: Path) -> list[Job]:
    """What the history file holds; it has to be readable."""
    jobs = load_history(history)
    assert jobs is not None, "the history couldn't be read"
    return jobs


@contextmanager
def next_session(app: App) -> Iterator[App]:
    """A new window with the app's download, folder, files and history: what
    the user sees when they open the app again."""
    root = tk.Tk()
    root.withdraw()
    try:
        yield App(root, app.run_download, app.folder, app.files, app.history)
    finally:
        root.destroy()


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


def test_window_has_the_chrome_buttons_icon(app: App) -> None:
    sizes = [(icon.width(), icon.height()) for icon in app.icons]
    assert sizes == [(16, 16), (32, 32), (48, 48), (128, 128)]
    # Tk gives Windows the 32 px image: blue left of the arrow (#2563eb).
    assert app.icons[1].get(4, 16) == (0x25, 0x63, 0xEB)


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


def test_cancel_during_a_playlist_plays_its_finished_videos(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    first = tmp_path / "My list" / "First.mp4"
    first.parent.mkdir()
    first.write_bytes(b"a video")
    fake.wait_for_cancel = {LINK}
    fake.kept = (first, first.with_name("Second.mp4"))
    add(app, LINK)
    app.cancel_button.invoke()
    wait_until_done(app)
    folder = shown_folder(first.parent)
    assert app.status.get() == (
        f"Cancelled. Kept the 2 videos already finished (in {folder})."
    )
    assert rows(app)[0][2] == "Cancelled"
    app.play_button.invoke()
    assert files.calls == [("play", first)]
    # Like every cancelled download, not kept in the history.
    assert load_history(app.history) == []


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
        confirm: Confirm,
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


def test_saved_files_are_in_the_list_next_time(
    app: App, fake: FakeDownload, files: FakeFiles, tmp_path: Path
) -> None:
    title = "Ünï “video” {1} [x] $y"
    video, audio = tmp_path / f"{title}.mp4", tmp_path / "Song.mp3"
    video.write_bytes(b"")
    fake.results = {
        LINK: [Progress("Downloading: 50%", 50.0, title), Done(video, False)],
        LINK2: [Failed("No video here.")],
        LINK3: [Done(audio, already_there=True)],
    }
    add(app, LINK)
    app.mp3_button.invoke()
    add(app, LINK2)
    add(app, LINK3)
    wait_until_done(app)

    with next_session(app) as again:
        assert rows(again) == [(title, "MP4", "Done"), ("Song", "MP3", "Already there")]
        assert (again.downloads.selection(), again.status.get()) == ((), "")
        assert again.remove_button.instate(["disabled"]), "nothing selected"
        past = again.downloads.get_children()[0]
        select(again, past)
        assert again.status.get() == done_message(Done(video, False))
        assert again.progress_bar.cget("value") == 100
        again.play_button.invoke()
        again.show_button.invoke()
        assert files.calls == [("play", video), ("show", video)]

        add(again, LINK)
        wait_until_done(again)
        assert rows(again)[2] == (title, "MP4", "Done"), "a new row below the past"
    assert len(saved(app.history)) == 3


def test_remove_takes_a_row_out_of_the_history(app: App, tmp_path: Path) -> None:
    video, gone = tmp_path / "Kept.mp4", tmp_path / "Gone.mp4"
    video.write_bytes(b"")
    save_history(
        app.history,
        [
            Job(LINK, Kind.MP4, 720, True, State.DONE, "Kept", "Done.", file=video),
            Job(LINK2, Kind.MP4, None, False, State.DONE, "Gone", "Done.", file=gone),
            Job(LINK3, Kind.MP3, None, False, State.DONE, "Removed", file=video),
        ],
    )
    with next_session(app) as again:
        assert rows(again)[0] == ("Kept", "MP4 720p, subtitles", "Done")
        kept, gone_row, removed = again.downloads.get_children()
        select(again, gone_row)
        again.play_button.invoke()  # Play finds it gone: left out from now on
        titles = [job.title for job in saved(app.history)]
        assert titles == ["Kept", "Removed"], "saved at once"
        select(again, removed)
        again.remove_button.invoke()
        assert video.is_file(), "Remove never deletes a file"
        assert again.downloads.get_children() == (kept, gone_row)
    assert [job.title for job in saved(app.history)] == ["Kept"]


def test_the_history_keeps_the_newest_downloads(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    jobs = [
        Job(f"{LINK}/{n}", Kind.MP3, None, False, State.DONE, file=Path(f"{n}.mp3"))
        for n in range(HISTORY_SIZE + 1)
    ]
    jobs.insert(5, Job(LINK, Kind.MP4, None, False, State.FAILED))
    jobs.insert(7, Job(LINK, Kind.MP4, None, False, State.CANCELLED))
    save_history(history, jobs)
    kept = saved(history)
    assert len(kept) == HISTORY_SIZE, "only saved files, the newest 200"
    assert (kept[0].link, kept[-1].link) == (f"{LINK}/1", f"{LINK}/{HISTORY_SIZE}")
    assert kept[0] == Job(
        f"{LINK}/1", Kind.MP3, None, False, State.DONE, percent=100, file=Path("1.mp3")
    )
    assert not history.with_name("history.json.new").exists()


def test_a_missing_or_broken_history_is_an_empty_one(app: App, tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    assert load_history(history) == [], "not there yet"
    for broken in (b"{", b"\xff\xfe\x00", b'{"link": "x"}', b"[1, null]"):
        history.write_bytes(broken)
        assert load_history(history) == [], broken
    good = {
        "link": LINK,
        "kind": "mp4",
        "height": 480,
        "subtitles": False,
        "title": "Fine",
        "state": "Already there",
        "message": "Already there.",
        "file": str(tmp_path / "Fine.mp4"),
    }
    bad = [
        {**good, "state": "Failed"},
        {**good, "kind": "avi"},
        {**good, "height": "480"},
        {key: value for key, value in good.items() if key != "file"},
    ]
    history.write_text(json.dumps([*bad, good]), encoding="utf-8")
    assert [job.title for job in saved(history)] == ["Fine"]

    app.history.write_text("{", encoding="utf-8")
    with next_session(app) as again:
        assert rows(again) == []
        add(again, LINK)
        wait_until_done(again)
    assert len(saved(app.history)) == 1, "the next save writes it anew"


def test_a_failed_save_doesnt_stop_the_queue(
    app: App,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    in_the_way = tmp_path / "a file, not a folder"
    in_the_way.write_bytes(b"")
    app.history = in_the_way / "history.json"
    add(app, LINK)
    add(app, LINK2)
    wait_until_done(app)
    assert [row[2] for row in rows(app)] == ["Done", "Done"], "the next one ran"
    assert "FileExistsError" in capsys.readouterr().err, "the details, in the terminal"

    def not_text(self: Path, *args: object, **kwargs: object) -> int:
        raise UnicodeEncodeError("utf-8", "\udc80", 0, 1, "surrogates not allowed")

    monkeypatch.setattr(Path, "write_text", not_text)
    app.history = tmp_path / "history.json"
    add(app, LINK)
    add(app, LINK2)
    wait_until_done(app)
    assert [row[2] for row in rows(app)] == ["Done"] * 4, "the next one ran"
    assert "UnicodeEncodeError" in capsys.readouterr().err


def test_a_locked_history_is_not_written_over(
    app: App, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    old = Job(LINK, Kind.MP4, None, False, State.DONE, "Old", file=Path("Old.mp4"))
    save_history(app.history, [old])
    before = app.history.read_bytes()

    def locked(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "In use by another program", str(self))

    monkeypatch.setattr(Path, "read_text", locked)
    with next_session(app) as again:
        assert rows(again) == []
        add(again, LINK)
        wait_until_done(again)
        assert rows(again) == [("Test video", "MP4", "Done")]
    assert app.history.read_bytes() == before, "its downloads are still there"
    assert "PermissionError" in capsys.readouterr().err


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
    assert done_message(Done(path, True, no_subtitles=True)) == (
        f"Already there, not downloaded again: Clip.mp4 (in {folder}). {NO_SUBTITLES}"
    )


def test_playlist_messages_count_the_videos() -> None:
    first = Path.home() / "Downloads" / "Videos" / "My list" / "First.mp4"
    folder = Path("Downloads") / "Videos" / "My list"

    def message(playlist: Playlist, already_there: bool = False) -> str:
        return done_message(Done(first, already_there, playlist=playlist))

    assert message(Playlist(12, 12, 0)) == f"Done: 12 of 12 videos saved (in {folder})."
    assert message(Playlist(12, 10, 1, why=NOT_AVAILABLE)) == (
        f"Done: 10 of 12 videos saved, 1 was already there, 1 failed (in {folder}). "
        f"Why the first failed: {NOT_AVAILABLE}"
    )
    assert message(Playlist(3, 1, 2, no_subtitles=2)) == (
        f"Done: 1 of 3 videos saved, 2 were already there (in {folder}). "
        "No English subtitles for 2 of the videos."
    )
    assert message(Playlist(2, 0, 2), already_there=True) == (
        f"Already there, not downloaded again: 2 of 2 videos (in {folder})."
    )
    assert message(Playlist(3, 0, 2), already_there=True) == (
        f"Already there, not downloaded again: 2 of 3 videos, 1 failed (in {folder})."
    )
    assert message(Playlist(1, 1, 0)) == f"Done: 1 of 1 video saved (in {folder})."


def test_enter_is_bound_on_the_link_box(app: App) -> None:
    # A hidden window gets no key presses, so pressing Enter for real is
    # left to the GUI test (To do 2); here, check the binding is there.
    assert app.link_entry.bind("<Return>")
    assert not app.root.bind("<Return>")
    assert app.downloads.bind("<Delete>")  # Remove
    assert app.downloads.bind("<Double-Button-1>")  # Play


@pytest.fixture
def to_front(monkeypatch: pytest.MonkeyPatch) -> list[tk.Tk]:
    """Record bring_to_front() instead of showing the hidden window (the GUI
    test brings the real one to the front)."""
    calls: list[tk.Tk] = []
    monkeypatch.setattr("video_downloader.app.bring_to_front", calls.append)
    return calls


class FakeBox:
    """Stands in for the Yes/No box: remembers its texts and gives `answer`."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.texts: list[str] = []

    def __call__(self, root: tk.Tk, text: str) -> bool:
        self.texts.append(text)
        return self.answer


@pytest.mark.parametrize("answer", [True, False], ids=["yes", "no"])
def test_a_big_playlist_asks_first_with_the_window_in_front(
    app: App, fake: FakeDownload, to_front: list[tk.Tk], answer: bool
) -> None:
    box = app.ask = FakeBox(answer)
    fake.playlists[LINK] = ("My channel - Videos", 1234)
    add(app, LINK)
    wait_until_done(app)
    text = "“My channel - Videos” has 1,234 videos. Download all of them?"
    assert box.texts == [text]
    assert to_front == [app.root], "a download from Chrome runs in the background"
    assert fake.answers == [answer]
    if answer:
        assert rows(app)[0][2] == "Done"
    else:
        assert rows(app)[0][2] == "Cancelled"
        assert app.status.get() == CANCELLED
        assert app.play_button.instate(["disabled"]), "nothing saved"


@pytest.mark.parametrize(
    ("title", "count", "text"),
    [
        ("Small list", ASK_ABOVE, None),
        ("", ASK_ABOVE + 1, "This playlist has 51 videos. Download all of them?"),
    ],
    ids=["up to 50: no box", "above 50, no title"],
)
def test_only_a_playlist_above_50_videos_asks(
    app: App,
    fake: FakeDownload,
    to_front: list[tk.Tk],
    title: str,
    count: int,
    text: str | None,
) -> None:
    box = app.ask = FakeBox(True)
    fake.playlists[LINK] = (title, count)
    add(app, LINK)
    wait_until_done(app)
    assert box.texts == ([text] if text else [])
    assert len(to_front) == len(box.texts)
    assert fake.answers == [True]


def test_a_big_playlist_waiting_its_turn_asks_too(
    app: App, fake: FakeDownload, to_front: list[tk.Tk]
) -> None:
    # It asks as soon as it starts, while the check that saw the first one
    # end is still running (code review: that check asked with the ended row).
    box = app.ask = FakeBox(True)
    fake.playlists[LINK2] = ("My channel - Videos", 1234)
    add(app, LINK)
    add(app, LINK2)
    wait_until_done(app)
    assert len(box.texts) == 1
    assert fake.answers == [True]
    assert [row[2] for row in rows(app)] == ["Done", "Done"]


def test_after_cancel_a_question_gets_no_without_a_box(
    app: App, to_front: list[tk.Tk]
) -> None:
    answers: list[bool] = []

    def listing(
        link: str,
        kind: Kind,
        folder: Path,
        report: Report,
        height: int | None,
        subtitles: bool,
        cancel: threading.Event,
        confirm: Confirm,
    ) -> None:
        # Cancel while yt-dlp lists the playlist, before it can act.
        cancel.wait(timeout=5)
        answers.append(confirm("My channel - Videos", 1234))
        report(Cancelled())

    app.run_download = listing
    box = app.ask = FakeBox(True)
    add(app, LINK)
    app.cancel_button.invoke()
    wait_until_done(app)
    assert answers == [False]
    assert box.texts == [] and to_front == []
    assert app.status.get() == CANCELLED


def test_a_received_link_replaces_the_box_and_waits(
    app: App, fake: FakeDownload, to_front: list[tk.Tk]
) -> None:
    assert app.listening is None, "no pipe given: it doesn't listen"
    app.link.set("half a typed link")
    app.receive_link(LINK)
    assert app.link.get() == LINK
    assert app.status.get() == LINK_RECEIVED
    assert to_front == [app.root]
    app.root.update()
    assert fake.calls == [], "it waits for Download: MP4 or MP3 is chosen first"
    assert not app.busy


def test_the_app_started_again_brings_the_window_to_the_front(
    app: App, to_front: list[tk.Tk]
) -> None:
    app.link.set("half a typed link")
    app.received.put(handoff.SHOW)
    app.check_links()
    assert to_front == [app.root]
    assert app.link.get() == "half a typed link", "the box stays as it was"
    app.root.after_cancel(app.next_link_check)  # one check at a time, as in the app
    app.received.put(handoff.SHOW)
    app.received.put(Message(LINK))
    app.check_links()
    assert to_front == [app.root, app.root], "once for both"
    assert app.link.get() == LINK


def test_a_link_sent_to_the_pipe_reaches_the_window(
    fake: FakeDownload,
    files: FakeFiles,
    tmp_path: Path,
    pipe: str,
    to_front: list[tk.Tk],
) -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        window = App(root, fake, tmp_path, files, listening=handoff.listen(pipe))
        assert window.listening is not None
        assert handoff.send(LINK, pipe)
        deadline = time.monotonic() + 5
        while window.link.get() != LINK:
            assert time.monotonic() < deadline, "the link never arrived"
            root.update()
            time.sleep(0.01)
        assert window.status.get() == LINK_RECEIVED
        assert to_front == [root]
    finally:
        root.destroy()
    assert not handoff.send(LINK, pipe), "a closed window stops listening"


def test_a_received_download_joins_the_list_and_leaves_the_window_alone(
    app: App, fake: FakeDownload, tmp_path: Path, to_front: list[tk.Tk]
) -> None:
    app.link.set("half a typed link")
    app.quality_buttons[2].invoke()  # 480p in the window
    app.received.put(Message(LINK, Choices("mp4", "720p", True)))
    app.check_links()
    assert rows(app) == [(LINK, "MP4 720p, subtitles", "Downloading")]
    assert app.downloads.selection() == app.downloads.get_children(), (
        "nothing was downloading: it is selected, as with Download"
    )
    assert app.link.get() == "half a typed link", "the box stays as it was"
    assert (app.kind.get(), app.quality.get(), app.subtitles.get()) == (
        "mp4",
        "480p",
        False,
    ), "the window's choices stay as they were"
    assert to_front == [], "the window stays where it is"
    wait_until_done(app)
    assert fake.calls == [(LINK, Kind.MP4, tmp_path, 720, True)]


def test_downloads_received_in_one_check_all_run_in_order(
    app: App, fake: FakeDownload, to_front: list[tk.Tk]
) -> None:
    first = add(app, LINK)  # running: the received ones wait their turn
    app.received.put(Message(LINK2, Choices("mp3", "720p", True)))
    app.received.put(Message("https://example.com/box-1"))
    app.received.put(Message(LINK3, Choices("mp4")))
    app.received.put(Message("https://example.com/box-2"))
    app.check_links()
    assert rows(app) == [
        (LINK, "MP4", "Downloading"),
        (LINK2, "MP3", "Waiting"),  # MP3: the quality and subtitles don't count
        (LINK3, "MP4", "Waiting"),
    ]
    assert app.downloads.selection() == (first,), "the running one stays selected"
    assert app.link.get() == "https://example.com/box-2", "the newest link alone"
    assert to_front == [app.root], "the link alone brings it to the front"
    wait_until_done(app)
    assert [call[:2] + call[3:] for call in fake.calls] == [
        (LINK, Kind.MP4, None, False),
        (LINK2, Kind.MP3, None, False),
        (LINK3, Kind.MP4, None, False),
    ]


def test_a_cancel_from_outside_stops_its_link_only(
    app: App, fake: FakeDownload
) -> None:
    """The running one as Cancel does; waiting ones, also one in the list
    twice, become Cancelled and are skipped. Other links and the selection
    stay as they were."""
    fake.wait_for_cancel = {LINK}
    add(app, LINK)
    add(app, LINK2)
    app.mp3_button.invoke()
    add(app, LINK2)  # the same page again, as MP3
    other = add(app, LINK3)
    select(app, other)

    def states() -> list[State]:
        return [job.state for job in app.jobs.values()]

    assert app.cancel_link(LINK2) is Answer.CANCELLED
    assert states() == [
        State.DOWNLOADING,
        State.CANCELLED,
        State.CANCELLED,
        State.WAITING,
    ]
    assert app.cancel_link(LINK) is Answer.CANCELLED
    assert states()[0] is State.CANCELLING
    assert app.downloads.selection() == (other,), "unlike the Cancel button"
    assert app.cancel_link(LINK) is Answer.CANCELLED, "it is cancelling already"
    wait_until_done(app)
    assert [call[0] for call in fake.calls] == [LINK, LINK3]
    assert [row[2] for row in rows(app)] == [
        "Cancelled",
        "Cancelled",
        "Cancelled",
        "Done",
    ]
    select(app, app.downloads.get_children()[1])
    assert app.status.get() == CANCELLED


def test_a_cancel_from_outside_with_nothing_to_cancel(
    app: App, fake: FakeDownload
) -> None:
    assert app.cancel_link(LINK) is Answer.NOTHING, "an empty list"
    fake.results[LINK2] = [Failed("It broke.")]
    add(app, LINK)
    add(app, LINK2)
    wait_until_done(app)
    assert app.cancel_link(LINK) is Answer.NOTHING, "done: the file stays"
    assert app.cancel_link(LINK2) is Answer.NOTHING, "failed"
    assert app.cancel_link(LINK3) is Answer.NOTHING, "not in the list"
    assert [row[2] for row in rows(app)] == ["Done", "Failed"]


@contextmanager
def listening_window(
    fake: FakeDownload, files: FakeFiles, folder: Path, pipe: str
) -> Iterator[App]:
    """A hidden window that listens on `pipe`."""
    root = tk.Tk()
    root.withdraw()
    try:
        window = App(root, fake, folder, files, listening=handoff.listen(pipe))
        assert window.listening is not None
        yield window
    finally:
        root.destroy()


def run_for(app: App, seconds: float) -> None:
    """Let the window run, as its mainloop would."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.01)


def test_a_cancel_sent_to_the_pipe_gets_the_windows_answer(
    fake: FakeDownload, files: FakeFiles, tmp_path: Path, pipe: str
) -> None:
    fake.wait_for_cancel = {LINK}
    with listening_window(fake, files, tmp_path, pipe) as window:
        add(window, LINK)
        answers: list[Answer] = []

        def cancel_two() -> None:  # as the helper does, from another process
            answers.append(handoff.cancel(LINK, pipe))
            answers.append(handoff.cancel(LINK2, pipe))

        sender = threading.Thread(target=cancel_two)
        sender.start()
        deadline = time.monotonic() + 5
        while sender.is_alive():
            assert time.monotonic() < deadline, "the window never answered"
            run_for(window, 0.01)
        assert answers == [Answer.CANCELLED, Answer.NOTHING]
        wait_until_done(window)
        assert rows(window)[0][2] == "Cancelled"


def test_a_cancel_the_window_cant_answer_in_time_is_withdrawn(
    fake: FakeDownload,
    files: FakeFiles,
    tmp_path: Path,
    pipe: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sender is told "no answer", so the Cancel mustn't happen later."""
    monkeypatch.setattr("video_downloader.app.ANSWER_WITHIN", 0.2)
    fake.wait_for_cancel = {LINK}
    with listening_window(fake, files, tmp_path, pipe) as window:
        row = add(window, LINK)
        # The window doesn't run meanwhile: it is stuck.
        assert handoff.cancel(LINK, pipe) is Answer.NO_ANSWER
        run_for(window, 3 * CHECK_EVERY / 1000)  # it runs again
        assert window.jobs[row].state is State.DOWNLOADING
        window.cancel_button.invoke()
        wait_until_done(window)


def test_start_puts_a_link_in_the_box(
    fake: FakeDownload, files: FakeFiles, tmp_path: Path, to_front: list[tk.Tk]
) -> None:
    window = start(fake, tmp_path, files, tmp_path / "history.json", link=LINK)
    try:
        assert window.link.get() == LINK
        assert window.status.get() == LINK_RECEIVED
    finally:
        window.root.destroy()


def test_start_with_choices_downloads_in_a_minimized_window(
    fake: FakeDownload, files: FakeFiles, tmp_path: Path, to_front: list[tk.Tk]
) -> None:
    window = start(
        fake, tmp_path, files, tmp_path / "history.json", None, LINK, Choices("mp3")
    )
    try:
        window.root.update()
        assert window.root.state() == "iconic"
        assert rows(window) == [(LINK, "MP3", "Downloading")]
        assert window.link.get() == "", "not in the box"
        assert to_front == []
        wait_until_done(window)
        assert fake.calls[0][:2] == (LINK, Kind.MP3)
    finally:
        window.root.destroy()


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, object]]]:
    """Record the windows main() opens instead of opening them. The pipe each
    one took stays taken until the test ends, as by a window still being
    built (it reads only once it is built)."""
    calls: list[dict[str, object]] = []

    def fake_start(**options: object) -> SimpleNamespace:
        calls.append(options)
        return SimpleNamespace(root=SimpleNamespace(mainloop=lambda: None))

    monkeypatch.setattr("video_downloader.app.start", fake_start)
    yield calls
    for options in calls:
        if isinstance(listening := options["listening"], handoff.Listening):
            listening.close()


def took_the_pipe(options: dict[str, object]) -> bool:
    """The window main() opened took handoff.PIPE (the test's own,
    conftest.py), so it gets what is sent there."""
    listening = options["listening"]
    return isinstance(listening, handoff.Listening) and listening.pipe == handoff.PIPE


@contextmanager
def open_window_on(pipe: str) -> Iterator[queue.Queue[Message]]:
    """A window that is open already and listens on `pipe`; what it gets goes
    into the queue."""
    listening = handoff.listen(pipe)
    assert listening is not None
    received: queue.Queue[Message] = queue.Queue()
    listening.start(received.put)
    try:
        yield received
    finally:
        listening.close()


def test_main_hands_everything_to_the_open_window(
    opened: list[dict[str, object]],
) -> None:
    with open_window_on(handoff.PIPE) as received:
        main([f" {LINK} "])
        main([LINK, "--download", "mp4", "--quality", "720p", "--subtitles"])
        main(["--download", "mp3", LINK])
        main([])  # the app started again: the open window to the front
        got = [received.get(timeout=5) for _ in range(4)]
    assert got == [
        Message(LINK),
        Message(LINK, Choices("mp4", "720p", True)),
        Message(LINK, Choices("mp3", "Best", False)),
        handoff.SHOW,
    ]
    assert opened == [], "no second window"


@pytest.mark.parametrize(
    ("arguments", "choices"),
    [([LINK], None), ([LINK, "--download", "mp3"], Choices("mp3"))],
    ids=["link", "download"],
)
def test_main_opens_a_window_with_the_link_when_none_is_open(
    arguments: list[str], choices: Choices | None, opened: list[dict[str, object]]
) -> None:
    main(arguments)
    [options] = opened
    assert took_the_pipe(options)
    assert (options["link"], options["choices"]) == (LINK, choices)


def test_main_without_a_link_opens_an_empty_window(
    monkeypatch: pytest.MonkeyPatch, opened: list[dict[str, object]]
) -> None:
    def fake_show(pipe: str) -> bool:
        raise AssertionError("no window to bring to the front")

    monkeypatch.setattr(handoff, "show", fake_show)
    main([])
    [options] = opened
    assert took_the_pipe(options)
    assert (options["link"], options["choices"]) == ("", None)


def test_two_windows_started_at_once_end_in_one(
    opened: list[dict[str, object]],
    fake: FakeDownload,
    files: FakeFiles,
    tmp_path: Path,
) -> None:
    """Download in the Chrome popup on two tabs, with no window open: the
    second starts while the first, which took the pipe, is still being
    built. It hands its download over, and the first window, once built,
    downloads both, its own first."""
    main([LINK, "--download", "mp4"])
    main([LINK2, "--download", "mp3"])
    [options] = opened
    assert options == {
        "listening": options["listening"],
        "link": LINK,
        "choices": Choices("mp4"),
    }
    listening = options["listening"]
    assert took_the_pipe(options) and isinstance(listening, handoff.Listening)
    history = tmp_path / "history.json"
    window = start(fake, tmp_path, files, history, listening, LINK, Choices("mp4"))
    try:
        deadline = time.monotonic() + 5
        while len(fake.calls) < 2:
            assert time.monotonic() < deadline, "the second download never came"
            window.root.update()
            time.sleep(0.01)
        assert [call[:2] for call in fake.calls] == [
            (LINK, Kind.MP4),
            (LINK2, Kind.MP3),
        ]
    finally:
        window.root.destroy()


@pytest.mark.parametrize("closing", [True, False], ids=["closing", "stuck"])
def test_main_when_handing_over_fails(
    closing: bool, monkeypatch: pytest.MonkeyPatch, opened: list[dict[str, object]]
) -> None:
    """The open window was closing: the new one takes its pipe. It is stuck:
    the new one opens all the same, without listening."""
    other = handoff.listen(handoff.PIPE)
    assert other is not None

    def fails(link: str, pipe: str, start: Choices | None = None) -> bool:
        if closing:
            other.close()
        return False

    monkeypatch.setattr(handoff, "send", fails)
    try:
        main([LINK])
    finally:
        other.close()
    [options] = opened
    assert took_the_pipe(options) is closing
    assert options["link"] == LINK


def test_main_opens_a_window_when_the_pipe_cant_be_made(
    monkeypatch: pytest.MonkeyPatch, opened: list[dict[str, object]]
) -> None:
    too_long = r"\\.\pipe" + "\\" + "x" * 300  # Windows allows 256 characters
    monkeypatch.setattr(handoff, "PIPE", too_long)
    main([LINK])
    assert opened == [{"listening": None, "link": LINK, "choices": None}]


@pytest.mark.parametrize(
    "arguments",
    [["--download", "mp3"], [LINK, "--download", "avi"], [LINK, "--quality", "1080p"]],
)
def test_main_refuses_a_download_without_a_link_or_known_choices(
    arguments: list[str],
    opened: list[dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(arguments)
    assert opened == []
    assert "error" in capsys.readouterr().err
