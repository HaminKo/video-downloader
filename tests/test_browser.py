"""The Chrome button: its helper (host.py), its setup (browser.py) and the
extension's ID. Never the registry (tests/conftest.py fakes it) and never a
real Chrome."""

import base64
import hashlib
import io
import json
import os
import queue
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_downloader import app, browser, handoff, host
from video_downloader.browser import EXTENSION_FOLDER, EXTENSION_ID, HOST_NAME
from video_downloader.handoff import Answer, Choices, Message
from video_downloader.host import BAD_CHOICES, BAD_MESSAGE, LENGTH, NOT_A_WEB_PAGE

LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
OK = {"ok": True}
START = {"kind": "mp4", "quality": "720p", "subtitles": True}


class Opened(list[tuple[str, Choices | None]]):
    """Stands in for host.start_window: records the windows the helper would
    open, each a link and its choices."""

    def __call__(self, link: str, start: Choices | None) -> None:
        self.append((link, start))


def framed(message: object) -> bytes:
    """A message as Chrome sends it: its length in 4 bytes, then the JSON."""
    data = json.dumps(message).encode("utf-8")
    return LENGTH.pack(len(data)) + data


def serve(data: bytes, pipe: str, open_window: host.OpenWindow) -> object:
    """Run the helper with data as its stdin; its reply."""
    stdout = io.BytesIO()
    host.serve(io.BytesIO(data), stdout, pipe, open_window)
    return host.read_message(io.BytesIO(stdout.getvalue()))


def extension_id(key: str) -> str:
    """The ID Chrome gives an extension with this manifest "key" (a public
    key in base64): the first 32 hex digits of its SHA-256, with a-p for 0-f
    (Chromium, components/crx_file/id_util.cc)."""
    digest = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(digit, 16)) for digit in digest)


def test_a_message_is_its_length_in_4_bytes_then_json() -> None:
    stream = io.BytesIO()
    host.write_message(stream, {"link": "a"})
    assert stream.getvalue() == b'\x0d\x00\x00\x00{"link": "a"}'
    assert host.read_message(io.BytesIO(stream.getvalue())) == {"link": "a"}


@pytest.mark.parametrize(
    ("message", "received"),
    [
        ({"link": LINK}, Message(LINK)),
        ({"link": LINK, "start": START}, Message(LINK, Choices("mp4", "720p", True))),
    ],
    ids=["link", "with choices"],
)
def test_a_link_goes_to_the_open_window(
    message: object, received: Message, pipe: str
) -> None:
    links: queue.Queue[Message] = queue.Queue()
    listening = handoff.listen(pipe)
    assert listening is not None
    listening.start(links.put)
    opened = Opened()
    try:
        assert serve(framed(message), pipe, opened) == OK
        assert links.get(timeout=5) == received
    finally:
        listening.close()
    assert opened == []


@pytest.mark.parametrize(
    ("answer", "reply"),
    [
        (Answer.CANCELLED, OK),
        (
            Answer.NOTHING,
            {
                "ok": False,
                "error": "Nothing to cancel: "
                "Video Downloader isn't downloading this page.",
            },
        ),
        (None, {"ok": False, "error": "Video Downloader didn't answer."}),
    ],
    ids=["cancelled", "nothing", "no answer"],
)
def test_a_cancel_goes_to_the_open_window(
    answer: Answer | None, reply: dict[str, object], pipe: str
) -> None:
    asked: list[str] = []

    def on_cancel(link: str) -> Answer | None:
        asked.append(link)
        return answer

    listening = handoff.listen(pipe)
    assert listening is not None
    listening.start(lambda _message: None, on_cancel)
    opened = Opened()
    try:
        message = {"link": f" {LINK} ", "cancel": True}
        assert serve(framed(message), pipe, opened) == reply
    finally:
        listening.close()
    assert asked == [LINK]
    assert opened == []


def test_with_no_window_open_a_cancel_opens_none(pipe: str) -> None:
    opened = Opened()
    reply = serve(framed({"link": LINK, "cancel": True}), pipe, opened)
    assert reply == {"ok": False, "error": "Video Downloader isn't open."}
    assert opened == []


def test_with_no_window_open_one_opens_with_the_link(pipe: str) -> None:
    opened = Opened()
    assert serve(framed({"link": f" {LINK} "}), pipe, opened) == OK
    assert serve(framed({"link": LINK, "start": START}), pipe, opened) == OK
    assert opened == [(LINK, None), (LINK, Choices("mp4", "720p", True))]


