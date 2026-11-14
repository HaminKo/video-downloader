"""Hand a link to the window that is open already: the window listens on a
Windows named pipe, and `python -m video_downloader LINK` or the Chrome
button's helper (host.py) sends the link there, alone (the window puts it in
its box) or with the choices to download it with (the window adds it to its
list at once).

A message is UTF-8 JSON: {"link": "https://..."}, or with the choices too,
{"link": ..., "start": {"kind": "mp3", "quality": "Best", "subtitles": false}}.
The Chrome button sends its helper the same. multiprocessing's send() and
recv() are never used: they unpickle, which runs whatever the sender packs
in, while json.loads only reads data. Web pages can't reach a named pipe
(docs/research/browser-button.md).
"""

import contextlib
import ctypes
import dataclasses
import json
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Client, Listener

# The real window's pipe; callers always name the pipe, so the tests can
# replace this one (tests/conftest.py).
PIPE = r"\\.\pipe\video-downloader"

# The longest message read, in bytes; a longer one is dropped. Links are far
# shorter (YouTube's about 45 characters).
LONGEST = 64 * 1024

# What a link can be downloaded as: downloader.Kind's values. Spelled out
# here, as the Chrome button's helper (host.py) imports only this module and
# importing downloader loads yt-dlp, which is slow.
KINDS = ("mp4", "mp3")

# The video quality choices, as the window names them, and their limit as
# the downloader takes it (720 for 720p). "Best" (None) is the best that
# plays everywhere: 1080p on YouTube, whose H.264 stops there, so a 1080p
# choice would give the same file (docs/research/yt-dlp-library.md "Quality").
QUALITIES: dict[str, int | None] = {"Best": None, "720p": 720, "480p": 480}


@dataclass(frozen=True)
class Choices:
    """What to download a link as: one of KINDS, a key of QUALITIES, and
    English subtitles or not. The quality and subtitles are for MP4 only."""

    kind: str
    quality: str = "Best"
    subtitles: bool = False


@dataclass(frozen=True)
class Message:
    """A link sent from outside; with choices, to be downloaded with them at
    once, otherwise to go in the box."""

    link: str
    start: Choices | None = None


class Listening:
    """Passes each message sent to the pipe to on_message, in a background
    thread; close() stops it."""

    def __init__(self, pipe: str, on_message: Callable[[Message], None]) -> None:
        # PermissionError when another window listens on the pipe already.
        self.listener = Listener(pipe, family="AF_PIPE")
        self.pipe = pipe
        self.on_message = on_message
        self.closed = False
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self) -> None:
        while True:
            try:
                connection = self.listener.accept()
            except OSError:  # the pipe itself broke: stop rather than retry
                break
            with connection:
                if self.closed:
                    break
                try:
                    data = connection.recv_bytes(LONGEST)
                except OSError:  # too long, or the sender went away midway
                    continue
            message = read_message(data)
            if message is not None:
                self.on_message(message)
        self.listener.close()

    def close(self) -> None:
        """Stop listening, so another window can listen on the pipe. The
        thread waits for a sender, so one wakes it up."""
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(OSError):  # it stopped already
            Client(self.pipe, family="AF_PIPE").close()
        self.thread.join(timeout=1)


def listen(on_message: Callable[[Message], None], pipe: str) -> Listening | None:
    """Start passing the messages sent to `pipe` to on_message (called in
    another thread). None when it can't: mostly because another window
    listens there already (PermissionError), which gets the messages then.
    The window opens either way."""
    try:
        return Listening(pipe, on_message)
    except OSError:
        return None


def send(link: str, pipe: str, start: Choices | None = None) -> bool:
    """Hand `link` to the window listening on `pipe`, with the choices to
    download it with, if any; False when there is none (FileNotFoundError),
    or it is closing or stuck: the caller opens a window of its own then. Only
    a link alone brings the window to the front."""
    message: dict[str, object] = {"link": link}
    if start is None:
        allow_to_front()
    else:
        message["start"] = dataclasses.asdict(start)
    try:
        with Client(pipe, family="AF_PIPE") as connection:
            connection.send_bytes(json.dumps(message).encode("utf-8"))
    except OSError:
        return False
    return True


def read_message(data: bytes) -> Message | None:
    """The message in the bytes sent, or None for one that isn't JSON (in
    UTF-8) as checked_message() takes it."""
    try:
        message = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):  # not UTF-8 or JSON; nested too deep
        return None
    return checked_message(message)


def checked_message(message: object) -> Message | None:
    """The message as JSON gives it, if it holds a link (text, not empty)
    and, if it has "start" at all, known choices (checked_choices()); else
    None."""
    if not isinstance(message, dict):
        return None
    link = message.get("link")
    if not isinstance(link, str) or not link.strip():
        return None
    if "start" not in message:
        return Message(link.strip())
    choices = checked_choices(message["start"])  # null too: not choices
    return None if choices is None else Message(link.strip(), choices)


def checked_choices(start: object) -> Choices | None:
    """A message's "start" as Choices, if it holds a known kind and quality
    and subtitles true or false; else None."""
    if not isinstance(start, dict):
        return None
    kind, quality, subtitles = (
        start.get("kind"),
        start.get("quality"),
        start.get("subtitles"),
    )
    if (
        not isinstance(kind, str)
        or kind not in KINDS
        or not isinstance(quality, str)
        or quality not in QUALITIES
        or not isinstance(subtitles, bool)
    ):
        return None
    return Choices(kind, quality, subtitles)


def allow_to_front() -> None:
    """Let the window that gets the link come to the front. Windows lets only
    some programs take the foreground (the one started by the program in
    front, for example); this one passes its right on, if it has it."""
    if sys.platform == "win32":
        ASFW_ANY = -1
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
