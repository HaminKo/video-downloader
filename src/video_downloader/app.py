"""The main window: a link box, Download and Cancel buttons, MP4 or MP3, the
video quality, English subtitles, the list of downloads, progress, a status
line, and Play, Show in folder and Remove buttons. Under them, once the
built app has downloaded a newer yt-dlp for its next start, a line says so,
with a Restart now button.

Links wait in the list and download one after another. The bar, the status
line and the buttons under them are about the selected row. The list starts
with the past downloads from the history file.

A link sent from outside (`python -m video_downloader LINK`, or the Chrome
button's helper, host.py) goes into the link box of the window that is open
already, through a named pipe (handoff.py); it doesn't start by itself. A
link sent with the choices to download it with (`--download mp3`) joins the
list instead, and leaves the box, the window's choices and its place alone;
with no window open, one opens minimized with it downloading. A Cancel sent
(the Chrome popup's) stops that link's download, and the window answers
whether it did. There is only ever one window: the app started again with
no link brings the open one to the front (main())."""

import argparse
import contextlib
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from collections.abc import Callable, Iterable
from concurrent.futures import Future
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tkinter import font, messagebox, ttk

from video_downloader import downloader, handoff, host, places, ytdlp_update
from video_downloader.browser import EXTENSION_FOLDER
from video_downloader.downloader import (
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

TITLE = "Video Downloader"

# The window's icon: the Chrome button's, one PNG per size. Tk gives Windows
# the 32 px one for the taskbar and Alt+Tab, scaled down for the title bar
# (docs/research/window-icon.md).
ICONS = EXTENSION_FOLDER / "icons"
ICON_SIZES = (16, 32, 48, 128)

# The app's own ID for Windows' taskbar: without it, the window joins
# Python's taskbar button and shows Python's icon (measured). Also the name
# of the mutex the open window holds for Setup (main()).
APP_ID = "VideoDownloader.App"
PASTE_A_LINK = "Paste a link to a video first."
LOOKING_UP = "Looking up the video..."
CANCELLING = "Cancelling..."
CANCELLED = "Cancelled."
WAITING = "Waiting: starts when the downloads above it have ended."
NO_END = "Something went wrong: the download stopped without saying why."
# A cancelled playlist whose first videos were finished.
KEPT = "Cancelled. Kept the {videos} already finished (in {folder})."
NO_SUBTITLES = "No English subtitles found."
SOME_WITHOUT_SUBTITLES = "No English subtitles for {count} of the videos."
GONE = "Can't play {name}: it isn't in {folder} anymore."
LINK_RECEIVED = "Link received: choose MP4 or MP3, then Download."
# Under everything else, once the built app has downloaded a newer yt-dlp
# (look_for_update()), next to the Restart now button.
UPDATED = "yt-dlp was updated to {version}. Restart the app to use it."

# A playlist with more videos than this is downloaded only after a Yes in a
# box (ask_yes_no()): a channel can have thousands.
ASK_ABOVE = 50
MANY_VIDEOS = "{playlist} has {count:,} videos. Download all of them?"

# The video quality choices and their limit as the downloader takes it
# (handoff.py, which the Chrome button's helper shares them from).
QUALITIES = handoff.QUALITIES

# Failures are shown in dark red, everything else in the normal text color.
FAILED_COLOR = "#a00000"

# The width the window opens with, which is also its smallest, in pixels at
# 100% display scaling (96 DPI). window_width() scales it to the display.
WIDTH = 600

# How often the window checks for news from the download, and for links sent
# from outside, in milliseconds.
CHECK_EVERY = 100

# How long the pipe's thread waits for the window's answer to a Cancel sent
# from outside, in seconds; shorter than the sender waits
# (handoff.WAIT_FOR_ANSWER). Taking it takes up to CHECK_EVERY.
ANSWER_WITHIN = 2.0

# How many rows the list of downloads shows; it scrolls for more.
LIST_ROWS = 6

# The downloads with a saved file, kept for the next sessions: the newest
# HISTORY_SIZE of them. The tests pass a file of their own.
HISTORY = places.DATA_FOLDER / "history.json"
HISTORY_SIZE = 200

# link, MP4 or MP3, folder, report, the quality limit (None: the best),
# English subtitles, cancel (set: stop and report Cancelled), confirm (asked
# before a playlist's first video; False: stop as Cancel does)
type Download = Callable[
    [str, Kind, Path, Report, int | None, bool, threading.Event, Confirm], None
]

# Shows a Yes/No box on the window with this text; True: Yes.
type Ask = Callable[[tk.Tk, str], bool]


def ask_yes_no(root: tk.Tk, text: str) -> bool:
    """Ask in a Yes/No box on the window (Yes is what Enter picks); the
    window waits until it is answered. The tests pass a fake."""
    return messagebox.askyesno(TITLE, text, parent=root)


class State(StrEnum):
    """Where a download in the list is, as its State column says it."""

    WAITING = "Waiting"
    DOWNLOADING = "Downloading"
    CANCELLING = "Cancelling"
    DONE = "Done"
    ALREADY_THERE = "Already there"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


# The states of a download that has ended.
ENDED = {State.DONE, State.ALREADY_THERE, State.FAILED, State.CANCELLED}

# The states of a download whose file was saved: only these are kept in the
# history.
SAVED = {State.DONE, State.ALREADY_THERE}


@dataclass
class Job:
    """One row of the list: a link with the choices it was added with, and
    what the window shows while its row is selected."""

    link: str
    kind: Kind
    height: int | None  # the quality limit (None: the best); None for MP3
    subtitles: bool  # False for MP3
    state: State = State.WAITING
    title: str = ""  # the video's title, once yt-dlp has looked it up
    message: str = WAITING  # the status line
    failed: bool = False  # the status line in dark red
    percent: float | None = 0  # the bar; None moves it to and fro
    file: Path | None = None  # the saved file, once done

    def row(self) -> tuple[str, str, str]:
        """The row's Video, As and State columns."""
        what = str(self.kind).upper()
        if self.height is not None:
            what += f" {self.height}p"
        if self.subtitles:
            what += ", subtitles"
        state = str(self.state)
        if self.state is State.DOWNLOADING and self.percent is not None:
            state += f" {self.percent:.0f}%"
        return self.title or self.link, what, state


def new_job(link: str, choices: handoff.Choices) -> Job:
    """A waiting row for the link with the choices; the quality and subtitles
    count for MP4 only."""
    kind = Kind(choices.kind)
    mp4 = kind == Kind.MP4
    height = QUALITIES[choices.quality] if mp4 else None
    return Job(link, kind, height, choices.subtitles and mp4)


class Files:
    """Opens files and folders for the user; the tests pass a fake, so nothing
    opens."""

    def play(self, file: Path) -> None:
        """Open the file in its default app (VLC, Media Player...)."""
        os.startfile(file)

    def show(self, file: Path) -> None:
        """Open Explorer at the file's folder, with the file selected."""
        # Not waited for: explorer.exe takes about 0.3 s, and returns 1 even
        # when it worked.
        subprocess.Popen(show_command(file))

    def open_folder(self, folder: Path) -> None:
        """Open the folder in Explorer, making it first if it isn't there."""
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)


