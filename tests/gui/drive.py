"""Start the real window and use it like a user: shared by the GUI test and the
screenshots. Keys and clicks go through Tk's own events, so they run the same
code a real key press or click runs, without moving the user's mouse.

The window takes the keyboard focus while it is open (about 0.3 s each). Real
key presses and clicks are ignored then, so someone typing in another window
can't change the result (docs/research/gui-testing.md)."""

import ctypes
import tempfile
import threading
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from tkinter import ttk

from PIL import ImageGrab

from video_downloader.app import (
    App,
    Files,
    Job,
    State,
    done_message,
    save_history,
    start,
)
from video_downloader.downloader import Cancelled, Done, Failed, Kind, Progress, Report

SCREENSHOT_DIR = Path(tempfile.gettempdir()) / "video-downloader-screenshots"

# The links the GUI test and the screenshots type.
LINK = "https://www.youtube.com/watch?v=abc_123-XYZ"
LINK2 = "https://www.youtube.com/watch?v=def_456-UVW"

# What FakeDownload reports: the video's title by its link (VIDEO_TITLE for
# any other), and this progress.
VIDEO_TITLE = "Test video"
TITLES = {LINK: VIDEO_TITLE, LINK2: "Second video"}
PROGRESS = "Downloading video: 40% of 12 MB"

# The past downloads write_history() puts in the history, oldest first: the
# title, MP4 or MP3, the quality limit (None: the best) and subtitles.
PAST = [
    ("Cooking pasta at home", Kind.MP4, None, False),
    ("Morning news", Kind.MP4, 720, False),
    ("Lecture 1: Introduction", Kind.MP4, None, True),
    ("Piano practice", Kind.MP3, None, False),
    ("Cat video", Kind.MP4, 480, False),
    ("Lecture 2: Basics", Kind.MP4, None, True),
    ("Favourite song", Kind.MP3, None, False),
    ("Trip to the mountains", Kind.MP4, 720, True),
]

# Tk's key names for the printable characters that aren't letters or digits.
KEY_NAMES = {
    " ": "space",
    "!": "exclam",
    '"': "quotedbl",
    "#": "numbersign",
    "$": "dollar",
    "%": "percent",
    "&": "ampersand",
    "'": "apostrophe",
    "(": "parenleft",
    ")": "parenright",
    "*": "asterisk",
    "+": "plus",
    ",": "comma",
    "-": "minus",
    ".": "period",
    "/": "slash",
    ":": "colon",
    ";": "semicolon",
    "<": "less",
    "=": "equal",
    ">": "greater",
    "?": "question",
    "@": "at",
    "[": "bracketleft",
    "\\": "backslash",
    "]": "bracketright",
    "^": "asciicircum",
    "_": "underscore",
    "`": "grave",
    "{": "braceleft",
    "|": "bar",
    "}": "braceright",
    "~": "asciitilde",
}

# Bind tag put first on every widget: it drops real key presses and clicks.
IGNORE_REAL_INPUT = "GuiTestIgnoreRealInput"


class InputState:
    """True only while this module sends a key or click; real input is ignored
    the rest of the time."""

    sending = False


@contextmanager
def sending() -> Iterator[None]:
    InputState.sending = True
    try:
        yield
    finally:
        InputState.sending = False


class FakeDownload:
    """Stands in for yt-dlp, so nothing touches the internet: reports PROGRESS,
    then waits for finish() before reporting Done, or the failure given to
    finish(); or for Cancel, then reports Cancelled."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Kind, Path, int | None, bool]] = []
        self.finished = threading.Event()
        self.failure: Failed | None = None

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
        title = TITLES.get(link, VIDEO_TITLE)
        report(Progress(PROGRESS, 40.0, title))
        deadline = time.monotonic() + 10
        while not (self.finished.is_set() or cancel.is_set()):
            if time.monotonic() > deadline:
                break
            time.sleep(0.01)
        self.finished.clear()  # the next download waits for its own finish()
        if cancel.is_set():
            report(Cancelled())
        else:
            report(self.failure or Done(folder / f"{title}.{kind}", False))

    def finish(self, failure: Failed | None = None) -> None:
        self.failure = failure
        self.finished.set()


class FakeFiles(Files):
    """Opens nothing: remembers what Play and Show in folder asked to open, as
    ("play", path), ("show", path) or ("open_folder", path)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def play(self, file: Path) -> None:
        self.calls.append(("play", file))

    def show(self, file: Path) -> None:
        self.calls.append(("show", file))

    def open_folder(self, folder: Path) -> None:
        self.calls.append(("open_folder", folder))


def wait_until(app: App, condition: Callable[[], bool], what: str) -> None:
    """Let the window run (it checks for news from the download every 0.1 s)
    until condition() is true; fail after 5 s."""
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline, f"waited 5 s for {what}"
        app.root.update()
        time.sleep(0.01)


def write_history(history: Path, folder: Path) -> None:
    """Write PAST into the history file, as files saved in `folder`."""
    jobs: list[Job] = []
    for number, (title, kind, height, subtitles) in enumerate(PAST):
        file = folder / f"{title}.{kind}"
        message = done_message(Done(file, already_there=False))
        link = f"https://www.youtube.com/watch?v=past{number}"
        job = Job(link, kind, height, subtitles, State.DONE, title, message, file=file)
        jobs.append(job)
    save_history(history, jobs)


