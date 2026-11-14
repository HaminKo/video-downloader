import pytest

from video_downloader import app, downloader


@pytest.fixture(autouse=True)
def own_files_in_a_temporary_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Point the app at a sign-in file and a history that aren't there (a test
    can write them), so tests never use or change the user's real ones."""
    folder = tmp_path_factory.mktemp("app-data")
    monkeypatch.setattr(downloader, "COOKIES", folder / "cookies.txt")
    monkeypatch.setattr(app, "HISTORY", folder / "history.json")
