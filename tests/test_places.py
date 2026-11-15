"""Where the app's parts are, in the project and in the built app (sys.frozen
faked: PyInstaller sets it, and sys.executable is then the .exe)."""

import sys
from pathlib import Path

import pytest

from video_downloader import places

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def built_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Run as chrome-helper.exe in a built app's folder; that folder."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / places.HELPER_EXE))
    return tmp_path


def test_from_the_project() -> None:
    assert not places.built()
    assert places.extension_folder() == PROJECT / "extension"
    assert (places.extension_folder() / "manifest.json").is_file()
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    assert places.app_command() == [pythonw, "-m", "video_downloader"]


def test_in_the_built_app(built_app: Path) -> None:
    assert places.built()
    assert places.extension_folder() == built_app / "extension"
    assert places.ytdlp_folder() == built_app / "yt-dlp"
    assert places.app_command() == [str(built_app / "Video Downloader.exe")]
