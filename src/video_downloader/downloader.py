"""Download one video with yt-dlp, as MP4 or MP3.

The window runs download() in a background thread. It hears what happens
only through `report`: Progress events while it runs, then exactly one Done
or Failed.
"""

import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yt_dlp
from yt_dlp.utils import DownloadError

if TYPE_CHECKING:
    # yt-dlp's settings as pyright knows them (its bundled yt-dlp stubs).
    from yt_dlp import _Params


class Kind(StrEnum):
    """What to save: the video with its sound, or the sound only."""

    MP4 = "mp4"
    MP3 = "mp3"


# yt-dlp's own `-t mp4` and `-t mp3` presets (yt-dlp 2026.10.26) as library
# options: H.264 video with AAC sound, which plays everywhere, and MP3 made by
# ffmpeg from the best audio (docs/decisions.md). Their FFmpegConcat step, for
# playlists only, is left out. tests/test_downloader.py checks that these
# still match yt-dlp's presets after an update.
PRESETS: dict[Kind, "_Params"] = {
    Kind.MP4: {
        "format_sort": [
            "vcodec:h264",
            "lang",
            "quality",
            "res",
            "fps",
            "hdr:12",
            "acodec:aac",
        ],
        "merge_output_format": "mp4",
        "final_ext": "mp4",
        "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
    },
    Kind.MP3: {
        "format": "ba[acodec^=mp3]/ba/b",
        "final_ext": "mp3",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "5",
                "nopostoverwrites": False,
            }
        ],
    },
}

# The video's title, cut to 150 bytes so the path stays well under Windows'
# 260-character limit (X posts use the whole post as the title).
FILE_NAME = "%(title).150B.%(ext)s"

# yt-dlp's steps after the download, as the window names them.
STEP_TEXTS = {
    "Merger": "Joining video and audio...",
    "ExtractAudio": "Converting to MP3...",
}


@dataclass(frozen=True)
class Progress:
    text: str
    percent: float | None  # None: busy, but how far along isn't known


@dataclass(frozen=True)
class Done:
    path: Path
    already_there: bool  # the file was already there, so nothing was downloaded


@dataclass(frozen=True)
class Failed:
    message: str


type Event = Progress | Done | Failed
type Report = Callable[[Event], None]


def default_folder() -> Path:
    """Videos inside the user's Downloads folder."""
    return Path.home() / "Downloads" / "Videos"


def options(kind: Kind, folder: Path) -> "_Params":
    """yt-dlp's settings for one download into `folder`, without the hooks."""
    settings = copy.deepcopy(PRESETS[kind])
    settings.update(
        {
            "paths": {"home": str(folder)},
            "outtmpl": FILE_NAME,
            # A link to a video in a playlist gets just that video; a link to a
            # whole playlist or channel gets its first video only.
            "noplaylist": True,
            "playlist_items": "1",
            # The window shows the progress. Warnings and errors still go to the
            # terminal, without color codes, which would end up in error messages.
            "quiet": True,
            "noprogress": True,
            "color": {"stdout": "never", "stderr": "never"},
        }
    )
    return settings


def download(link: str, kind: Kind, folder: Path, report: Report) -> None:
    """Download the video at `link` into `folder` (made if missing)."""
    saved: list[Path] = []

    def on_progress(status: Mapping[str, Any]) -> None:
        if status["status"] == "downloading":
            report(progress(status))

    def on_step(status: Mapping[str, Any]) -> None:
        text = STEP_TEXTS.get(status["postprocessor"])
        if status["status"] == "started" and text:
            report(Progress(text, None))

    settings = options(kind, folder)
    settings["progress_hooks"] = [on_progress]
    settings["postprocessor_hooks"] = [on_step]
    settings["post_hooks"] = [lambda path: saved.append(Path(path))]
    try:
        folder.mkdir(parents=True, exist_ok=True)
        # yt-dlp doesn't say whether it skipped a file that was already there,
        # and its progress reports can't tell either: downloads it hands to
        # ffmpeg report only "finished" (docs/research/yt-dlp-library.md).
        there_before = {path.name for path in folder.iterdir()}
        with yt_dlp.YoutubeDL(settings) as ydl:
            ydl.download([link])
    except DownloadError as error:
        report(Failed(str(error).removeprefix("ERROR: ")))
    except Exception as error:  # the window must always hear that it ended
        report(Failed(f"Something went wrong: {error}"))
    else:
        if saved:
            report(Done(saved[-1], already_there=saved[-1].name in there_before))
        else:
            report(Failed("Nothing was downloaded from this link."))


def progress(status: Mapping[str, Any]) -> Progress:
    """yt-dlp's progress report as the window shows it, for example
    "Downloading video: 45% of 23 MB"."""
    info = status.get("info_dict") or {}
    if info.get("vcodec") == "none":
        what = "Downloading audio"
    elif info.get("acodec") == "none":
        what = "Downloading video"
    else:
        what = "Downloading"
    done = status.get("downloaded_bytes") or 0
    total = status.get("total_bytes")
    size = total or status.get("total_bytes_estimate")
    if size:
        percent = min(100.0, 100 * done / size)
        about = "" if total else "about "
        return Progress(f"{what}: {percent:.0f}% of {about}{size_text(size)}", percent)
    index, count = status.get("fragment_index"), status.get("fragment_count")
    if index is not None and count:
        percent = min(100.0, 100 * index / count)
        return Progress(f"{what}: {percent:.0f}%", percent)
    return Progress(f"{what}: {size_text(done)} so far", None)


def size_text(size: float) -> str:
    """A size in bytes the way Windows shows it: 3.4 MB, 23 MB, 1.2 GB."""
    megabytes = size / 1024**2
    if megabytes >= 1024:
        return f"{megabytes / 1024:.1f} GB"
    if megabytes >= 10:
        return f"{megabytes:.0f} MB"
    return f"{megabytes:.1f} MB"
