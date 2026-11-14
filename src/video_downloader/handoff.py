"""Hand a link to the window that is open already: the window listens on a
Windows named pipe, and `python -m video_downloader LINK` or the Chrome
button's helper (host.py) sends the link there, alone (the window puts it in
its box) or with the choices to download it with (the window adds it to its
list at once).

The Chrome popup's Cancel goes the same way (cancel()), and the window
answers it on the same connection: whether it cancelled the link's download.

A message is UTF-8 JSON: {"link": "https://..."}, or with the choices too,
{"link": ..., "start": {"kind": "mp3", "quality": "Best", "subtitles": false}},
or {"link": ..., "cancel": true}; the window's answer to a Cancel is
{"answer": "cancelled"} or {"answer": "nothing to cancel"}. The Chrome button
sends its helper the same messages. multiprocessing's send() and recv() are
never used: they unpickle, which runs whatever the sender packs in, while
json.loads only reads data. Web pages can't reach a named pipe
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
from enum import StrEnum
from multiprocessing.connection import Client, Connection, Listener, PipeConnection

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

# How long cancel() waits for the window's answer, in seconds. The window
# itself gives up sooner (app.ANSWER_WITHIN), so its "no answer" comes first.
WAIT_FOR_ANSWER = 5.0


class Answer(StrEnum):
    """How a Cancel sent to the window went (cancel())."""

    CANCELLED = "cancelled"  # the link's download stopped, or won't start
    NOTHING = "nothing to cancel"  # the link isn't downloading or waiting there
    NOT_OPEN = "not open"  # no window listens
    NO_ANSWER = "no answer"  # the window didn't answer in time, or closed


# What the window itself can answer; the others are cancel()'s own.
WINDOW_ANSWERS = (Answer.CANCELLED, Answer.NOTHING)


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
    once; with cancel, to stop its download; otherwise to go in the box."""

    link: str
    start: Choices | None = None
    cancel: bool = False


# Gets a Cancel's link in the listener's thread and returns the window's
# answer, or None for none (the window didn't answer in time).
OnCancel = Callable[[str], Answer | None]


class Listening:
    """Passes each message sent to the pipe to on_message, in a background
    thread, and each Cancel's link to on_cancel (None: a Cancel gets no
    answer), whose answer goes back to the sender; close() stops it."""

    def __init__(
        self,
        pipe: str,
        on_message: Callable[[Message], None],
        on_cancel: OnCancel | None = None,
    ) -> None:
        # PermissionError when another window listens on the pipe already.
        self.listener = Listener(pipe, family="AF_PIPE")
        self.pipe = pipe
        self.on_message = on_message
        self.on_cancel = on_cancel
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
                # Too long, or the sender went away midway (after a Cancel:
                # before its answer); EOFError: before it sent anything. Not
                # caught, either would end this thread, and the window would
                # get no more links.
                with contextlib.suppress(OSError, EOFError):
                    self.take(connection)
        self.listener.close()

    def take(self, connection: Connection | PipeConnection) -> None:
        """Pass on the message sent on the connection; answer a Cancel on it."""
        message = read_message(connection.recv_bytes(LONGEST))
        if message is None:
            return
        if not message.cancel:
            self.on_message(message)
            return
        answer = self.on_cancel(message.link) if self.on_cancel else None
        if answer is not None:
            connection.send_bytes(json.dumps({"answer": answer}).encode("utf-8"))

    def close(self) -> None:
        """Stop listening, so another window can listen on the pipe. The
        thread waits for a sender, so one wakes it up."""
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(OSError):  # it stopped already
            Client(self.pipe, family="AF_PIPE").close()
        self.thread.join(timeout=1)


def listen(
    on_message: Callable[[Message], None],
    pipe: str,
    on_cancel: OnCancel | None = None,
) -> Listening | None:
    """Start passing the messages sent to `pipe` to on_message, and the
    Cancels to on_cancel (both called in another thread). None when it
    can't: mostly because another window listens there already
    (PermissionError), which gets the messages then. The window opens either
    way."""
    try:
        return Listening(pipe, on_message, on_cancel)
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


def cancel(link: str, pipe: str) -> Answer:
    """Ask the window listening on `pipe` to cancel the link's download, and
    wait up to WAIT_FOR_ANSWER seconds for its answer. NOT_OPEN when no
    window listens (FileNotFoundError); NO_ANSWER when it doesn't answer in
    time or hangs up first (EOFError, which isn't an OSError). It never opens
    a window or brings one to the front."""
    message = {"link": link, "cancel": True}
    try:
        with Client(pipe, family="AF_PIPE") as connection:
            connection.send_bytes(json.dumps(message).encode("utf-8"))
            if not connection.poll(WAIT_FOR_ANSWER):
                return Answer.NO_ANSWER
            data = connection.recv_bytes(LONGEST)
    except FileNotFoundError:
        return Answer.NOT_OPEN
    except (OSError, EOFError):
        return Answer.NO_ANSWER
    return read_answer(data)


def read_answer(data: bytes) -> Answer:
    """The window's answer to a Cancel in the bytes it sent; NO_ANSWER for
    one that isn't {"answer": ...} with one of WINDOW_ANSWERS."""
    try:
        answer = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):  # not UTF-8 or JSON; nested too deep
        return Answer.NO_ANSWER
    said = answer.get("answer") if isinstance(answer, dict) else None
    return Answer(said) if said in WINDOW_ANSWERS else Answer.NO_ANSWER


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
    and, if it has "start" at all, known choices (checked_choices()), or if
    it has "cancel" at all, true and no "start"; else None."""
    if not isinstance(message, dict):
        return None
    link = message.get("link")
    if not isinstance(link, str) or not link.strip():
        return None
    if "cancel" in message:
        if message["cancel"] is not True or "start" in message:
            return None
        return Message(link.strip(), cancel=True)
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
