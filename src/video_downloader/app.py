"""The main window: a link box, MP4 or MP3, the video quality, a Download
button, progress and a status line."""

import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from video_downloader import downloader
from video_downloader.downloader import Done, Event, Failed, Kind, Progress, Report

TITLE = "Video Downloader"
PASTE_A_LINK = "Paste a link to a video first."
LOOKING_UP = "Looking up the video..."
PLAYLIST_NOTE = (
    "The link is a playlist: the app only takes its first video "
    "(playlists aren't supported yet)."
)

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

# link, MP4 or MP3, folder, report, the quality limit (None: the best)
type Download = Callable[[str, Kind, Path, Report, int | None], None]


class App:
    """The window's widgets and what happens when they are used.

    download: what fetches the video (yt-dlp; the tests pass a fake).
    folder: where files go (default: Videos inside Downloads).
    """

    def __init__(
        self,
        root: tk.Tk,
        download: Download = downloader.download,
        folder: Path | None = None,
    ) -> None:
        self.root = root
        self.run_download = download
        self.folder = folder or downloader.default_folder()
        self.busy = False
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
        self.download_button = ttk.Button(
            frame, text="Download", command=self.start_download
        )
        self.download_button.grid(row=1, column=1)

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
        self.kind.trace_add("write", lambda *_: self.update_states())

        self.progress_bar = ttk.Progressbar(frame, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # Progress, the result and error messages. yt-dlp's messages can be
        # long: they wrap to the window's width instead of widening it, and
        # the window grows taller to show every line.
        self.status = tk.StringVar()
        self.status_label = ttk.Label(frame, textvariable=self.status, justify="left")
        self.status_label.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.status_label.bind("<Configure>", self.wrap_status)
        self.status.trace_add("write", lambda *_: self.fit_height_soon())
        root.resizable(True, False)  # fit_height() sets the height

        self.link_entry.focus_set()
        self.link_entry.bind("<Return>", lambda _event: self.start_download())
        root.bind("<Destroy>", self.on_destroy)

    def start_download(self) -> None:
        """Start downloading the link in the background; one at a time."""
        if self.busy:
            return
        link = self.link.get().strip()
        if not link:
            self.show_status(PASTE_A_LINK)
            return
        self.set_busy(True)
        self.show_progress(None)
        self.show_status(LOOKING_UP)
        threading.Thread(
            target=self.run_download,
            args=(
                link,
                Kind(self.kind.get()),
                self.folder,
                self.events.put,
                QUALITIES[self.quality.get()],  # the downloader ignores it for MP3
            ),
            daemon=True,  # closing the window stops the download
        ).start()
        self.next_check = self.root.after(CHECK_EVERY, self.check_events)

    def check_events(self) -> None:
        """Show what the download reported since the last check."""
        self.next_check = ""
        while not self.events.empty():
            match self.events.get():
                case Progress(text, percent):
                    self.show_status(text)
                    self.show_progress(percent)
                case Done() as done:
                    self.show_status(done_message(done))
                    self.show_progress(100)
                    self.set_busy(False)
                case Failed(message):
                    self.show_status(message, failed=True)
                    self.show_progress(0)
                    self.set_busy(False)
        if self.busy:
            self.next_check = self.root.after(CHECK_EVERY, self.check_events)

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

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.update_states()

    def update_states(self) -> None:
        """Grey out what can't be used now: every choice and the Download
        button during a download, the video quality while MP3 is chosen."""
        idle = not self.busy
        video = idle and self.kind.get() == Kind.MP4
        for widget in (self.download_button, self.mp4_button, self.mp3_button):
            widget.state(["!disabled"] if idle else ["disabled"])
        for widget in (self.quality_label, *self.quality_buttons):
            widget.state(["!disabled"] if video else ["disabled"])

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


def done_message(done: Done) -> str:
    folder = done.path.parent
    if folder.is_relative_to(Path.home()):
        folder = folder.relative_to(Path.home())
    if done.already_there:
        message = f"Already there, not downloaded again: {done.path.name} (in {folder})"
    else:
        message = f"Done: {done.path.name} (in {folder})"
    return f"{message}. {PLAYLIST_NOTE}" if done.playlist else message


def window_width(root: tk.Misc) -> int:
    """WIDTH in the display's own pixels: 900 at 150% scaling."""
    return round(WIDTH * root.winfo_fpixels("1i") / 96)


def start(download: Download = downloader.download) -> App:
    """Build the window as the user sees it; the GUI test starts it this way too."""
    if sys.platform == "win32":
        # Without this, Windows scales the window up and the text looks blurry.
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    return App(tk.Tk(), download)


def main() -> None:
    start().root.mainloop()
