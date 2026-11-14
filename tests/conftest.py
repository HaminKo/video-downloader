import uuid
from pathlib import Path

import pytest

from video_downloader import app, browser, downloader, handoff, places


def own_pipe() -> str:
    """A named pipe no other test and no real window uses."""
    return rf"\\.\pipe\video-downloader-test-{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
def own_files_in_a_temporary_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Point the app at a sign-in file and a history that aren't there (a test
    can write them), and the Chrome button's setup at the same empty folder,
    so tests never use or change the user's real ones; and at a pipe of its
    own, so a link never reaches a real window."""
    folder = tmp_path_factory.mktemp("app-data")
    monkeypatch.setattr(downloader, "COOKIES", folder / "cookies.txt")
    monkeypatch.setattr(app, "HISTORY", folder / "history.json")
    monkeypatch.setattr(browser, "DATA_FOLDER", folder)
    monkeypatch.setattr(places, "DATA_FOLDER", folder)  # for any later reader
    monkeypatch.setattr(handoff, "PIPE", own_pipe())


@pytest.fixture(autouse=True)
def registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Stand in for Chrome's registry key, so no test ever writes the real
    registry: browser.install() puts the manifest's path here under "key"."""
    key: dict[str, Path] = {}
    monkeypatch.setattr(browser, "write_key", lambda path: key.update(key=path))
    monkeypatch.setattr(browser, "delete_key", lambda: key.pop("key", None))
    return key


@pytest.fixture
def pipe() -> str:
    return own_pipe()
