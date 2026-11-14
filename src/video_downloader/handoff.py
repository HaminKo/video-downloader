"""Hand a link to the window that is open already: the window listens on a
Windows named pipe, and `python -m video_downloader LINK` (later the Chrome
button's helper) sends the link there.

A message is the link as UTF-8 text, nothing else. multiprocessing's send()
and recv() are never used: they unpickle, which runs whatever the sender
packs in. Web pages can't reach a named pipe (docs/research/browser-button.md).
"""

import contextlib
import ctypes
import sys
import threading
from collections.abc import Callable
from multiprocessing.connection import Client, Listener

# The real window's pipe; callers always name the pipe, so the tests can
# replace this one (tests/conftest.py).
PIPE = r"\\.\pipe\video-downloader"

# The longest message read, in bytes; a longer one is dropped. Links are far
# shorter (YouTube's about 45 characters).
LONGEST = 64 * 1024


class Listening:
    """Passes each link sent to the pipe to on_link, in a background thread;
    close() stops it."""

    def __init__(self, pipe: str, on_link: Callable[[str], None]) -> None:
        # PermissionError when another window listens on the pipe already.
        self.listener = Listener(pipe, family="AF_PIPE")
        self.pipe = pipe
        self.on_link = on_link
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
            link = read_link(data)
            if link:
                self.on_link(link)
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


def listen(on_link: Callable[[str], None], pipe: str) -> Listening | None:
    """Start passing the links sent to `pipe` to on_link (called in another
    thread). None when it can't: mostly because another window listens there
    already (PermissionError), which gets the links then. The window opens
    either way."""
    try:
        return Listening(pipe, on_link)
    except OSError:
        return None


def send(link: str, pipe: str) -> bool:
    """Hand `link` to the window listening on `pipe`; False when there is
    none (FileNotFoundError), or it is closing or stuck: the caller opens a
    window of its own then."""
    allow_to_front()
    try:
        with Client(pipe, family="AF_PIPE") as connection:
            connection.send_bytes(link.encode("utf-8"))
    except OSError:
        return False
    return True


def read_link(data: bytes) -> str:
    """The link in a message, or "" for one that isn't text."""
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


def allow_to_front() -> None:
    """Let the window that gets the link come to the front. Windows lets only
    some programs take the foreground (the one started by the program in
    front, for example); this one passes its right on, if it has it."""
    if sys.platform == "win32":
        ASFW_ANY = -1
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
