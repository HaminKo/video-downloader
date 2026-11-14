"""Handing a link, alone or with the choices to download it with, to the
open window through a named pipe."""

import contextlib
import json
import queue
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import Client, Connection

import pytest

from video_downloader import handoff
from video_downloader.handoff import (
    LONGEST,
    Choices,
    Listening,
    Message,
    checked_message,
    listen,
    send,
)

LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
START = {"kind": "mp4", "quality": "720p", "subtitles": True}


@contextmanager
def window(pipe: str) -> Iterator[tuple[Listening, queue.Queue[Message]]]:
    """Listen on `pipe` as an open window does; the messages it gets go into
    the queue."""
    links: queue.Queue[Message] = queue.Queue()
    listening = listen(links.put, pipe)
    assert listening is not None, "nothing else listens on a test's own pipe"
    try:
        yield listening, links
    finally:
        listening.close()


def send_raw(pipe: str, data: bytes) -> None:
    # The window hangs up on a message that is too long before reading all of
    # it, so the sender's write breaks off then.
    with (
        contextlib.suppress(BrokenPipeError),
        Client(pipe, family="AF_PIPE") as connection,
    ):
        connection.send_bytes(data)


def test_a_link_reaches_the_open_window(pipe: str) -> None:
    with window(pipe) as (_, links):
        assert send(f"  {LINK}\n", pipe)
        assert links.get(timeout=2) == Message(LINK), "spaces around it go"
        assert send(LINK + "&t=1", pipe), "it goes on listening"
        assert links.get(timeout=2) == Message(LINK + "&t=1")


def test_a_link_with_choices_reaches_the_open_window(pipe: str) -> None:
    with window(pipe) as (_, links):
        assert send(LINK, pipe, Choices("mp3"))
        assert links.get(timeout=2) == Message(LINK, Choices("mp3", "Best", False))
        assert send(LINK, pipe, Choices("mp4", "720p", True))
        assert links.get(timeout=2) == Message(LINK, Choices("mp4", "720p", True))


def test_a_message_is_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same as the Chrome button sends its helper (host.py)."""
    sent: list[bytes] = []

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def send_bytes(self, data: bytes) -> None:
            sent.append(data)

    allowed: list[bytes] = []  # sent when the window was let to the front
    monkeypatch.setattr(handoff, "Client", lambda *_a, **_k: FakeConnection())
    monkeypatch.setattr(handoff, "allow_to_front", lambda: allowed.append(b""))
    assert send(LINK, "pipe")
    assert send(LINK, "pipe", Choices("mp4", "720p", True))
    assert [json.loads(data) for data in sent] == [
        {"link": LINK},
        {"link": LINK, "start": START},
    ]
    assert len(allowed) == 1, "only a link alone brings the window to the front"


@pytest.mark.parametrize(
    "message",
    [
        {"link": LINK, "start": {**START, "kind": "avi"}},
        {"link": LINK, "start": {**START, "kind": ["mp4"]}},
        {"link": LINK, "start": {**START, "quality": "1080p"}},
        {"link": LINK, "start": {**START, "quality": ["720p"]}},  # can't be a key
        {"link": LINK, "start": {**START, "subtitles": "yes"}},
        {"link": LINK, "start": {"kind": "mp3"}},  # all three are always sent
        {"link": LINK, "start": "mp3"},
        {"link": LINK, "start": None},  # not the same as no "start"
        {"link": "   "},
        {"link": 5},
        {"start": START},
        LINK,
        [LINK],
    ],
)
def test_a_message_without_a_link_or_with_unknown_choices_is_dropped(
    message: object,
) -> None:
    assert checked_message(message) is None


def test_without_an_open_window_nothing_is_sent(pipe: str) -> None:
    assert not send(LINK, pipe)


def test_a_window_closing_while_sending_counts_as_none(
    monkeypatch: pytest.MonkeyPatch, pipe: str
) -> None:
    def closing(*_args: object, **_kwargs: object) -> Connection:
        raise BrokenPipeError(109, "The pipe has been ended")

    monkeypatch.setattr(handoff, "Client", closing)
    assert not send(LINK, pipe), "the caller opens a window of its own"


def test_a_pipe_that_cant_be_made_means_no_listening() -> None:
    too_long = r"\\.\pipe" + "\\" + "x" * 300  # Windows allows 256 characters
    assert listen(lambda _message: None, too_long) is None


def test_a_second_window_doesnt_listen(pipe: str) -> None:
    with window(pipe) as (_, links):
        assert listen(lambda _message: None, pipe) is None
        assert send(LINK, pipe)
        assert links.get(timeout=2) == Message(LINK), "the first window gets it"


def test_a_closed_window_lets_another_listen(pipe: str) -> None:
    with window(pipe) as (listening, _):
        listening.close()
        assert not send(LINK, pipe)
    with window(pipe) as (_, links):
        assert send(LINK, pipe)
        assert links.get(timeout=2) == Message(LINK)


@pytest.mark.parametrize(
    "junk",
    [
        b"",
        b"   \n",
        b"\xff\xfe not text",
        b"x" * (LONGEST + 1),
        LINK.encode(),  # plain text, as before To do 16: not JSON
        b'{"link": "https://example.com", "start": {"kind": "avi"}}',
        b"[" * 60_000,  # json.loads gives up (RecursionError)
    ],
    ids=["empty", "spaces", "not UTF-8", "too long", "text", "bad choices", "deep"],
)
def test_junk_is_dropped(pipe: str, junk: bytes) -> None:
    with window(pipe) as (_, links):
        send_raw(pipe, junk)
        assert send(LINK, pipe), "it goes on listening"
        assert links.get(timeout=2) == Message(LINK), "the junk never arrives"
        assert links.empty()


class RunsWhenUnpickled:
    """Unpickling this calls ran.append("ran"): a stand-in for a sender that
    packs code into a pickle."""

    ran: list[str] = []

    def __reduce__(self) -> tuple[object, tuple[str]]:
        return (RunsWhenUnpickled.ran.append, ("ran",))


def test_a_pickle_is_never_unpickled(pipe: str) -> None:
    with window(pipe) as (_, links):
        with Client(pipe, family="AF_PIPE") as connection:
            connection.send(RunsWhenUnpickled())  # pickles it
        assert send(LINK, pipe)
        assert links.get(timeout=2) == Message(LINK)
        assert links.empty(), "a pickle isn't JSON, so it is dropped"
    assert RunsWhenUnpickled.ran == []
