import uuid

import pytest

from video_downloader import app, downloader, handoff


def own_pipe() -> str:
    """A named pipe no other test and no real window uses."""
    return rf"\\.\pipe\video-downloader-test-{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
def own_files_in_a_temporary_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Point the app at a sign-in file and a history that aren't there (a test
    can write them), so tests never use or change the user's real ones; and
    at a pipe of its own, so a link never reaches a real window."""
    folder = tmp_path_factory.mktemp("app-data")
    monkeypatch.setattr(downloader, "COOKIES", folder / "cookies.txt")
    monkeypatch.setattr(app, "HISTORY", folder / "history.json")
    monkeypatch.setattr(handoff, "PIPE", own_pipe())


@pytest.fixture
def pipe() -> str:
    return own_pipe()
