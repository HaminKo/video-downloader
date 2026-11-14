"""Handing a link, alone or with the choices to download it with, to the
open window through a named pipe; and a Cancel, which the window answers."""

import contextlib
import json
import queue
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import Client, Connection

import pytest

from video_downloader import handoff
from video_downloader.handoff import (
    LONGEST,
    SHOW,
    Answer,
    Choices,
    Listening,
    Message,
    OnCancel,
    cancel,
    checked_message,
    listen,
    read_answer,
    send,
    show,
)

LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
START = {"kind": "mp4", "quality": "720p", "subtitles": True}


@contextmanager
def window(
    pipe: str, on_cancel: OnCancel | None = None
) -> Iterator[tuple[Listening, queue.Queue[Message]]]:
    """Listen on `pipe` as an open window does; the messages it gets go into
    the queue, its Cancels to on_cancel."""
    links: queue.Queue[Message] = queue.Queue()
    listening = listen(pipe)
    assert listening is not None, "nothing else listens on a test's own pipe"
    listening.start(links.put, on_cancel)
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

        def poll(self, timeout: float) -> bool:
            return False  # no answer

    allowed: list[bytes] = []  # sent when the window was let to the front
    monkeypatch.setattr(handoff, "Client", lambda *_a, **_k: FakeConnection())
    monkeypatch.setattr(handoff, "allow_to_front", lambda: allowed.append(b""))
    assert send(LINK, "pipe")
    assert send(LINK, "pipe", Choices("mp4", "720p", True))
    assert cancel(LINK, "pipe") is Answer.NO_ANSWER
    assert show("pipe")
    assert [json.loads(data) for data in sent] == [
        {"link": LINK},
        {"link": LINK, "start": START},
        {"link": LINK, "cancel": True},
        {"show": True},
    ]
    assert len(allowed) == 2, "only a link alone and a show bring it to the front"


def test_a_cancel_message_holds_a_link() -> None:
    message = {"link": f" {LINK} ", "cancel": True}
    assert checked_message(message) == Message(LINK, cancel=True)


def test_a_show_reaches_the_open_window(pipe: str) -> None:
    with window(pipe) as (_, links):
        assert show(pipe)
        assert links.get(timeout=2) == SHOW == Message("", show=True)


def test_without_an_open_window_a_show_says_so(pipe: str) -> None:
    assert not show(pipe)


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
        {"link": LINK, "cancel": False},
        {"link": LINK, "cancel": "yes"},
        {"link": LINK, "cancel": True, "start": START},  # which one?
        {"link": "  ", "cancel": True},
        {"cancel": True},
        {"show": False},
        {"show": 1},  # equal to True in Python, but not true in JSON
        {"show": True, "link": LINK},  # which one?
        {"show": True, "cancel": True},
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
    assert cancel(LINK, pipe) is Answer.NO_ANSWER


@pytest.mark.parametrize("answer", [Answer.CANCELLED, Answer.NOTHING])
def test_a_cancel_gets_the_windows_answer(answer: Answer, pipe: str) -> None:
    asked: list[str] = []

    def on_cancel(link: str) -> Answer:
        asked.append(link)
        return answer

    with window(pipe, on_cancel) as (_, links):
        assert cancel(LINK, pipe) is answer
        assert asked == [LINK]
        assert send(LINK, pipe), "it goes on listening"
        assert links.get(timeout=2) == Message(LINK), "the Cancel isn't a link"
        assert links.empty()


def test_without_an_open_window_a_cancel_says_so(pipe: str) -> None:
    assert cancel(LINK, pipe) is Answer.NOT_OPEN


@pytest.mark.parametrize(
    "on_cancel", [None, lambda _link: None], ids=["no on_cancel", "none in time"]
)
def test_a_window_that_doesnt_answer_a_cancel(
    on_cancel: OnCancel | None, pipe: str
) -> None:
    """It hangs up without answering: the sender knows at once."""
    with window(pipe, on_cancel):
        started = time.monotonic()
        assert cancel(LINK, pipe) is Answer.NO_ANSWER
        assert time.monotonic() - started < 1, "not the full wait"


def test_a_window_too_slow_to_answer_a_cancel(
    monkeypatch: pytest.MonkeyPatch, pipe: str
) -> None:
    """The sender gives up; the late answer then finds it gone, and the
    window goes on listening."""
    monkeypatch.setattr(handoff, "WAIT_FOR_ANSWER", 0.2)
    answered = threading.Event()

    def slow(_link: str) -> Answer:
        time.sleep(0.6)
        answered.set()
        return Answer.CANCELLED

    with window(pipe, slow) as (_, links):
        assert cancel(LINK, pipe) is Answer.NO_ANSWER
        assert answered.wait(timeout=5)
        assert send(LINK, pipe)
        assert links.get(timeout=2) == Message(LINK)


@pytest.mark.parametrize(
    ("data", "answer"),
    [
        (b'{"answer": "cancelled"}', Answer.CANCELLED),
        (b'{"answer": "nothing to cancel"}', Answer.NOTHING),
        (b'{"answer": "not open"}', Answer.NO_ANSWER),  # not the window's to say
        (b'{"answer": "maybe"}', Answer.NO_ANSWER),
        (b'{"answer": ["cancelled"]}', Answer.NO_ANSWER),
        (b'"cancelled"', Answer.NO_ANSWER),
        (b"\xff\xfe", Answer.NO_ANSWER),
        (b"[" * 60_000, Answer.NO_ANSWER),
    ],
)
def test_only_a_known_answer_counts(data: bytes, answer: Answer) -> None:
    assert read_answer(data) is answer


def test_a_pipe_that_cant_be_made_means_no_listening() -> None:
    too_long = r"\\.\pipe" + "\\" + "x" * 300  # Windows allows 256 characters
    assert listen(too_long) is None


def test_a_second_window_cant_take_the_pipe(pipe: str) -> None:
    with window(pipe) as (_, links):
        with pytest.raises(PermissionError):
            listen(pipe)
        assert send(LINK, pipe)
        assert links.get(timeout=2) == Message(LINK), "the first window gets it"


def test_what_is_sent_before_the_window_reads_waits_for_it(pipe: str) -> None:
    """A window takes the pipe before it is built and reads only then; the
    first sender is through at once, the next one waits (it would wait up to
    20 s, multiprocessing's limit)."""
    listening = listen(pipe)
    assert listening is not None
    links: queue.Queue[Message] = queue.Queue()
    try:
        assert send(LINK, pipe, Choices("mp3"))
        second = threading.Thread(target=show, args=(pipe,))
        second.start()
        time.sleep(0.3)
        assert second.is_alive(), "the second sender waits for the window"
        assert links.empty()
        listening.start(links.put)
        assert links.get(timeout=5) == Message(LINK, Choices("mp3"))
        assert links.get(timeout=5) == SHOW, "in the order sent"
        second.join(timeout=5)
    finally:
        listening.close()
    assert not send(LINK, pipe), "closed: the pipe is gone"


def test_a_pipe_taken_but_never_read_can_be_closed(pipe: str) -> None:
    listening = listen(pipe)
    assert listening is not None
    listening.close()
    listening.close()  # twice is fine
    assert not send(LINK, pipe)
    again = listen(pipe)  # free for another window
    assert again is not None
    again.close()


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


def test_a_sender_that_hangs_up_before_sending(pipe: str) -> None:
    """For example the helper, ended by Chrome right after connecting: the
    window reads EOFError, and must go on listening."""
    with window(pipe) as (_, links):
        Client(pipe, family="AF_PIPE").close()
        assert send(LINK, pipe)
        assert links.get(timeout=2) == Message(LINK)


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
