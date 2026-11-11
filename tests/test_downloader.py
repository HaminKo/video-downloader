import shutil
import subprocess
import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yt_dlp

from video_downloader.downloader import (
    PRESETS,
    Done,
    Event,
    Failed,
    Kind,
    Progress,
    download,
    options,
    progress,
    size_text,
)


@pytest.mark.parametrize("kind", list(Kind))
def test_settings_are_yt_dlps_own_presets(kind: Kind) -> None:
    # Fails after a yt-dlp update that changed its -t mp4 or -t mp3 preset:
    # then decide whether to follow it (docs/decisions.md).
    plain = yt_dlp.parse_options(["--ignore-config"]).ydl_opts
    preset = yt_dlp.parse_options(["--ignore-config", "-t", kind]).ydl_opts
    changed: dict[str, Any] = {
        key: value for key, value in preset.items() if plain.get(key) != value
    }
    changed["postprocessors"] = [
        step for step in changed["postprocessors"] if step["key"] != "FFmpegConcat"
    ]
    assert changed == PRESETS[kind]


def test_options_save_by_title_in_the_folder_one_video_only(tmp_path: Path) -> None:
    settings = options(Kind.MP4, tmp_path)
    assert settings.get("paths") == {"home": str(tmp_path)}
    assert settings.get("outtmpl") == "%(title).150B.%(ext)s"
    assert settings.get("noplaylist") is True
    assert settings.get("playlist_items") == "1"
    assert settings.get("merge_output_format") == "mp4"
    assert options(Kind.MP3, tmp_path).get("final_ext") == "mp3"


def test_options_are_a_copy() -> None:
    copied = options(Kind.MP3, Path()).get("postprocessors")
    assert copied == PRESETS[Kind.MP3].get("postprocessors")
    assert copied is not PRESETS[Kind.MP3].get("postprocessors")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            {
                "downloaded_bytes": 12 * 1024**2,
                "total_bytes": 24 * 1024**2,
                "info_dict": {"vcodec": "avc1", "acodec": "none"},
            },
            Progress("Downloading video: 50% of 24 MB", 50.0),
        ),
        (
            {
                "downloaded_bytes": 1024**2,
                "total_bytes_estimate": 4 * 1024**2,
                "info_dict": {"vcodec": "none", "acodec": "mp4a"},
            },
            Progress("Downloading audio: 25% of about 4.0 MB", 25.0),
        ),
        (
            {"downloaded_bytes": 0, "fragment_index": 3, "fragment_count": 12},
            Progress("Downloading: 25%", 25.0),
        ),
        (
            {"downloaded_bytes": 5 * 1024**2, "info_dict": {}},
            Progress("Downloading: 5.0 MB so far", None),
        ),
        (
            {"downloaded_bytes": 30, "total_bytes_estimate": 20},
            Progress("Downloading: 100% of about 0.0 MB", 100.0),
        ),
    ],
)
def test_progress_text(status: dict[str, Any], expected: Progress) -> None:
    assert progress({"status": "downloading", **status}) == expected


def test_size_text() -> None:
    assert size_text(3.44 * 1024**2) == "3.4 MB"
    assert size_text(23.4 * 1024**2) == "23 MB"
    assert size_text(1.25 * 1024**3) == "1.2 GB"


# --- With real yt-dlp and ffmpeg, against a web server on this PC (no internet).


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def clip_link(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """A link to a 1-second MP4 (H.264 and AAC) made by ffmpeg."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("needs ffmpeg")
    site = tmp_path_factory.mktemp("site")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
         "testsrc=duration=1:size=160x120:rate=10", "-f", "lavfi", "-i",
         "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", "-shortest",
         str(site / "clip.mp4")],
        check=True,
    )  # fmt: skip
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(site))
    )
    # A short poll interval makes shutdown() quick (the default waits 0.5 s).
    threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/clip.mp4"
    finally:
        server.shutdown()
        server.server_close()


def run(link: str, kind: Kind, folder: Path) -> list[Event]:
    events: list[Event] = []
    download(link, kind, folder, events.append)
    return events


@pytest.mark.parametrize("kind", list(Kind))
def test_download_then_already_there(
    clip_link: str, kind: Kind, tmp_path: Path
) -> None:
    folder = tmp_path / "Videos"  # not there yet: download() makes it
    events = run(clip_link, kind, folder)
    assert any(isinstance(event, Progress) for event in events)
    if kind == Kind.MP3:
        assert Progress("Converting to MP3...", None) in events
    assert events[-1] == Done(folder / f"clip.{kind}", already_there=False)
    assert sorted(path.name for path in folder.iterdir()) == [f"clip.{kind}"]

    # The second time nothing is downloaded. (MP3 still shows "Converting to
    # MP3..." for a moment: yt-dlp checks the existing file.)
    again = run(clip_link, kind, folder)
    bars = [e for e in again if isinstance(e, Progress) and e.percent is not None]
    assert bars == []
    assert again[-1] == Done(folder / f"clip.{kind}", already_there=True)


def test_broken_link_fails(clip_link: str, tmp_path: Path) -> None:
    missing = clip_link.replace("clip.mp4", "missing.mp4")
    events = run(missing, Kind.MP4, tmp_path)
    assert len(events) == 1
    assert isinstance(events[0], Failed)
    assert "404" in events[0].message
    assert not events[0].message.startswith("ERROR")