def open_window(
    download: FakeDownload,
    history: Path,
    width: int | None = None,
    folder: Path | None = None,
    files: FakeFiles | None = None,
) -> App:
    """Start the window as main() does, on top, with the link box focused.

    download: the fake that stands in for yt-dlp.
    history: the file of past downloads; never the real one, which the
    screenshots (run without pytest's conftest.py) would change.
    width: in screen pixels; None keeps the size the window opens with.
    folder: where the window says files go; None: the real Downloads\\Videos,
    which the fakes never write to.
    files: the fake that stands in for opening files (default: a new one).
    """
    app = start(download, folder, files or FakeFiles(), history)
    root = app.root
    try:
        root.attributes("-topmost", True)
        if width is not None:
            root.update_idletasks()  # works out the height the widgets need
            root.geometry(f"{width}x{root.winfo_reqheight()}")
        ignore_real_input(root)
        root.update()
        focus(app.link_entry)
    except BaseException:
        root.destroy()
        raise
    return app


def ignore_real_input(window: tk.Misc) -> None:
    """Drop key presses and clicks that don't come from this module, in the
    window and everything in it. Safe to call again for widgets added since."""

    def drop_if_real(_event: tk.Event) -> str | None:
        return None if InputState.sending else "break"

    for sequence in ("<KeyPress>", "<KeyRelease>", "<ButtonPress>", "<ButtonRelease>"):
        window.bind_class(IGNORE_REAL_INPUT, sequence, drop_if_real)
    widgets: list[tk.Misc] = [window]
    while widgets:
        widget = widgets.pop()
        if IGNORE_REAL_INPUT not in widget.bindtags():
            widget.bindtags((IGNORE_REAL_INPUT, *widget.bindtags()))
        widgets.extend(widget.winfo_children())


def focus(widget: tk.Widget) -> None:
    """Give the widget the keyboard focus, taking it back if another window
    took it (a click elsewhere, or Windows activating another window)."""
    if widget.focus_get() is widget:
        return
    widget.focus_force()
    widget.update()
    if widget.focus_get() is not widget:
        raise RuntimeError(f"{widget} didn't get the keyboard focus")


def type_text(widget: tk.Widget, text: str) -> None:
    """Type text one key at a time into the widget."""
    for char in text:
        if char.isascii() and char.isalnum():
            press(widget, char)
        elif char in KEY_NAMES:
            press(widget, KEY_NAMES[char])
        else:
            raise ValueError(f"Can't type {char!r}: add its Tk key name to KEY_NAMES")


def press(widget: tk.Widget, key: str) -> None:
    """Press and release one key in the widget, by its Tk name ("a", "Return",
    "slash"). Tk sends key presses to the widget with the keyboard focus."""
    ignore_real_input(widget.winfo_toplevel())
    focus(widget)
    with sending():
        widget.event_generate("<KeyPress>", keysym=key)
        widget.event_generate("<KeyRelease>", keysym=key)
    widget.update()


def click(widget: tk.Widget) -> None:
    """Move the mouse onto the middle of the widget and click it."""
    assert_inside_window(widget)
    ignore_real_input(widget.winfo_toplevel())
    x, y = widget.winfo_width() // 2, widget.winfo_height() // 2
    with sending():
        widget.event_generate("<Enter>", x=x, y=y)
        widget.event_generate("<ButtonPress-1>", x=x, y=y)
        widget.event_generate("<ButtonRelease-1>", x=x, y=y)
    widget.update()


def click_row(tree: ttk.Treeview, row: str, double: bool = False) -> None:
    """Click the middle of a row in the list, twice for a double click."""
    assert_inside_window(tree)
    ignore_real_input(tree.winfo_toplevel())
    x, y, width, height = tree.bbox(row) or (0, 0, 0, 0)
    assert width, f"row {row} isn't shown in the list"
    x, y = x + width // 2, y + height // 2
    with sending():
        for _ in range(2 if double else 1):
            tree.event_generate("<ButtonPress-1>", x=x, y=y)
            tree.event_generate("<ButtonRelease-1>", x=x, y=y)
    tree.update()


def box(widget: tk.Misc) -> tuple[int, int, int, int]:
    """The widget's left, top, right and bottom edge, in pixels from the
    window's top left corner."""
    top = widget.winfo_toplevel()
    left = widget.winfo_rootx() - top.winfo_rootx()
    upper = widget.winfo_rooty() - top.winfo_rooty()
    return left, upper, left + widget.winfo_width(), upper + widget.winfo_height()


def assert_inside_window(widget: tk.Misc) -> None:
    """Fail unless the whole widget is shown inside the window."""
    root = widget.winfo_toplevel()
    left, upper, right, lower = box(widget)
    inside = (
        widget.winfo_viewable()
        and left >= 0
        and upper >= 0
        and right <= root.winfo_width()
        and lower <= root.winfo_height()
    )
    assert inside, (
        f"{widget} is not fully inside the window: its box is "
        f"{(left, upper, right, lower)}, the window is "
        f"{root.winfo_width()}x{root.winfo_height()}"
    )


def screenshot(app: App, name: str) -> Path:
    """Save the whole window, title bar included, as NAME.png in SCREENSHOT_DIR."""
    root = app.root
    root.update()
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    ImageGrab.grab(bbox=window_frame(root), all_screens=True).save(path)
    return path


def window_frame(root: tk.Tk) -> tuple[int, int, int, int]:
    """The window's visible edges on screen, title bar included, in pixels.

    Asks Windows (DWM) for them: GetWindowRect would add an invisible border.
    """
    hwnd = int(root.wm_frame(), 16)
    rect = wintypes.RECT()
    dwmwa_extended_frame_bounds = 9
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        dwmwa_extended_frame_bounds,
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if result != 0:
        raise OSError(
            f"Windows didn't give the window's edges (DwmGetWindowAttribute "
            f"returned {result & 0xFFFFFFFF:#010x})"
        )
    return rect.left, rect.top, rect.right, rect.bottom
