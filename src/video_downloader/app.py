"""The main window: a link box, Download and Cancel buttons, MP4 or MP3, the
video quality, English subtitles, the list of downloads, progress, a status
line, and Play, Show in folder and Remove buttons.

Links wait in the list and download one after another. The bar, the status
line and the buttons under them are about the selected row. The list starts
with the past downloads from the history file.

A link sent from outside (`python -m video_downloader LINK`, later the Chrome
button) goes into the link box of the window that is open already, through a
named pipe (handoff.py); it doesn't start by itself."""

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tkinter import font, ttk

from video_downloader import downloader, handoff
from video_downloader.downloader import (
    Cancelled,
    Done,
    Event,
    Failed,
    Kind,
    Progress,
    Report,
)

TITLE = "Video Downloader"
PASTE_A_LINK = "Paste a link to a video first."
LOOKING_UP = "Looking up the video..."
CANCELLING = "Cancelling..."
CANCELLED = "Cancelled."
WAITING = "Waiting: starts when the downloads above it have ended."
NO_END = "Something went wrong: the download stopped without saying why."
PLAYLIST_NOTE = (
    "The link is a playlist: the app only takes its first video "
    "(playlists aren't supported yet)."
)
NO_SUBTITLES = "No English subtitles found."
GONE = "Can't play {name}: it isn't in {folder} anymore."
LINK_RECEIVED = "Link received: choose MP4 or MP3, then Download."

# The video quality choices and their limit as the downloader takes it (720
# for 720p). "Best" (None) is the best that plays everywhere: 1080p on
# YouTube, whose H.264 stops there, so a 1080p choice would give the same
# file (docs/research/yt-dlp-library.md "Quality").
QUALITIES: dict[str, int | None] = {"Best": None, "720p": 720, "480p": 480}

# Failures are shown in dark red, everything else in the normal text color.
FAILED_COLOR = "#a00000"

# The width the window opens with, which is also its smallest, in pixels at
# 100% display scaling (96 DPI). window_width() scales it to the display.
WIDTH = 600

# How often the window checks for news from the download, and for links sent
# from outside, in milliseconds.
CHECK_EVERY = 100

# How many rows the list of downloads shows; it scrolls for more.
LIST_ROWS = 6

# The downloads with a saved file, kept for the next sessions: the newest
# HISTORY_SIZE of them. The tests pass a file of their own.
HISTORY = downloader.DATA_FOLDER / "history.json"
HISTORY_SIZE = 200

# link, MP4 or MP3, folder, report, the quality limit (None: the best),
# English subtitles, cancel (set: stop and report Cancelled)
type Download = Callable[
    [str, Kind, Path, Report, int | None, bool, threading.Event], None
]


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
    pipe: the named pipe to listen on for links sent from outside (main()
    passes handoff.PIPE; tests pass one of their own). None: don't listen.
    """

    def __init__(
        self,
        root: tk.Tk,
        download: Download = downloader.download,
        folder: Path | None = None,
        files: Files | None = None,
        history: Path | None = None,
        pipe: str | None = None,
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
        self.links: queue.Queue[str] = queue.Queue()  # sent from outside
        self.next_link_check = ""  # the scheduled check_links()
        self.listening: handoff.Listening | None = None

        root.title(TITLE)
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
        self.status_label.bind("<Configure>", self.wrap_status)
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

        # Only now: update_states() uses every widget above.
        self.kind.trace_add("write", lambda *_: self.update_states())
        self.update_states()

        self.link_entry.focus_set()
        self.link_entry.bind("<Return>", lambda _event: self.start_download())
        root.bind("<Destroy>", self.on_destroy)

        # Not when another window listens already: that one gets the links.
        if pipe is not None:
            self.listening = handoff.listen(self.links.put, pipe)
            if self.listening is not None:
                self.check_links()

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
        kind = Kind(self.kind.get())
        mp4 = kind == Kind.MP4  # the quality and subtitles are for MP4 only
        job = Job(
            link,
            kind,
            QUALITIES[self.quality.get()] if mp4 else None,
            self.subtitles.get() and mp4,
        )
        self.add_row(job)
        self.link.set("")
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
            )
        except Exception as error:
            traceback.print_exc()  # the details, in the terminal
            report(Failed(f"Something went wrong: {error}"))
        report(Failed(NO_END))  # dropped when it has ended already

    def cancel_download(self) -> None:
        """Ask the running download to stop, and select its row. It reports
        Cancelled once it has stopped and deleted what it had saved: at once
        while downloading, after the step while ffmpeg joins or converts. One
        that finishes before it notices reports Done as usual: the file is
        there. The next waiting link starts then."""
        job = self.jobs.get(self.running)
        if job is None or job.state is not State.DOWNLOADING:
            return
        self.cancel.set()
        job.state, job.message, job.percent = State.CANCELLING, CANCELLING, None
        self.select(self.running)
        self.update_row(self.running)

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
                case Cancelled():
                    job.state, job.message, job.percent = State.CANCELLED, CANCELLED, 0
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
        if self.busy and not self.next_check:
            self.next_check = self.root.after(CHECK_EVERY, self.check_events)

    def check_links(self) -> None:
        """Take the newest link sent from outside since the last check (the
        box holds one), and check again soon."""
        link = ""
        while not self.links.empty():
            link = self.links.get()
        if link:
            self.receive_link(link)
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
            for scheduled in (self.next_check, self.next_fit, self.next_link_check):
                if scheduled:
                    self.root.after_cancel(scheduled)
            if self.listening is not None:
                self.listening.close()

    def wrap_status(self, event: tk.Event) -> None:
        """Wrap the status line at its width, which follows the window's."""
        self.status_label.configure(wraplength=event.width)
        self.fit_height_soon()

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
        Play unless the selected row has a file, and Remove unless a row is
        selected that isn't running."""
        job = self.jobs.get(self.running)
        enabled: dict[ttk.Widget, bool] = {
            self.cancel_button: job is not None and job.state is State.DOWNLOADING,
            self.play_button: self.selected_file() is not None,
            self.remove_button: self.selected() not in ("", self.running),
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
    if done.already_there:
        message = f"Already there, not downloaded again: {done.path.name} (in {folder})"
    else:
        message = f"Done: {done.path.name} (in {folder})"
    notes: list[str] = []
    if done.no_subtitles:
        notes.append(NO_SUBTITLES)
    if done.playlist:
        notes.append(PLAYLIST_NOTE)
    return " ".join([f"{message}.", *notes]) if notes else message


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
    pipe: str | None = None,
    link: str = "",
) -> App:
    """Build the window as the user sees it; the GUI test starts it this way
    too. The parameters are App's, and link: put in the box at the start."""
    if sys.platform == "win32":
        # Without this, Windows scales the window up and the text looks blurry.
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    app = App(tk.Tk(), download, folder, files, history, pipe)
    if link:
        app.receive_link(link)
    return app


def main(arguments: list[str] | None = None) -> None:
    """Open the window. With a link: hand it to the window that is open
    already, or open one with the link in the box. arguments: the command
    line's (default: sys.argv's)."""
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
    link = parser.parse_args(arguments).link.strip()
    if link and handoff.send(link, handoff.PIPE):
        return
    start(pipe=handoff.PIPE, link=link).root.mainloop()
