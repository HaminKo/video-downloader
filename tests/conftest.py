import pytest

from video_downloader import downloader


@pytest.fixture(autouse=True)
def sign_in_file_in_a_temporary_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Point the app at a sign-in file that isn't there (a test can write it),
    so tests never use the user's real one."""
    folder = tmp_path_factory.mktemp("sign-ins")
    monkeypatch.setattr(downloader, "COOKIES", folder / "cookies.txt")
