"""Download one video with yt-dlp, as MP4 or MP3.

The window runs download() in a background thread. It hears what happens
only through `report`: Progress events while it runs, then exactly one Done
or Failed.
"""

import copy
import re
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yt_dlp
from yt_dlp.utils import DownloadError, UnavailableVideoError

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

# What the window says when a download fails.
NOT_A_LINK = (
    "That isn't a link. Copy the video's address from your browser and paste it here."
)
NO_VIDEO = (
    "No video found at this link. The site may not be supported, "
    "or the page has no video."
)
NO_CONNECTION = "Couldn't reach the site. Check your internet connection and the link."
PRIVATE = "This video is private, so it can't be downloaded."
NOT_AVAILABLE = (
    "This video isn't available. It may have been removed, or the link may be wrong."
)
SIGN_IN = (
    "This video needs you to be signed in (for example, it's age-restricted "
    "or for members only). The app can't sign in yet."
)
REDDIT = "Reddit blocks downloads from this app for now."
BOT_CHECK = "YouTube wants to check you're not a bot. Try again later."
RATE_LIMITED = "YouTube is limiting downloads for now. Try again in about an hour."
COUNTRY = "This video isn't available in your country."
FFMPEG_MISSING = (
    "ffmpeg is missing; it's needed for MP4 and MP3. Install it with "
    "winget install --id yt-dlp.FFmpeg -e, then restart VS Code (or the "
    "terminal) and the app."
)

# Patterns in yt-dlp's error texts, and what the window says instead. The
# first match wins, so the order matters: a private video's text also says
# "sign in", and every sign-in text ends in yt-dlp's "--cookies" hint. The
# texts, measured and read in the source: docs/research/yt-dlp-library.md
# "Errors". Anything else shows yt-dlp's own text.
PLAIN_MESSAGES = [
    (r"is not a valid URL", NOT_A_LINK),
    (r"Unsupported URL:", NO_VIDEO),
    (r"(ffmpeg|ffprobe) not found|ffmpeg is not installed", FFMPEG_MISSING),
    (
        r"TransportError|getaddrinfo failed|Failed to resolve"
        r"|Failed to establish a new connection|timed out",
        NO_CONNECTION,
    ),
    (r"\[Reddit\].*Account authentication is required", REDDIT),
    (r"Private video|This video is private", PRIVATE),
    (r"not a bot", BOT_CHECK),
    (r"rate-limited", RATE_LIMITED),
    (r"not available from your location|available in your country", COUNTRY),
    (r"sign in|log ?in|--cookies|members-only|registered users", SIGN_IN),
    (
        r"video is unavailable|video unavailable|has been removed"
        r"|no longer available|does not exist|HTTP Error (404|410)",
        NOT_AVAILABLE,
    ),
]


@dataclass(frozen=True)
class Progress:
    text: str
    percent: float | None  # None: busy, but how far along isn't known


@dataclass(frozen=True)
class Done:
    path: Path
    already_there: bool  # the file was already there, so nothing was downloaded
    playlist: bool = False  # a playlist link: only its first video was saved


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

    # Without ffmpeg, yt-dlp doesn't fail on an MP4: it quietly picks a worse
    # file that needs no joining (docs/research/yt-dlp-library.md "Errors").
    if shutil.which("ffmpeg") is None:
        report(Failed(FFMPEG_MISSING))
        return
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
            # Not ydl.download(), which doesn't say whether it was a playlist.
            # It did turn UnavailableVideoError (an OSError while saving, such
            # as a full disk) into a DownloadError; the next line does that now.
            info = ydl.extract_info(link)
    except (DownloadError, UnavailableVideoError) as error:
        report(Failed(plain_message(str(error))))
    except Exception as error:  # the window must always hear that it ended
        report(Failed(f"Something went wrong: {error}"))
    else:
        if saved:
            report(
                Done(
                    saved[-1],
                    already_there=saved[-1].name in there_before,
                    playlist=info.get("_type") == "playlist"
                    and info.get("playlist_count") != 1,
                )
            )
        else:
            report(Failed("Nothing was downloaded from this link."))


def plain_message(error: str) -> str:
    """What the window says for yt-dlp's error text: a plain message for the
    failures met most often, otherwise yt-dlp's own text."""
    text = error.removeprefix("ERROR: ")
    for pattern, message in PLAIN_MESSAGES:
        if re.search(pattern, text, re.IGNORECASE):
            return message
    return text


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