@pytest.mark.parametrize(
    "start",
    [
        {**START, "kind": "avi"},
        {**START, "quality": "1080p"},
        {"kind": "mp3"},
        "mp3",
        None,
    ],
)
def test_unknown_choices_get_an_error(start: object, pipe: str) -> None:
    opened = Opened()
    reply = serve(framed({"link": LINK, "start": start}), pipe, opened)
    assert reply == {"ok": False, "error": BAD_CHOICES}
    assert opened == []


@pytest.mark.parametrize("cancel", ["yes", False, None])
def test_a_cancel_that_isnt_true_gets_an_error(cancel: object, pipe: str) -> None:
    opened = Opened()
    reply = serve(framed({"link": LINK, "cancel": cancel}), pipe, opened)
    assert reply == {"ok": False, "error": BAD_CHOICES}
    assert opened == []


@pytest.mark.parametrize(
    "message",
    [
        {"link": "chrome://newtab/"},
        {"link": "file:///C:/Users/Public/clip.mp4"},
        {"link": ""},
        {"link": 5},
        {},
        [LINK],
    ],
)
def test_only_a_web_page_is_sent(message: object, pipe: str) -> None:
    opened = Opened()
    reply = serve(framed(message), pipe, opened)
    assert reply == {"ok": False, "error": NOT_A_WEB_PAGE}
    assert opened == []


@pytest.mark.parametrize(
    "data",
    [
        b"",  # nothing at all
        b"\x05\x00",  # half a length
        LENGTH.pack(100) + b'{"link"',  # shorter than it says
        LENGTH.pack(handoff.LONGEST + 1) + b"{}",  # longer than a link can be
        LENGTH.pack(5) + b"hello",  # not JSON
        LENGTH.pack(2) + b"\xff\xfe",  # not UTF-8
        LENGTH.pack(60_000) + b"[" * 60_000,  # too deep for json.loads
    ],
)
def test_a_broken_message_gets_an_error(data: bytes, pipe: str) -> None:
    opened = Opened()
    assert serve(data, pipe, opened) == {"ok": False, "error": BAD_MESSAGE}
    assert opened == []


def test_a_window_that_cant_open_gets_an_error(pipe: str) -> None:
    def cant_open(link: str, start: Choices | None) -> None:
        raise FileNotFoundError(2, "The system cannot find the file specified")

    reply = serve(framed({"link": LINK}), pipe, cant_open)
    assert isinstance(reply, dict)
    assert reply["ok"] is False
    assert "window couldn't be opened" in reply["error"]


def test_the_window_gets_a_fresh_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not Chrome's PATH, which may be days old (no ffmpeg in it)."""
    started: list[tuple[list[object], dict[str, object]]] = []
    monkeypatch.setattr(
        host.subprocess,
        "Popen",
        lambda command, **options: started.append((command, options)),
    )
    monkeypatch.setattr(host, "fresh_path", lambda: r"C:\Fresh")
    host.start_window(LINK, None)
    [(command, options)] = started
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    assert command == [pythonw, "-m", "video_downloader", "--", LINK]
    env = options["env"]
    assert isinstance(env, dict)
    assert env["PATH"] == r"C:\Fresh"
    assert env["SYSTEMROOT"] == os.environ["SYSTEMROOT"]  # the rest stays
    assert options["stdout"] == subprocess.DEVNULL


