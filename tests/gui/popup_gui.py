"""GUI test of the Chrome button's popup: extension/popup.html in headless
Chrome, with Chrome's extension functions faked (popup.py, fake_chrome.js).

Run it with: pytest tests/gui/popup_gui.py
A plain `pytest` skips it (the file name doesn't start with test_): it needs
Chrome and takes about 1.5 s per case. Nothing reaches the helper or the app;
what the popup would send is recorded. Chrome's real parts (the tab's link,
native messaging, the popup closing) are the user's hand test.
"""

from typing import Any

import pytest
from popup import Case, run

from video_downloader.browser import HOST_NAME
from video_downloader.handoff import Answer
from video_downloader.host import CANCEL_ERRORS, NOT_A_WEB_PAGE

LINK = "https://www.youtube.com/watch?v=abc_123-XYZ"
OK = {"ok": True}
VIDEO_CHOICES = ["quality-best", "quality-720p", "quality-480p", "subtitles"]
BUTTONS = ["download", "open", "cancel"]
NOT_INSTALLED = (
    "The helper isn't installed: run Video Downloader Setup again "
    "(from the project: python -m video_downloader.browser install)."
)


def sent(seen: dict[str, Any]) -> list[object]:
    """The messages the popup sent to the helper; each to HOST_NAME."""
    assert all(each["host"] == HOST_NAME for each in seen["sent"])
    return [each["message"] for each in seen["sent"]]


def test_download_sends_the_link_with_the_choices_and_closes() -> None:
    """Nothing kept yet: the window's own first choices. Download sends them
    with the link, says so, and closes 1.5 s later."""
    seen = run({"url": LINK, "reply": OK, "clicks": ["#mp3", "#download"]})
    start = {"kind": "mp3", "quality": "Best", "subtitles": False}
    assert sent(seen) == [{"link": LINK, "start": start}]
    assert seen["status"] == "Added to Video Downloader."
    assert not seen["error"]
    assert seen["closedAfter"] == 1500


def test_it_opens_with_the_defaults_ready_for_enter() -> None:
    seen = run({"url": LINK})
    assert (seen["kind"], seen["quality"], seen["subtitles"]) == ("mp4", "Best", False)
    assert seen["disabled"] == []
    assert seen["focused"] == "download"  # so Enter downloads
    assert seen["status"] == ""
    assert sent(seen) == []


def test_mp3_greys_out_the_video_choices_and_each_change_is_kept() -> None:
    seen = run({"url": LINK, "clicks": ["#quality-720p", "#subtitles", "#mp3"]})
    assert seen["disabled"] == VIDEO_CHOICES
    assert seen["stored"] == [
        {"kind": "mp4", "quality": "720p", "subtitles": False},
        {"kind": "mp4", "quality": "720p", "subtitles": True},
        {"kind": "mp3", "quality": "720p", "subtitles": True},
    ]
    assert sent(seen) == []


@pytest.mark.parametrize(
    ("kept", "disabled"),
    [
        ({"kind": "mp4", "quality": "480p", "subtitles": True}, []),
        ({"kind": "mp3", "quality": "720p", "subtitles": False}, VIDEO_CHOICES),
    ],
)
def test_the_kept_choices_come_back(
    kept: dict[str, object], disabled: list[str]
) -> None:
    seen = run({"url": LINK, "stored": kept, "reply": OK, "clicks": ["#download"]})
    assert (seen["kind"], seen["quality"], seen["subtitles"]) == tuple(kept.values())
    assert sent(seen) == [{"link": LINK, "start": kept}]
    assert seen["disabled"] == disabled + BUTTONS  # the buttons: sent


def test_kept_choices_it_doesnt_know_give_the_defaults() -> None:
    """For example after a choice is renamed in a later version."""
    kept = {"kind": "flac", "quality": "4K", "subtitles": "yes"}
    seen = run({"url": LINK, "stored": kept})
    assert (seen["kind"], seen["quality"], seen["subtitles"]) == ("mp4", "Best", False)


@pytest.mark.parametrize("url", ["chrome://newtab/", "file:///C:/video.mp4", None])
def test_a_page_that_isnt_a_web_page_says_so_at_once(url: str | None) -> None:
    """None: Chrome gives no link (New Tab, its own pages)."""
    seen = run({"url": url, "reply": OK, "clicks": ["#download", "#open", "#cancel"]})
    assert seen["status"] == NOT_A_WEB_PAGE
    assert seen["error"]
    assert seen["disabled"] == BUTTONS
    assert sent(seen) == []


@pytest.mark.parametrize(
    ("case", "shown"),
    [
        ({"reply": {"ok": False, "error": "It broke."}}, "It broke."),
        ({"reply": {}}, "The helper gave no answer."),
        ({"error": "Specified native messaging host not found."}, NOT_INSTALLED),
        ({"error": "Native host has exited."}, "Native host has exited."),
    ],
)
def test_a_failure_stays_in_the_popup(case: Case, shown: str) -> None:
    """The helper's error, or Chrome's; the popup stays open, Download can be
    tried again."""
    seen = run({**case, "url": LINK, "clicks": ["#download"]})
    assert seen["status"] == shown
    assert seen["error"]
    assert seen["disabled"] == []
    assert seen["focused"] == "download"  # so Enter tries again
    assert seen["closedAfter"] is None


def test_open_in_the_window_sends_the_link_alone_and_closes() -> None:
    seen = run({"url": LINK, "reply": OK, "clicks": ["#mp3", "#open"]})
    assert sent(seen) == [{"link": LINK}]
    assert seen["closedAfter"] == 0  # the window comes to the front


def test_cancel_sends_the_link_says_so_and_closes() -> None:
    """Whatever the choices: only the tab's link counts."""
    seen = run({"url": LINK, "reply": OK, "clicks": ["#mp3", "#cancel"]})
    assert sent(seen) == [{"link": LINK, "cancel": True}]
    assert seen["status"] == "Cancelled."
    assert not seen["error"]
    assert seen["closedAfter"] == 1500


@pytest.mark.parametrize(
    "answer", [Answer.NOTHING, Answer.NOT_OPEN, Answer.NO_ANSWER], ids=str
)
def test_a_cancel_that_didnt_cancel_stays_in_the_popup(answer: Answer) -> None:
    """The helper's words for each answer; Enter then cancels again, it
    mustn't download."""
    error = CANCEL_ERRORS[answer]
    reply = {"ok": False, "error": error}
    seen = run({"url": LINK, "reply": reply, "clicks": ["#cancel"]})
    assert seen["status"] == error
    assert seen["error"]
    assert seen["disabled"] == []
    assert seen["focused"] == "cancel"
    assert seen["closedAfter"] is None


def test_a_failed_open_keeps_the_focus_on_open() -> None:
    reply = {"ok": False, "error": "It broke."}
    seen = run({"url": LINK, "reply": reply, "clicks": ["#open"]})
    assert seen["focused"] == "open"


def test_while_sending_a_second_click_sends_nothing() -> None:
    seen = run(
        {
            "url": LINK,
            "reply": OK,
            "reply_after": 2000,
            "clicks": ["#download", "#download", "#open", "#cancel"],
            "read_at": 1000,
        }
    )
    assert len(sent(seen)) == 1
    assert seen["status"] == "Sending..."
    assert seen["disabled"] == BUTTONS
