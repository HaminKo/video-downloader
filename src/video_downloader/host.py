"""The Chrome button's helper (the button: extension/). Chrome starts it for
each click, through the host.bat that `python -m video_downloader.browser
install` writes, as `python -m video_downloader.host`. It reads the one
message the button sends, {"link": "https://..."} or with the choices to
download it with, {"link": ..., "start": {"kind": "mp3", "quality": "Best",
"subtitles": false}} (handoff.py checks them). It hands both to the open
window (handoff.py) or opens a window with them, and replies {"ok": true} or
{"ok": false, "error": "..."}; the button shows the error. The popup's
Cancel sends {"link": ..., "cancel": true}: the helper asks the open window
to cancel that link's download and replies with how it went; with no window
open, it opens none.

Native messaging: a message is UTF-8 JSON after its length in 4 bytes (this
PC's byte order), on stdin and stdout, which Python opens in binary mode on
Windows (docs/research/browser-button.md). This module imports nothing slow
(not yt-dlp), so a click gets its answer quickly.
"""

import json
import os
import struct
import subprocess
import sys
import winreg
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from video_downloader import handoff

NOT_A_WEB_PAGE = "Only web pages can be sent."
BAD_MESSAGE = "The helper couldn't read the message from Chrome."
BAD_CHOICES = "The helper doesn't know the choices Chrome sent."
CANT_OPEN = "The app's window couldn't be opened ({error})."

# What the popup shows when a Cancel didn't cancel (handoff.cancel()).
CANCEL_ERRORS = {
    handoff.Answer.NOTHING: (
        "Nothing to cancel: Video Downloader isn't downloading this page."
    ),
    handoff.Answer.NOT_OPEN: "Video Downloader isn't open.",
    handoff.Answer.NO_ANSWER: "Video Downloader didn't answer.",
}

# A message's length: 32 bits, unsigned, in this PC's byte order.
LENGTH = struct.Struct("=I")

# Where Windows keeps PATH: the system's part, then the user's.
PATH_KEYS = (
    (
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
    ),
    (winreg.HKEY_CURRENT_USER, "Environment"),
)


class BadMessage(Exception):
    """Not a 4-byte length and that much JSON, or longer than a link can be."""


def read_message(stream: BinaryIO) -> object:
    """The one message on stream, as JSON gives it."""
    header = stream.read(LENGTH.size)
    if len(header) < LENGTH.size:
        raise BadMessage
    (length,) = LENGTH.unpack(header)
    if length > handoff.LONGEST:
        raise BadMessage
    data = stream.read(length)
    if len(data) < length:
        raise BadMessage
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError) as error:  # not UTF-8 or JSON; too deep
        raise BadMessage from error


def write_message(stream: BinaryIO, message: object) -> None:
    data = json.dumps(message).encode("utf-8")
    stream.write(LENGTH.pack(len(data)) + data)
    stream.flush()


def web_link(message: object) -> str:
    """The message's link if it is a web page's, else ""."""
    link = message.get("link") if isinstance(message, dict) else None
    if not isinstance(link, str):
        return ""
    link = link.strip()
    return link if link.lower().startswith(("http://", "https://")) else ""


def fresh_path() -> str:
    """PATH as a program started now gets it: the system's part, then the
    user's, from the registry. Chrome keeps the PATH it was started with, for
    days, so it lacks programs installed since (ffmpeg, Deno) and folders
    that changed (an ffmpeg update); the window would then miss them too.
    This PC's PATH if the registry can't be read."""
    parts = []
    for root, key in PATH_KEYS:
        try:
            with winreg.OpenKey(root, key) as opened:
                value, _ = winreg.QueryValueEx(opened, "Path")
        except OSError:  # no such value
            continue
        parts.append(winreg.ExpandEnvironmentStrings(str(value)))
    return ";".join(parts) or os.environ.get("PATH", "")


def window_arguments(link: str, start: handoff.Choices | None) -> list[str]:
    """The app's command line (`python -m video_downloader ...`) for the link
    and the choices to download it with, if any. `--` before the link: it
    never counts as an option."""
    options = []
    if start is not None:
        options = ["--download", start.kind, "--quality", start.quality]
        if start.subtitles:
            options.append("--subtitles")
    return [*options, "--", link]


def start_window(link: str, start: handoff.Choices | None) -> None:
    """Start the app with the link in its box, or downloading it with the
    choices (window_arguments), without a console, with a fresh PATH
    (fresh_path). It gets none of Chrome's pipes (DEVNULL), so it lives on
    after this helper and after Chrome."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    subprocess.Popen(
        [pythonw, "-m", "video_downloader", *window_arguments(link, start)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        env={**os.environ, "PATH": fresh_path()},
    )


# Opens the app's window with a link, and choices to download it with or None.
OpenWindow = Callable[[str, handoff.Choices | None], None]


def answer(message: object, pipe: str, open_window: OpenWindow) -> dict[str, object]:
    """Hand the message's link, with its choices if any, to the window
    listening on pipe, or open a window with them; for a Cancel, ask that
    window to cancel the link's download. The reply for the button."""
    if not web_link(message):
        return {"ok": False, "error": NOT_A_WEB_PAGE}
    checked = handoff.checked_message(message)
    if checked is None:  # the link is fine: the choices (or Cancel) aren't
        return {"ok": False, "error": BAD_CHOICES}
    link, start = checked.link, checked.start
    if checked.cancel:
        how = handoff.cancel(link, pipe)
        if how is handoff.Answer.CANCELLED:
            return {"ok": True}
        return {"ok": False, "error": CANCEL_ERRORS[how]}
    if not handoff.send(link, pipe, start):
        try:
            open_window(link, start)
        except OSError as error:
            return {"ok": False, "error": CANT_OPEN.format(error=error)}
    return {"ok": True}


def serve(
    stdin: BinaryIO,
    stdout: BinaryIO,
    pipe: str,
    open_window: OpenWindow = start_window,
) -> None:
    """Read one message, act on it, reply."""
    try:
        message = read_message(stdin)
    except BadMessage:
        reply: dict[str, object] = {"ok": False, "error": BAD_MESSAGE}
    else:
        reply = answer(message, pipe, open_window)
    write_message(stdout, reply)


if __name__ == "__main__":
    serve(sys.stdin.buffer, sys.stdout.buffer, handoff.PIPE)