@pytest.mark.parametrize(
    "start", [None, Choices("mp3"), Choices("mp4", "480p", True)], ids=str
)
def test_the_window_opened_gets_the_link_and_choices(
    start: Choices | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app's command line (app.main()) reads back what the helper puts
    on it. handoff.PIPE is the test's own (conftest.py): no window listens."""
    opened: list[dict[str, object]] = []

    def fake_start(**options: object) -> SimpleNamespace:
        opened.append(options)
        return SimpleNamespace(
            root=SimpleNamespace(mainloop=lambda: None),
            look_for_update=lambda check: None,  # never the real check
        )

    monkeypatch.setattr(app, "start", fake_start)
    app.main(host.window_arguments(LINK, start))
    [options] = opened
    listening = options.pop("listening")
    assert isinstance(listening, handoff.Listening)
    listening.close()
    assert options == {"link": LINK, "choices": start}


def test_a_fresh_path_has_the_system_folders_spelled_out() -> None:
    """Windows' own folder is in every PC's PATH, as %SystemRoot%\\system32."""
    folders = [folder.lower() for folder in host.fresh_path().split(";")]
    system32 = str(Path(os.environ["SYSTEMROOT"]) / "system32").lower()
    assert system32 in folders
    assert not any("%systemroot%" in folder for folder in folders)


def test_install_writes_the_helper_and_points_chrome_at_it(
    tmp_path: Path, registry: dict[str, Path]
) -> None:
    folder = tmp_path / "video-downloader"
    browser.install(folder, Path(r"C:\Python Folder\python.exe"))
    bat = folder / "host.bat"
    expected = '@"C:\\Python Folder\\python.exe" -m video_downloader.host\n'
    assert bat.read_text(encoding="oem") == expected
    manifest = folder / "host.json"
    assert json.loads(manifest.read_text(encoding="utf-8")) == {
        "name": HOST_NAME,
        "description": "Video Downloader: gets links from the Chrome button",
        "path": str(bat),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"],
    }
    assert registry == {"key": manifest}


def test_uninstall_removes_only_the_helper(
    tmp_path: Path, registry: dict[str, Path]
) -> None:
    browser.install(tmp_path, Path(sys.executable))
    others = [tmp_path / "history.json", tmp_path / "cookies.txt"]
    for file in others:
        file.write_text("kept", encoding="utf-8")
    browser.uninstall(tmp_path)
    assert sorted(tmp_path.iterdir()) == sorted(others)
    assert registry == {}
    browser.uninstall(tmp_path)  # once more: nothing there, no error


def test_install_says_what_to_do_in_chrome(capsys: pytest.CaptureFixture[str]) -> None:
    browser.main(["install"])
    out = capsys.readouterr().out
    assert str(EXTENSION_FOLDER) in out
    assert EXTENSION_ID in out
    assert (browser.DATA_FOLDER / "host.json").exists()  # conftest's folder
    browser.main(["uninstall"])
    assert not (browser.DATA_FOLDER / "host.json").exists()


def test_host_bat_answers_chrome_through_cmd(tmp_path: Path) -> None:
    """Run host.bat the way Chrome does (through cmd.exe, with Chrome's
    arguments): nothing but the reply may reach stdout, and both ways must
    be binary. The message is 26 bytes long, Ctrl+Z, which ends a text-mode
    read. Its page isn't a web page, so it never reaches a pipe."""
    browser.install(tmp_path, Path(sys.executable))
    base = len(json.dumps({"link": "chrome://"}))
    message = {"link": "chrome://" + "a" * (26 - base)}
    assert len(framed(message)) == 4 + 26
    bat = tmp_path / "host.bat"
    command = (
        f'cmd.exe /d /s /c ""{bat}" chrome-extension://{EXTENSION_ID}/ '
        '--parent-window=0"'
    )
    result = subprocess.run(
        command, input=framed(message), capture_output=True, timeout=60
    )
    assert result.stdout == framed({"ok": False, "error": NOT_A_WEB_PAGE})
    assert result.returncode == 0, result.stderr


def test_the_extension_matches_the_helper() -> None:
    """Its key gives EXTENSION_ID; the popup calls the helper by HOST_NAME,
    offers the choices handoff.py takes, in the window's order, and checks
    for web pages with the helper's words. What the popup does with them:
    tests/gui/popup_gui.py."""
    manifest = json.loads(
        (EXTENSION_FOLDER / "manifest.json").read_text(encoding="utf-8")
    )
    assert extension_id(manifest["key"]) == EXTENSION_ID
    assert manifest["action"]["default_popup"] == "popup.html"
    script = (EXTENSION_FOLDER / "popup.js").read_text(encoding="utf-8")
    assert f"const HOST = {json.dumps(HOST_NAME)};" in script
    assert f"const NOT_A_WEB_PAGE = {json.dumps(NOT_A_WEB_PAGE)};" in script
    page = (EXTENSION_FOLDER / "popup.html").read_text(encoding="utf-8")
    kinds = re.findall(r'name="kind" value="([^"]*)"', page)
    qualities = re.findall(r'name="quality" value="([^"]*)"', page)
    assert tuple(kinds) == handoff.KINDS
    assert qualities == list(handoff.QUALITIES)
