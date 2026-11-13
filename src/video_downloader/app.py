"""The main window: a link box, Download and Cancel buttons, MP4 or MP3, the
video quality, English subtitles, the list of downloads, progress, a status
line, and Play, Show in folder and Remove buttons.

Links wait in the list and download one after another. The bar, the status
line and the buttons under them are about the selected row."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tkinter import font, ttk

from video_downloader import downloader
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

# How often the window checks for news from the download, in milliseconds.
CHECK_EVERY = 100

# How many rows the list of downloads shows; it scrolls for more.
LIST_ROWS = 6

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
    """

    def __init__(
        self,
        root: tk.Tk,
        download: Download = downloader.download,
        folder: Path | None = None,
        files: Files | None = None,
    ) -> None:
        self.root = root
        self.run_download = download
        self.folder = folder or downloader.default_folder()
        self.files = files or Files()
        self.jobs: dict[str, Job] = {}  # by the list's row id
        self.running = ""  # the row downloading now, if any
        self.cancel = threading.Event()  # set by Cancel; a new one per download
        self.events: queue.Queue[Event] = queue.Queue()
        self.next_check = ""  # the scheduled check_events(), while busy
        self.next_fit = ""  # the scheduled fit_height()

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

        # Every download of this session, oldest at the top: one at a time,
        # the others wait their turn. One row is selected at most.
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
        row = self.downloads.insert("", "end", values=job.row())
        self.jobs[row] = job
        self.downloads.see(row)
        self.link.set("")
        if self.busy:
            self.update_states()
        else:
            self.start_next(select=True)

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
            if job.state in ENDED:
                # The next one gets selected unless another row was selected
                # since this one started: the user is looking at that one.
                self.start_next(select=self.selected() in (row, ""))
        if self.busy and not self.next_check:
            self.next_check = self.root.after(CHECK_EVERY, self.check_events)

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
        downloaded. The file of a finished one stays where it is. Not the
        running one: Cancel stops that."""
        row = self.selected()
        if not row or row == self.running:
            return
        self.downloads.delete(row)
        del self.jobs[row]
        if self.running:
            self.select(self.running)
        else:
            self.show_status("")
            self.show_progress(0)
            self.update_states()

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
        if event.widget is self.root:
            for scheduled in (self.next_check, self.next_fit):
                if scheduled:
                    self.root.after_cancel(scheduled)

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


def window_width(root: tk.Misc) -> int:
    """WIDTH in the display's own pixels: 900 at 150% scaling."""
    return round(WIDTH * root.winfo_fpixels("1i") / 96)


def start(
    download: Download = downloader.download,
    folder: Path | None = None,
    files: Files | None = None,
) -> App:
    """Build the window as the user sees it; the GUI test starts it this way
    too. The parameters are App's."""
    if sys.platform == "win32":
        # Without this, Windows scales the window up and the text looks blurry.
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    return App(tk.Tk(), download, folder, files)


def main() -> None:
    start().root.mainloop()