def show_command(file: Path) -> str:
    """Explorer's command line that shows `file` selected. A string, not a
    list: Python quotes a list's parts only when they hold a space, and
    Explorer splits an unquoted path at its commas
    (docs/research/opening-files.md). Explorer's full path, because Windows
    looks for a bare `explorer` in Python's folder and the current folder
    first."""
    explorer = Path(os.environ["WINDIR"]) / "explorer.exe"
    return f'"{explorer}" /select,"{file}"'


class App:
    """The window's widgets and what happens when they are used.

    download: what fetches the video (yt-dlp; the tests pass a fake).
    folder: where files go (default: Videos inside Downloads).
    files: what opens the downloaded file or its folder (the tests pass a fake).
    history: the file of past downloads (default: HISTORY; the tests pass one
    in a temporary folder).
    listening: the named pipe taken for this window (handoff.listen(): main()
    takes handoff.PIPE, tests one of their own); the window starts reading
    the links sent from outside there. None: don't listen.
    ask: the Yes/No box for a playlist above ASK_ABOVE videos (default:
    ask_yes_no(); the tests pass a fake).
    """

    def __init__(
        self,
        root: tk.Tk,
        download: Download = downloader.download,
        folder: Path | None = None,
        files: Files | None = None,
        history: Path | None = None,
        listening: handoff.Listening | None = None,
        ask: Ask = ask_yes_no,
    ) -> None:
        self.root = root
        self.run_download = download
        self.folder = folder or downloader.default_folder()
        self.files = files or Files()
        self.history = history or HISTORY
        self.keeps_history = True  # False: the file was there but unreadable
        self.jobs: dict[str, Job] = {}  # by the list's row id
        self.running = ""  # the row downloading now, if any
        self.cancel = threading.Event()  # set by Cancel; a new one per download
        self.events: queue.Queue[Event] = queue.Queue()
        self.next_check = ""  # the scheduled check_events(), while busy
        self.next_fit = ""  # the scheduled fit_height()
        self.received: queue.Queue[handoff.Message] = queue.Queue()  # from outside
        # Cancels sent from outside: the link, and where its answer goes.
        self.cancels: queue.Queue[tuple[str, Future[handoff.Answer]]] = queue.Queue()
        self.next_link_check = ""  # the scheduled check_links()
        self.next_update_check = ""  # the scheduled show_update()
        self.restart = False  # Restart now was clicked: main() starts the app
        self.listening = listening
        self.ask = ask
        # Questions from the running download (confirm_playlist()): the box's
        # text, and where its answer goes.
        self.questions: queue.Queue[tuple[str, Future[bool]]] = queue.Queue()

        root.title(TITLE)
        # Kept here: Tk drops an image that Python no longer refers to.
        self.icons = [
            tk.PhotoImage(master=root, file=ICONS / f"{size}.png")
            for size in ICON_SIZES
        ]
        root.iconphoto(True, *self.icons)
        root.minsize(window_width(root), 0)
        root.columnconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=12)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Link to a video:").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.link = tk.StringVar()
        self.link_entry = ttk.Entry(frame, textvariable=self.link)
        self.link_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        # Cancel is greyed out unless a download is running.
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=1)
        self.download_button = ttk.Button(
            buttons, text="Download", command=self.start_download
        )
        self.download_button.grid(row=0, column=0, padx=(0, 8))
        self.cancel_button = ttk.Button(
            buttons, text="Cancel", command=self.cancel_download
        )
        self.cancel_button.grid(row=0, column=1)

        self.kind = tk.StringVar(value=Kind.MP4)
        kinds = ttk.Frame(frame)
        kinds.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.mp4_button = ttk.Radiobutton(
            kinds, text="Video (MP4)", variable=self.kind, value=Kind.MP4
        )
        self.mp4_button.grid(row=0, column=0, padx=(0, 16))
        self.mp3_button = ttk.Radiobutton(
            kinds, text="Audio only (MP3)", variable=self.kind, value=Kind.MP3
        )
        self.mp3_button.grid(row=0, column=1)

        # Greyed out while MP3 is chosen.
        self.quality = tk.StringVar(value="Best")  # a key of QUALITIES
        qualities = ttk.Frame(frame)
        qualities.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.quality_label = ttk.Label(qualities, text="Video quality:")
        self.quality_label.grid(row=0, column=0, padx=(0, 8))
        self.quality_buttons = [
            ttk.Radiobutton(qualities, text=text, variable=self.quality, value=text)
            for text in QUALITIES
        ]
        for column, button in enumerate(self.quality_buttons, start=1):
            button.grid(row=0, column=column, padx=(0, 16))

        # Saved as a file of their own next to the video; greyed out while
        # MP3 is chosen.
        self.subtitles = tk.BooleanVar(value=False)
        self.subtitles_box = ttk.Checkbutton(
            frame, text="English subtitles", variable=self.subtitles
        )
        self.subtitles_box.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Every download, oldest at the top: the past ones from the history,
        # then this session's. One at a time, the others wait their turn. One
        # row is selected at most.
        listed = ttk.Frame(frame)
        listed.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        listed.columnconfigure(0, weight=1)
        self.downloads = ttk.Treeview(
            listed,
            columns=("video", "as", "state"),
            show="headings",
            height=LIST_ROWS,
            selectmode="browse",
        )
        self.downloads.grid(row=0, column=0, sticky="ew")
        self.scrollbar = ttk.Scrollbar(listed, command=self.downloads.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.downloads.configure(yscrollcommand=self.scrollbar.set)
        # Tk's own row height cuts off the bottom of the text (an underscore)
        # at 150% display scaling: rows a quarter taller than a line of text.
        text_font = font.nametofont("TkDefaultFont")
        line = text_font.metrics("linespace")
        ttk.Style(root).configure("Treeview", rowheight=line + line // 4)
        # As and State as wide as their longest text; Video takes the rest.
        text_width = text_font.measure
        columns = {
            "video": ("Video", None),
            "as": ("As", "MP4 720p, subtitles"),
            "state": ("State", "Downloading 100%"),
        }
        for column, (heading, longest) in columns.items():
            self.downloads.heading(column, text=heading, anchor="w")
            if longest is not None:
                width = text_width(longest) + text_width("    ")
                self.downloads.column(column, width=width, stretch=False)
        self.downloads.tag_configure("failed", foreground=FAILED_COLOR)
        self.downloads.bind("<<TreeviewSelect>>", lambda _event: self.show_selected())
        self.downloads.bind("<Double-Button-1>", self.on_double_click)
        self.downloads.bind("<Delete>", lambda _event: self.remove_selected())
        past = load_history(self.history)
        self.keeps_history = past is not None  # don't write over what it holds
        for job in past or []:  # the newest ends up in view
            self.add_row(job)

        self.progress_bar = ttk.Progressbar(frame, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # Progress, the result and error messages. yt-dlp's messages can be
        # long: they wrap to the window's width instead of widening it, and
        # the window grows taller to show every line.
        self.status = tk.StringVar()
        self.status_label = ttk.Label(frame, textvariable=self.status, justify="left")
        self.status_label.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.status_label.bind("<Configure>", self.wrap)
        self.status.trace_add("write", lambda *_: self.fit_height_soon())
        root.resizable(True, False)  # fit_height() sets the height

        # About the selected row. Play is greyed out unless it has a file;
        # Show in folder opens the download folder then.
        actions = ttk.Frame(frame)
        actions.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.play_button = ttk.Button(actions, text="Play", command=self.play)
        self.play_button.grid(row=0, column=0, padx=(0, 8))
        # Wider than its text, as the other buttons are (in average characters).
        self.show_button = ttk.Button(
            actions, text="Show in folder", width=16, command=self.show_in_folder
        )
        self.show_button.grid(row=0, column=1, padx=(0, 8))
        self.remove_button = ttk.Button(
            actions, text="Remove", command=self.remove_selected
        )
        self.remove_button.grid(row=0, column=2)

        # UPDATED and Restart now, under everything else: placed only once
        # there is a newer yt-dlp (show_update()), so the window has no empty
        # line otherwise. The text wraps; the button stays at the right, under
        # Download and Cancel. Greyed out while a download runs, as a restart
        # would stop it and drop the links waiting behind it.
        self.update_line = ttk.Frame(frame)
        self.update_line.columnconfigure(0, weight=1)
        self.update_label = ttk.Label(self.update_line, justify="left")
        self.update_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.update_label.bind("<Configure>", self.wrap)
        self.restart_button = ttk.Button(
            self.update_line, text="Restart now", command=self.restart_now
        )
        self.restart_button.grid(row=0, column=1)

        # Only now: update_states() uses every widget above.
        self.kind.trace_add("write", lambda *_: self.update_states())
        self.update_states()

        self.link_entry.focus_set()
        self.link_entry.bind("<Return>", lambda _event: self.start_download())
        root.bind("<Destroy>", self.on_destroy)

        # The first check from the event loop: a link start() gives the
        # window comes first, before one sent while it was being built.
        if listening is not None:
            listening.start(self.received.put, self.answer_cancel)
            self.next_link_check = root.after(CHECK_EVERY, self.check_links)

    @property
    def busy(self) -> bool:
        """A download is running."""
        return bool(self.running)

    def start_download(self) -> None:
        """Add the link in the box to the list with the choices made now, and
        empty the box for the next one. It starts at once when nothing is
        downloading, otherwise when the downloads above it have ended."""
        link = self.link.get().strip()
        if not link:
            self.show_status(PASTE_A_LINK)
            return
        choices = handoff.Choices(
            self.kind.get(), self.quality.get(), self.subtitles.get()
        )
        self.link.set("")
        self.add_download(link, choices)

    def add_download(self, link: str, choices: handoff.Choices) -> None:
        """Add the link to the list with the choices. It starts at once, its
        row selected, when nothing is downloading, otherwise when the
        downloads above it have ended."""
        self.add_row(new_job(link, choices))
        if self.busy:
            self.update_states()
        else:
            self.start_next(select=True)

    def add_row(self, job: Job) -> None:
        """Add the job at the bottom of the list, and scroll it into view."""
        row = self.downloads.insert("", "end", values=job.row())
        self.jobs[row] = job
        self.downloads.see(row)

    def start_next(self, select: bool) -> None:
        """Start the first waiting download in the background, if there is
        one, and select its row when `select` is true."""
        waiting = (r for r, job in self.jobs.items() if job.state is State.WAITING)
        self.running = next(waiting, "")
        if not self.running:
            self.update_states()
            return
        job = self.jobs[self.running]
        job.state, job.message, job.percent = State.DOWNLOADING, LOOKING_UP, None
        self.cancel = threading.Event()
        threading.Thread(
            target=self.run_job,
            args=(job, self.cancel),
            daemon=True,  # closing the window stops the download
        ).start()
        if not self.next_check:
            self.next_check = self.root.after(CHECK_EVERY, self.check_events)
        if select:
            self.select(self.running)
        self.update_row(self.running)

    def run_job(self, job: Job, cancel: threading.Event) -> None:
        """Download the job's link; runs in the background. The window hears
        exactly one end from it (Done, Failed or Cancelled), and nothing
        after it, even when the download raises or returns without one: the
        next waiting link starts only then, and its reports must not mix
        with this one's."""
        ended = False

        def report(event: Event) -> None:
            nonlocal ended
            if not ended:
                self.events.put(event)
                ended = not isinstance(event, Progress)

        try:
            self.run_download(
                job.link,
                job.kind,
                self.folder,
                report,
                job.height,
                job.subtitles,
                cancel,
                self.confirm_playlist,
            )
        except Exception as error:
            traceback.print_exc()  # the details, in the terminal
            report(Failed(f"Something went wrong: {error}"))
        report(Failed(NO_END))  # dropped when it has ended already

    def confirm_playlist(self, title: str, count: int) -> bool:
        """The download's `confirm`, in its thread: yes for a playlist of up
        to ASK_ABOVE videos. Above that, the window asks (check_events())
        and the download waits for the answer."""
        if count <= ASK_ABOVE:
            return True
        playlist = f"“{title}”" if title else "This playlist"
        answer: Future[bool] = Future()
        self.questions.put((MANY_VIDEOS.format(playlist=playlist, count=count), answer))
        return answer.result()

    def answer_question(self, job: Job | None, text: str) -> bool:
        """Ask the running download's question in the box, with the window in
        front: a download from outside runs in a minimized window or one
        behind the browser, where nobody would see it. No without a box once
        Cancel was pressed (during yt-dlp's listing, it can't act yet)."""
        if job is None or job.state is not State.DOWNLOADING:
            return False
        bring_to_front(self.root)
        return self.ask(self.root, text)

    def cancel_download(self) -> None:
        """Cancel: stop the running download (stop_running()) and select its
        row."""
        if self.stop_running():
            self.select(self.running)

    def stop_running(self) -> bool:
        """Ask the running download to stop; False when none is downloading
        (or it is stopping already). It reports Cancelled once it has stopped
        and deleted what it had saved: at once while downloading, after the
        step while ffmpeg joins or converts. One that finishes before it
        notices reports Done as usual: the file is there. The next waiting
        link starts then."""
        job = self.jobs.get(self.running)
        if job is None or job.state is not State.DOWNLOADING:
            return False
        self.cancel.set()
        job.state, job.message, job.percent = State.CANCELLING, CANCELLING, None
        self.update_row(self.running)
        return True

    def cancel_link(self, link: str) -> handoff.Answer:
        """A Cancel sent from outside (the Chrome popup): stop the link's
        running download as Cancel does, and mark its waiting ones
        Cancelled, so they are skipped. Every row of the link counts (it can
        be in the list twice, as MP4 and as MP3); one that has ended stays as
        it is. The selection stays too: the window is left alone, as with a
        download sent from outside."""
        rows = [
            row
            for row, job in self.jobs.items()
            if job.link == link and job.state not in ENDED
        ]
        for row in rows:
            job = self.jobs[row]
            if job.state is State.WAITING:
                job.state, job.message = State.CANCELLED, CANCELLED
                self.update_row(row)
            elif row == self.running:
                self.stop_running()  # nothing to do while it is cancelling
        return handoff.Answer.CANCELLED if rows else handoff.Answer.NOTHING

    def answer_cancel(self, link: str) -> handoff.Answer | None:
        """A Cancel sent from outside, in the pipe's thread: hand it to the
        window's thread (check_links(), as Tk is used from that thread only)
        and wait for its answer. None when it doesn't come within
        ANSWER_WITHIN seconds (the window is stuck or closing): the Cancel is
        withdrawn then, so it doesn't happen after the sender was told "no
        answer"."""
        answer: Future[handoff.Answer] = Future()
        self.cancels.put((link, answer))
        try:
            return answer.result(timeout=ANSWER_WITHIN)
        except TimeoutError:
            # Withdrawn, unless the window's thread took it this very moment.
            answer.cancel()
            return None

    def check_events(self) -> None:
        """Show what the running download reported since the last check; when
        it has ended, start the next waiting one."""
        self.next_check = ""
        row = self.running  # only the running download reports (run_job())
        job = self.jobs.get(row)  # Remove skips the running row
        changed = False
        while job is not None and job.state not in ENDED and not self.events.empty():
            match self.events.get():
                # After Cancel, progress reported before it stopped would
                # replace "Cancelling...".
                case Progress() as progress if job.state is State.DOWNLOADING:
                    job.message, job.percent = progress.text, progress.percent
                    job.title = progress.title or job.title
                case Done() as done:
                    there = done.already_there
                    job.state = State.ALREADY_THERE if there else State.DONE
                    job.message, job.percent = done_message(done), 100
                    job.file = done.path
                    # yt-dlp reports no title for a file that is already there.
                    job.title = job.title or done.path.stem
                case Failed(message):
                    job.state, job.message, job.percent = State.FAILED, message, 0
                    job.failed = True
                case Cancelled(kept):
                    job.state, job.percent = State.CANCELLED, 0
                    job.message = cancelled_message(kept)
                    # A playlist's finished videos: Play plays the first.
                    job.file = kept[0] if kept else None
                case _:
                    continue
            changed = True
        # Once per check, not per report: a fast download reports many times
        # in 0.1 s, and only the last one shows.
        if job is not None and changed:
            self.update_row(row)
            if job.state in SAVED:
                self.update_history()
            if job.state in ENDED:
                # The next one gets selected unless another row was selected
                # since this one started: the user is looking at that one.
                self.start_next(select=self.selected() in (row, ""))
        # Last, as the box waits for its answer: the rows are up to date
        # meanwhile, and this check is scheduled again only after it. Only
        # the running download asks: the one start_next() may just have
        # started.
        while not self.questions.empty():
            text, answer = self.questions.get()
            answer.set_result(self.answer_question(self.jobs.get(self.running), text))
        if self.busy and not self.next_check:
            self.next_check = self.root.after(CHECK_EVERY, self.check_events)

    def check_links(self) -> None:
        """Take what was sent from outside since the last check, and check
        again soon. Each link with choices joins the list, in the order
        sent; of the links alone, only the newest goes in the box (it holds
        one). A "show" (the app started again, no link) brings the window to
        the front. Then the Cancels, each answered (answer_cancel()) unless
        it was withdrawn."""
        link, show = "", False
        while not self.received.empty():
            message = self.received.get()
            if message.show:
                show = True
            elif message.start is None:
                link = message.link
            else:
                self.add_download(message.link, message.start)
        if link:
            self.receive_link(link)  # to the front too
        elif show:
            bring_to_front(self.root)
        while not self.cancels.empty():
            cancel_link, answer = self.cancels.get()
            if answer.set_running_or_notify_cancel():  # False: withdrawn
                answer.set_result(self.cancel_link(cancel_link))
        self.next_link_check = self.root.after(CHECK_EVERY, self.check_links)

    def receive_link(self, link: str) -> None:
        """Put a link sent from outside in the box, replacing what is there,
        and bring the window to the front. It doesn't start: MP4 or MP3 is
        still chosen here. The hint stays until the selected row reports."""
        self.link.set(link)
        self.link_entry.icursor("end")
        self.show_status(LINK_RECEIVED)
        bring_to_front(self.root)
        self.link_entry.focus_set()

    def selected(self) -> str:
        """The selected row, or "" when none is."""
        rows = self.downloads.selection()
        return rows[0] if rows else ""

    def selected_file(self) -> Path | None:
        """The selected row's file, if it has one."""
        job = self.jobs.get(self.selected())
        return job.file if job else None

    def select(self, row: str) -> None:
        self.downloads.selection_set(row)
        self.downloads.see(row)
        self.show_selected()

    def update_row(self, row: str) -> None:
        """Show what changed in the row's job: in the row, and under the list
        when the row is selected."""
        job = self.jobs[row]
        failed = ("failed",) if job.state is State.FAILED else ()
        self.downloads.item(row, values=job.row(), tags=failed)
        if row == self.selected():
            self.show_selected()
        else:
            self.update_states()

    def show_selected(self) -> None:
        """Show the selected row's message and progress under the list."""
        job = self.jobs.get(self.selected())
        if job is not None:
            self.show_status(job.message, job.failed)
            self.show_progress(job.percent)
        self.update_states()

    def remove_selected(self) -> None:
        """Take the selected row out of the list: a waiting link won't be
        downloaded. The file of a finished one stays where it is, and the
        history forgets it. Not the running one: Cancel stops that."""
        row = self.selected()
        if not row or row == self.running:
            return
        self.downloads.delete(row)
        if self.jobs.pop(row).state in SAVED:
            self.update_history()
        if self.running:
            self.select(self.running)
        else:
            self.show_status("")
            self.show_progress(0)
            self.update_states()

    def update_history(self) -> None:
        """Write the list's saved files to the history file, for the next
        session; not when it couldn't be read at the start."""
        if self.keeps_history:
            save_history(self.history, self.jobs.values())  # in the list's order

    def on_double_click(self, event: tk.Event) -> None:
        # A double click on a row plays it; on a heading, nothing.
        if self.downloads.identify_row(event.y):
            self.play()

    def play(self) -> None:
        """Open the selected row's file in its default app."""
        row = self.selected()
        job = self.jobs.get(row)
        if job is None or job.file is None:  # Play is greyed out then
            return
        if job.file.is_file():
            self.files.play(job.file)
        else:  # moved or deleted since: say so, then grey Play out
            folder = shown_folder(job.file.parent)
            job.message = GONE.format(name=job.file.name, folder=folder)
            job.failed, job.file = True, None
            self.update_row(row)
            self.update_history()  # gone from it too

    def show_in_folder(self) -> None:
        """Open Explorer with the selected row's file selected, or the
        download folder when it has none (or it was moved or deleted)."""
        file = self.selected_file()
        if file is not None and file.is_file():
            self.files.show(file)
        else:
            self.files.open_folder(self.folder)

    def on_destroy(self, event: tk.Event) -> None:
        # Drop what is still scheduled, or it runs later without its window
        # (only the tests open a second window).
        # Stop listening, so a window opened later can listen on the pipe.
        if event.widget is self.root:
            for scheduled in (
                self.next_check,
                self.next_fit,
                self.next_link_check,
                self.next_update_check,
            ):
                if scheduled:
                    self.root.after_cancel(scheduled)
            if self.listening is not None:
                self.listening.close()

    def wrap(self, event: tk.Event) -> None:
        """Wrap a line of text (the status line, UPDATED) at its width, which
        follows the window's."""
        event.widget["wraplength"] = event.width
        self.fit_height_soon()

    def look_for_update(self, check: Callable[[], str | None]) -> None:
        """Run check() in the background (main() passes ytdlp_update.check:
        a newer yt-dlp for the next start), and show UPDATED once it returns
        a version; nothing when it returns None."""
        result: Future[str | None] = Future()

        def run() -> None:
            try:
                result.set_result(check())
            except Exception as error:  # so show_update() stops looking
                result.set_exception(error)

        threading.Thread(target=run, daemon=True).start()
        self.show_update(result)

    def show_update(self, result: Future[str | None]) -> None:
        """Show UPDATED and Restart now under everything else once
        look_for_update()'s check has found a version; until it has ended,
        look every CHECK_EVERY ms."""
        if not result.done():
            self.next_update_check = self.root.after(
                CHECK_EVERY, self.show_update, result
            )
            return
        self.next_update_check = ""
        version = None if result.exception() else result.result()
        if version:
            self.update_label.configure(text=UPDATED.format(version=version))
            self.update_line.grid(
                row=9, column=0, columnspan=2, sticky="ew", pady=(8, 0)
            )
            self.fit_height_soon()

    def restart_now(self) -> None:
        """Restart now: end the window's event loop; main() then closes the
        window and starts the app again, which loads the newer yt-dlp. Does
        nothing while the event loop isn't running (the tests)."""
        self.restart = True
        self.root.quit()

    def fit_height_soon(self) -> None:
        """Run fit_height() once Tk has worked out the new layout."""
        if not self.next_fit:
            self.next_fit = self.root.after_idle(self.fit_height)

    def fit_height(self) -> None:
        """Make the window as tall as its contents. Tk does this by itself
        only until the window's size has been set, by the user dragging its
        edge or by the GUI test."""
        self.next_fit = ""
        root = self.root
        root.update_idletasks()
        if root.winfo_ismapped() and root.winfo_height() != root.winfo_reqheight():
            root.geometry(f"{root.winfo_width()}x{root.winfo_reqheight()}")

    def show_status(self, text: str, failed: bool = False) -> None:
        """Show `text` under the bar: a failure in dark red."""
        self.status.set(text)
        self.status_label.configure(foreground=FAILED_COLOR if failed else "")

    def update_states(self) -> None:
        """Grey out what can't be used now: Cancel unless a download is
        running (once), the video quality and subtitles while MP3 is chosen,
        Play unless the selected row has a file, Remove unless a row is
        selected that isn't running, and Restart now while a download runs
        (links wait only behind a running one)."""
        job = self.jobs.get(self.running)
        enabled: dict[ttk.Widget, bool] = {
            self.cancel_button: job is not None and job.state is State.DOWNLOADING,
            self.play_button: self.selected_file() is not None,
            self.remove_button: self.selected() not in ("", self.running),
            self.restart_button: not self.busy,
        }
        video = self.kind.get() == Kind.MP4
        for widget in (self.quality_label, *self.quality_buttons, self.subtitles_box):
            enabled[widget] = video
        for widget, on in enabled.items():
            widget.state(["!disabled"] if on else ["disabled"])

    def show_progress(self, percent: float | None) -> None:
        """Fill the bar to `percent`; None makes it move to and fro instead."""
        bar = self.progress_bar
        if percent is None:
            if str(bar.cget("mode")) != "indeterminate":
                bar.configure(mode="indeterminate")
                bar.start(15)
        else:
            bar.stop()
            bar.configure(mode="determinate", value=percent)


def shown_folder(folder: Path) -> Path:
    """The folder as the status line names it: from the home folder on, when
    it is inside it."""
    home = Path.home()
    return folder.relative_to(home) if folder.is_relative_to(home) else folder


def done_message(done: Done) -> str:
    folder = shown_folder(done.path.parent)
    if done.playlist is not None:
        return playlist_message(done.playlist, folder)
    if done.already_there:
        message = f"Already there, not downloaded again: {done.path.name} (in {folder})"
    else:
        message = f"Done: {done.path.name} (in {folder})"
    return f"{message}. {NO_SUBTITLES}" if done.no_subtitles else message


def playlist_message(playlist: Playlist, folder: Path) -> str:
    """A finished playlist's status line, for example "Done: 10 of 12 videos
    saved, 1 was already there, 1 failed (in Downloads\\Videos\\My list).
    Why the first failed: ..." (the reason of the others: in the terminal)."""
    total = videos(playlist.videos)
    if playlist.saved:
        parts = [f"Done: {playlist.saved} of {total} saved"]
        if playlist.there:
            was = "was" if playlist.there == 1 else "were"
            parts.append(f"{playlist.there} {was} already there")
    else:
        parts = [f"Already there, not downloaded again: {playlist.there} of {total}"]
    if playlist.failed:
        parts.append(f"{playlist.failed} failed")
    notes = [f"{', '.join(parts)} (in {folder})."]
    if playlist.why:
        notes.append(downloader.WHY_FIRST_FAILED.format(why=playlist.why))
    if playlist.no_subtitles:
        notes.append(SOME_WITHOUT_SUBTITLES.format(count=playlist.no_subtitles))
    return " ".join(notes)


def cancelled_message(kept: tuple[Path, ...]) -> str:
    """The status line after Cancel; `kept`: a playlist's finished videos."""
    if not kept:
        return CANCELLED
    folder = shown_folder(kept[0].parent)
    return KEPT.format(videos=videos(len(kept)), folder=folder)


def videos(count: int) -> str:
    """A number of videos: "1 video", "12 videos"."""
    return f"{count} video" if count == 1 else f"{count} videos"


def load_history(file: Path) -> list[Job] | None:
    """The past downloads in the history file, oldest first. A file that isn't
    there or is broken is an empty history, and an entry that can't be read
    is left out: the next save writes the file anew without it. None: the
    file is there but couldn't be opened (locked by a virus scanner, or not
    allowed), so it must not be written over (details in the terminal)."""
    try:
        entries = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except OSError:
        traceback.print_exc()
        return None
    except ValueError:  # not UTF-8, or not JSON
        return []
    if not isinstance(entries, list):
        return []
    jobs: list[Job] = []
    for entry in entries:
        try:
            jobs.append(past_job(entry))
        except (KeyError, TypeError, ValueError):
            continue
    return jobs


def save_history(file: Path, jobs: Iterable[Job]) -> None:
    """Write the jobs with a saved file to the history file, the newest
    HISTORY_SIZE of them, oldest first. One whose file Play found gone has
    none any more, so it is left out. The new text goes into a file next to
    it first, which then replaces it: a save that stops halfway leaves the
    old one. A save that fails is skipped (the details in the terminal): the
    history only helps, and the download itself is fine. It must not raise:
    the window moves on to the next waiting link after it."""
    entries = [
        history_entry(job)
        for job in jobs
        if job.state in SAVED and job.file is not None
    ]
    new = file.with_name(f"{file.name}.new")
    try:
        text = json.dumps(entries[-HISTORY_SIZE:], ensure_ascii=False, indent=2)
        file.parent.mkdir(parents=True, exist_ok=True)
        new.write_text(text, encoding="utf-8")
        new.replace(file)
    except (OSError, ValueError):  # ValueError: a title that isn't valid text
        traceback.print_exc()


def history_entry(job: Job) -> dict[str, object]:
    """The job as the history file holds it."""
    return {
        "link": job.link,
        "kind": str(job.kind),
        "height": job.height,
        "subtitles": job.subtitles,
        "title": job.title,
        "state": str(job.state),
        "message": job.message,
        "file": str(job.file),
    }


def past_job(entry: dict[str, object]) -> Job:
    """A history file's entry as a finished row; raises KeyError, TypeError
    or ValueError when it isn't one."""
    state = State(entry["state"])
    height = entry["height"]
    if state not in SAVED or not isinstance(height, int | None):
        raise ValueError(entry)
    return Job(
        link=str(entry["link"]),
        kind=Kind(entry["kind"]),
        height=height,
        subtitles=bool(entry["subtitles"]),
        state=state,
        title=str(entry["title"]),
        message=str(entry["message"]),
        percent=100,
        file=Path(str(entry["file"])),
    )


def window_width(root: tk.Misc) -> int:
    """WIDTH in the display's own pixels: 900 at 150% scaling."""
    return round(WIDTH * root.winfo_fpixels("1i") / 96)


def bring_to_front(root: tk.Tk) -> None:
    """Show the window in front of the others, also when it was minimized,
    and give it the keyboard focus. Windows may refuse the focus (it flashes
    the taskbar button then), so being in front doesn't rely on it."""
    root.deiconify()
    on_top = bool(root.attributes("-topmost"))  # the GUI test's window is
    root.attributes("-topmost", True)
    root.attributes("-topmost", on_top)
    root.focus_force()


def start(
    download: Download = downloader.download,
    folder: Path | None = None,
    files: Files | None = None,
    history: Path | None = None,
    listening: handoff.Listening | None = None,
    link: str = "",
    choices: handoff.Choices | None = None,
    ask: Ask = ask_yes_no,
) -> App:
    """Build the window as the user sees it; the GUI test starts it this way
    too. The parameters are App's, and link: put in the box at the start, or
    with choices, downloading with them at once in a minimized window (as
    the first row, before any sent while the window was being built)."""
    if sys.platform == "win32":
        # Without this, Windows scales the window up and the text looks blurry.
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # Before the window opens: a taskbar button of its own, with its icon.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = App(tk.Tk(), download, folder, files, history, listening, ask)
    if link and choices is not None:
        app.add_download(link, choices)
        app.root.iconify()
    elif link:
        app.receive_link(link)
    return app


def main(arguments: list[str] | None = None) -> None:
    """Open the window, or with one open already, hand it the link, or with
    no link bring it to the front, and open none (hand_over()). A link goes
    in the box; with --download, it is downloaded at once (a window opened
    for it starts minimized). arguments: the command line's (default:
    sys.argv's)."""
    parser = argparse.ArgumentParser(
        prog="python -m video_downloader",
        description="Download a video as MP4 or MP3.",
    )
    parser.add_argument(
        "link",
        nargs="?",
        default="",
        help="put this link in the box (of the window that is open, if one is)",
    )
    parser.add_argument(
        "--download",
        choices=handoff.KINDS,
        help="download the link at once, as MP4 or MP3, instead of putting it "
        "in the box (in a minimized window, if none is open)",
    )
    parser.add_argument(
        "--quality",
        choices=handoff.QUALITIES,
        default="Best",
        help="the video quality, for --download mp4 (default: Best)",
    )
    parser.add_argument(
        "--subtitles",
        action="store_true",
        help="English subtitles too, for --download mp4",
    )
    options = parser.parse_args(arguments)
    link = options.link.strip()
    choices = None
    if options.download:
        if not link:
            parser.error("--download needs a link")
        choices = handoff.Choices(options.download, options.quality, options.subtitles)
    # The pipe first, before the window is built: of two windows started at
    # once, Windows gives it to one only, and the other hands over.
    listening = None
    try:
        listening = handoff.listen(handoff.PIPE)  # None: can't be made
    except PermissionError:  # another window has it: that one gets the link
        if hand_over(link, choices):
            return
        # That window was closing: take its pipe, unless it is stuck.
        with contextlib.suppress(PermissionError):
            listening = handoff.listen(handoff.PIPE)
    # Setup and the uninstaller ask to close the window while this exists
    # (installer/setup.iss, AppMutex). Here, not in start(): only a window
    # that opens holds it, not the GUI test's or the screenshots'.
    hold_mutex(APP_ID)
    app = start(listening=listening, link=link, choices=choices)
    # Once the window is built, the built app looks for a newer yt-dlp, for
    # its next start, and says so when it got one (from the project it
    # doesn't look).
    app.look_for_update(ytdlp_update.check)
    app.root.mainloop()
    # Restart now: close the window first, which frees the pipe for the new
    # one, then start it. This process ends right after (its mutex with it).
    if app.restart:
        app.root.destroy()
        host.start_app([])


def hold_mutex(name: str) -> int | None:
    """Create a mutex called `name`, held until this process ends (Windows
    closes it then; Inno Setup's help advises not closing it sooner). Its
    handle, or None when it can't be made."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32")  # its own copy, for these types
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    return kernel32.CreateMutexW(None, False, name)


def hand_over(link: str, choices: handoff.Choices | None) -> bool:
    """Hand the link, with the choices if any, to the window that is open,
    or with no link bring it to the front; False when that fails (it is
    closing or stuck)."""
    if link:
        return handoff.send(link, handoff.PIPE, choices)
    return handoff.show(handoff.PIPE)
