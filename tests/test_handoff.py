"""Handing a link to the open window through a named pipe."""

import contextlib
import queue
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import Client, Connection

import pytest

from video_downloader import handoff
from video_downloader.handoff import LONGEST, Listening, listen, send

LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@contextmanager
def window(pipe: str) -> Iterator[tuple[Listening, queue.Queue[str]]]:
    """Listen on `pipe` as an open window does; the links it gets go into the
    queue."""
    links: queue.Queue[str] = queue.Queue()
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
        assert links.get(timeout=2) == LINK, "spaces around it are dropped"
        assert send(LINK + "&t=1", pipe), "it goes on listening"
        assert links.get(timeout=2) == LINK + "&t=1"


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
    assert listen(lambda _link: None, too_long) is None


def test_a_second_window_doesnt_listen(pipe: str) -> None:
    with window(pipe) as (_, links):
        assert listen(lambda _link: None, pipe) is None
        assert send(LINK, pipe)
        assert links.get(timeout=2) == LINK, "the first window gets the links"


def test_a_closed_window_lets_another_listen(pipe: str) -> None:
    with window(pipe) as (listening, _):
        listening.close()
        assert not send(LINK, pipe)
    with window(pipe) as (_, links):
        assert send(LINK, pipe)
        assert links.get(timeout=2) == LINK


@pytest.mark.parametrize(
    "junk",
    [b"", b"   \n", b"\xff\xfe not text", b"x" * (LONGEST + 1)],
    ids=["empty", "spaces", "not UTF-8", "too long"],
)
def test_junk_is_dropped(pipe: str, junk: bytes) -> None:
    with window(pipe) as (_, links):
        send_raw(pipe, junk)
        assert send(LINK, pipe), "it goes on listening"
        assert links.get(timeout=2) == LINK, "the junk never arrives"
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
        assert links.get(timeout=2) == LINK
        assert links.empty(), "a pickle isn't text, so it is dropped"
    assert RunsWhenUnpickled.ran == []
