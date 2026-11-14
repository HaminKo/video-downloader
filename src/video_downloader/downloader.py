"""Download one video with yt-dlp, as MP4 (in a chosen quality, optionally
with English subtitles) or MP3; a download can be cancelled. It deletes only
files it saved itself, and only inside its folder (deletable()).

The window runs download() in a background thread. It hears what happens
only through `report`: Progress events while it runs, then exactly one Done,
Failed or Cancelled.
"""

import contextlib
import copy
import gc
import io
import os
import re
import shutil
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yt_dlp
from yt_dlp.cookies import CookieLoadError
from yt_dlp.utils import DownloadCancelled

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
# 260-character limit (X posts use the whole post as the title). A video in
# a lower quality gets it after the title, so it is a file of its own and
# not "already there" next to the same video at Best.
FILE_NAME = "%(title).150B.%(ext)s"
FILE_NAME_WITH_QUALITY = "%(title).150B ({height}p).%(ext)s"

# The app's own folder for what it keeps between sessions: the sign-in file
# and the history of downloads.
DATA_FOLDER = (
    Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    / "video-downloader"
)

# Sign-ins the user exported from their browser as a cookies.txt (Reddit's
# only), used whenever the file is there. yt-dlp can't read Edge's or Chrome's
# own cookies on Windows (docs/research/signing-in.md, docs/signing-in.md).
COOKIES = DATA_FOLDER / "cookies.txt"

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
    "or for members only). The app only signs in to Reddit for now."
)
# Reddit refuses a post's data to anyone not signed in, a real browser included
# (docs/research/yt-dlp-library.md "Sites"). REDDIT_REFUSED: the same error
# while the app used the sign-in file.
REDDIT = (
    "Reddit only allows downloads when you're signed in. To sign in, see "
    '"Signing in" in the README.'
)
REDDIT_REFUSED = (
    "Reddit didn't accept your sign-in: it may have run out, or the file isn't "
    "Reddit's. Export Reddit's cookies again (README, \"Signing in\")."
)
COOKIES_BROKEN = (
    "The sign-in file can't be read. Export Reddit's cookies again (format: "
    'Netscape), or delete the file (README, "Signing in").'
)
BOT_CHECK = "YouTube wants to check you're not a bot. Try again later."
RATE_LIMITED = "YouTube is limiting downloads for now. Try again in about an hour."
COUNTRY = "This video isn't available in your country."
FFMPEG_MISSING = (
    "ffmpeg is missing; it's needed for MP4 and MP3. Install it with "
    "winget install --id yt-dlp.FFmpeg -e, then restart VS Code (or the "
    "terminal) and the app."
)
# yt-dlp fetches the subtitles before the video and stops when it can't.
SUBTITLES_FAILED = (
    "Couldn't download the subtitles, so nothing was saved. Try again later, "
    "or untick English subtitles."
)

# Patterns in yt-dlp's error texts, and what the window says instead. The
# first match wins, so the order matters: a private video's text also says
# "sign in", and every sign-in text ends in yt-dlp's "--cookies" hint. The
# texts, measured and read in the source: docs/research/yt-dlp-library.md
# "Errors". Anything else shows yt-dlp's own text.
PLAIN_MESSAGES = [
    # A broken sign-in file fails every download, whatever the link.
    (r"Netscape format", COOKIES_BROKEN),
    (r"is not a valid URL", NOT_A_LINK),
    (r"Unsupported URL:", NO_VIDEO),
    (r"(ffmpeg|ffprobe) not found|ffmpeg is not installed", FFMPEG_MISSING),
    # Before the patterns below: its text ends in the cause (an HTTP 404
    # would say the video isn't available).
    (r"Unable to download video subtitles", SUBTITLES_FAILED),
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
    (r"\bsign in\b|\blog ?in\b|--cookies|members-only|registered users", SIGN_IN),
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
    title: str = ""  # the video's title, once yt-dlp has looked it up


@dataclass(frozen=True)
class Done:
    path: Path
    already_there: bool  # the file was already there, so nothing was downloaded
    playlist: bool = False  # a playlist link: only its first video was saved
    no_subtitles: bool = False  # subtitles were asked for, but none in English


@dataclass(frozen=True)
class Failed:
    message: str


@dataclass(frozen=True)
class Cancelled:
    """Stopped on request; what the download had saved is deleted."""


type Event = Progress | Done | Failed | Cancelled
type Report = Callable[[Event], None]


class Log:
    """yt-dlp's `logger`: keeps its errors, and prints its warnings and
    errors to the terminal as yt-dlp does without one. With `ignoreerrors`
    (options()) the errors are how download() learns why a video failed
    (docs/research/yt-dlp-library.md "Playlists and channels")."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    @property
    def first(self) -> str:
        """The first error, which without `ignoreerrors` yt-dlp would have
        raised as a DownloadError with this same text; "" with none."""
        return self.errors[0] if self.errors else ""

    def debug(self, message: str) -> None:
        """What yt-dlp prints while it works: left out, as with `quiet`."""

    def warning(self, message: str) -> None:
        print(f"WARNING: {message}", file=sys.stderr)

    def error(self, message: str) -> None:
        # Everything yt-dlp prints to stderr comes here, but only its errors
        # start with "ERROR:" (others: a bare "\r", "Deprecated Feature: ...").
        # Plain text only while options() turns colors off.
        print(message, file=sys.stderr)
        if message.startswith("ERROR:"):
            self.errors.append(message)


def default_folder() -> Path:
    """Videos inside the user's Downloads folder."""
    return Path.home() / "Downloads" / "Videos"


def options(
    kind: Kind, folder: Path, height: int | None = None, subtitles: bool = False
) -> "_Params":
    """yt-dlp's settings for one download into `folder`, without the hooks.

    height: for MP4, the largest to take (720 for 720p), counted on the
    video's shorter side, so a portrait video's width; with none at or under
    it, the smallest above. None: the best that plays everywhere.
    subtitles: for MP4, also save English subtitles as `Title.en.srt`.
    """
    settings = copy.deepcopy(PRESETS[kind])
    file_name = FILE_NAME
    if height and kind == Kind.MP4:
        # Right after H.264, which stays first, and before "quality", which
        # YouTube fills from its own labels: after it, the limit would do
        # nothing (docs/research/yt-dlp-library.md "Quality").
        sort = list(settings.get("format_sort") or [])
        sort.insert(sort.index("vcodec:h264") + 1, f"res:{height}")
        settings["format_sort"] = sort
        file_name = FILE_NAME_WITH_QUALITY.format(height=height)
    if subtitles and kind == Kind.MP4:
        # A file of their own next to the video: Windows' own player doesn't
        # read subtitles inside an MP4. Real ones when the video has them,
        # the site's automatic ones otherwise (docs/research/subtitles.md).
        settings.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en"],
                # YouTube's own srt: its vtt shows each line of automatic
                # captions twice. Other sites' vtt is converted by ffmpeg.
                "subtitlesformat": "srt/best",
            }
        )
        settings["postprocessors"] = [
            {"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"},
            *(settings.get("postprocessors") or []),
        ]
    if kind == Kind.MP3:
        # yt-dlp deletes the file it converted to MP3, also an MP4 of the
        # same video that was already in the folder: on a site with no
        # separate audio it takes that MP4 as the download. With this it
        # deletes nothing; download() deletes the source only when it is new
        # (docs/research/yt-dlp-library.md "Files yt-dlp deletes"). That
        # replaces yt-dlp's deleting for ExtractAudio only, the one step of
        # the MP3 preset that deletes: recheck if the preset gets another.
        # A bool in yt-dlp (its --keep-video is a switch); the type stub
        # says str.
        settings["keepvideo"] = True  # pyright: ignore[reportGeneralTypeIssues]
    settings.update(
        {
            "paths": {"home": str(folder)},
            "outtmpl": file_name,
            # A link to a video in a playlist gets just that video; a link to a
            # whole playlist or channel gets its first video only.
            "noplaylist": True,
            "playlist_items": "1",
            # The command line's default: a video that fails doesn't end the
            # download, so a playlist's other videos still come. Errors then
            # reach the app only through download()'s Log.
            "ignoreerrors": "only_download",
            # The window shows the progress. Warnings and errors still go to the
            # terminal, without color codes, which would end up in error messages.
            "quiet": True,
            "noprogress": True,
            "color": {"stdout": "never", "stderr": "never"},
        }
    )
    if COOKIES.is_file():
        # yt-dlp sends each cookie only to its own site. It writes every
        # cookie back after the download, YouTube's too; given a copy in
        # memory (a text stream, which yt-dlp also takes, though its type
        # stub says str only), the file stays as exported (docs/decisions.md).
        cookies = io.StringIO(COOKIES.read_text(encoding="utf-8"))
        settings["cookiefile"] = cookies  # pyright: ignore[reportGeneralTypeIssues]
    return settings


def download(
    link: str,
    kind: Kind,
    folder: Path,
    report: Report,
    height: int | None = None,
    subtitles: bool = False,
    cancel: threading.Event | None = None,
) -> None:
    """Download the video at `link` into `folder` (made if missing); `height`
    and `subtitles` as in options(). Setting `cancel` stops the download at
    yt-dlp's next report: within a second while downloading, after the step
    while ffmpeg joins or converts."""
    # The form of the paths yt-dlp reports (it normalizes them with
    # os.path.normpath), so that they compare equal to the folder's own.
    folder = Path(os.path.abspath(folder))
    saved: list[Path] = []
    # The files this download saves are these paths plus the rest of their
    # names (note_names()); a cancelled download deletes them.
    prefixes: set[Path] = set()
    # What was in the folder before the download (paths_in()). Taken before
    # yt-dlp starts, so before any hook can add a prefix.
    there_before: set[Path] = set()
    # The files an MP3 was converted from (remove_mp3_sources()).
    mp3_sources: set[Path] = set()
    log = Log()

    def stop_if_cancelled(status: Mapping[str, Any]) -> None:
        # yt-dlp has no stop call: this error from a hook is its own way
        # (docs/research/yt-dlp-library.md "Cancelling").
        note_names(status, prefixes)
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled

    def on_progress(status: Mapping[str, Any]) -> None:
        stop_if_cancelled(status)
        # Not the subtitles' own download, a few KB before the video's: the
        # bar would fill and start again. yt-dlp gives every video and audio
        # format a format_id, subtitles none (docs/research/subtitles.md).
        info = status.get("info_dict") or {}
        if status["status"] == "downloading" and "format_id" in info:
            report(progress(status))

    def on_step(status: Mapping[str, Any]) -> None:
        stop_if_cancelled(status)  # at "started", before ffmpeg runs, too
        if status["postprocessor"] == "ExtractAudio" and status["status"] == "started":
            # The file it converts from; the MP3 itself when that was already
            # there (docs/research/yt-dlp-library.md "Files yt-dlp deletes").
            mp3_sources.add(Path(status["info_dict"]["filepath"]))
        text = STEP_TEXTS.get(status["postprocessor"])
        if status["status"] == "started" and text:
            report(Progress(text, None, status["info_dict"].get("title") or ""))

    # Without ffmpeg, yt-dlp doesn't fail on an MP4: it quietly picks a worse
    # file that needs no joining (docs/research/yt-dlp-library.md "Errors").
    if shutil.which("ffmpeg") is None:
        report(Failed(FFMPEG_MISSING))
        return
    signed_in = False
    cancelled = False
    try:
        settings = options(kind, folder, height, subtitles)  # reads the sign-in file
        signed_in = "cookiefile" in settings
        settings["progress_hooks"] = [on_progress]
        settings["postprocessor_hooks"] = [on_step]
        settings["post_hooks"] = [lambda path: saved.append(Path(path))]
        # yt-dlp calls only debug, warning and error (read in the source);
        # its type stub asks for more.
        settings["logger"] = log  # pyright: ignore[reportGeneralTypeIssues]
        folder.mkdir(parents=True, exist_ok=True)
        # yt-dlp doesn't say whether it skipped a file that was already there,
        # and its progress reports can't tell either: downloads it hands to
        # ffmpeg report only "finished" (docs/research/yt-dlp-library.md).
        there_before = paths_in(folder)
        with yt_dlp.YoutubeDL(settings) as ydl:
            # Not ydl.download(), which doesn't say whether it was a playlist.
            # None when the link itself failed (`ignoreerrors`).
            info = ydl.extract_info(link)
    except DownloadCancelled:
        # Cleaned up below: until this block has ended, the error holds on to
        # files yt-dlp still has open.
        cancelled = True
    except CookieLoadError as error:
        # With `ignoreerrors`, the one failure that still raises: a broken
        # sign-in file, whose reason yt-dlp logs first. The others, also an
        # OSError while saving (such as a full disk), are only logged.
        report(Failed(plain_message(log.first or str(error), signed_in)))
    except Exception as error:  # the window must always hear that it ended
        report(Failed(f"Something went wrong: {error}"))
    else:
        if saved:
            video = saved[-1]
            remove_mp3_sources(mp3_sources, video, there_before, folder)
            report(
                Done(
                    video,
                    already_there=video in there_before,
                    playlist=info is not None
                    and info.get("_type") == "playlist"
                    and info.get("playlist_count") != 1,
                    # yt-dlp's name for them. It doesn't say when there are
                    # none in English (only on screen, which `quiet` hides).
                    no_subtitles=subtitles
                    and kind == Kind.MP4
                    and not video.with_suffix(".en.srt").is_file(),
                )
            )
        elif log.first:
            report(Failed(plain_message(log.first, signed_in)))
        else:
            report(Failed("Nothing was downloaded from this link."))
    if cancelled:
        try:
            remove_unfinished(folder, prefixes, there_before)
        finally:  # the window must always hear that it ended
            report(Cancelled())


def note_names(status: Mapping[str, Any], prefixes: set[Path]) -> None:
    """Add to `prefixes` how the paths of the files a hook's `status` is
    about start: their folder, and how their names start. Every file of a
    video starts with its file name without the extension, then a dot:
    Title.f137.mp4.part, Title.temp.mp4, Title.en.srt. A subtitle download's
    status doesn't have that name, but its own: Title.en.vtt
    (docs/research/yt-dlp-library.md "Cancelling")."""
    info = status.get("info_dict") or {}
    if name := info.get("_filename"):
        path = Path(name)
        prefixes.add(path.with_name(f"{path.stem}."))
    for key in ("filename", "tmpfilename"):
        if name := status.get(key):
            prefixes.add(Path(name))


def paths_in(folder: Path) -> set[Path]:
    """What is in `folder` and in the folders directly inside it: the places
    a download saves to (a playlist's videos will get a folder of their own)
    and the only ones it deletes from (deletable())."""
    found: set[Path] = set()
    with os.scandir(folder) as entries:  # its is_dir() needs no extra call
        for entry in entries:
            found.add(Path(entry.path))
            if not entry.is_dir():
                continue
            # One that can't be listed is left out rather than failing the
            # download: yt-dlp can't save there either.
            with contextlib.suppress(OSError):
                found.update(Path(entry.path).iterdir())
    return found


def remove_unfinished(
    folder: Path, prefixes: set[Path], there_before: set[Path]
) -> None:
    """Delete the files a cancelled download into `folder` left: those whose
    paths start with one of `prefixes` (in the prefix's folder, the name
    starting the same), unless they were there before it started (a .part
    left by closing the window, too). A file that lands in the folder
    meanwhile stays, unless its name starts the same way."""
    # yt-dlp's HLS downloader leaves its .part file open after the error, and
    # Windows can't delete an open file. A reference cycle holds it; this
    # closes it (measured, docs/research/yt-dlp-library.md "Cancelling").
    gc.collect()
    for directory in {prefix.parent for prefix in prefixes}:
        if not directory.is_dir():
            continue
        starts = tuple(p.name for p in prefixes if p.parent == directory)
        for path in directory.iterdir():
            if path in there_before or not path.name.startswith(starts):
                continue
            if path.is_file():
                delete(path, folder)


def remove_mp3_sources(
    sources: set[Path], mp3: Path, there_before: set[Path], folder: Path
) -> None:
    """Delete the files the finished `mp3` was converted from, as yt-dlp would
    have (`keepvideo` in options()), but only those new since the download
    into `folder` started: an MP4 of the same video that was there before
    stays."""
    for path in sources:
        if path != mp3 and path not in there_before:
            delete(path, folder)


def deletable(path: Path, folder: Path) -> bool:
    """Whether `path` is in `folder` or in a folder directly inside it, with
    `..` and links resolved: yt-dlp would put the videos of a playlist named
    ".." into the folder above (docs/research/yt-dlp-library.md "Playlists
    and channels")."""
    try:
        inside = path.resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return len(inside.parts) in (1, 2)


def delete(path: Path, folder: Path) -> None:
    """Delete a file the download into `folder` saved, but only in the places
    deletable() allows. If it can't, the download still counts as done or
    cancelled; the reason goes to the terminal."""
    if not deletable(path, folder):
        print(f"Not deleted, as it's outside {folder}: {path}", file=sys.stderr)
        return
    try:
        path.unlink()
    except OSError as error:
        print(f"Couldn't delete {path}: {error}", file=sys.stderr)


def plain_message(error: str, signed_in: bool = False) -> str:
    """What the window says for yt-dlp's error text: a plain message for the
    failures met most often, otherwise yt-dlp's own text. `signed_in`: the
    sign-in file was used."""
    text = error.removeprefix("ERROR: ")
    for pattern, message in PLAIN_MESSAGES:
        if re.search(pattern, text, re.IGNORECASE):
            return REDDIT_REFUSED if message == REDDIT and signed_in else message
    return text


def progress(status: Mapping[str, Any]) -> Progress:
    """yt-dlp's progress report as the window shows it, for example
    "Downloading video: 45% of 23 MB", with the video's title."""
    info = status.get("info_dict") or {}
    title = info.get("title") or ""
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
        text = f"{what}: {percent:.0f}% of {about}{size_text(size)}"
        return Progress(text, percent, title)
    index, count = status.get("fragment_index"), status.get("fragment_count")
    if index is not None and count:
        percent = min(100.0, 100 * index / count)
        return Progress(f"{what}: {percent:.0f}%", percent, title)
    return Progress(f"{what}: {size_text(done)} so far", None, title)


def size_text(size: float) -> str:
    """A size in bytes the way Windows shows it: 3.4 MB, 23 MB, 1.2 GB."""
    megabytes = size / 1024**2
    if megabytes >= 1024:
        return f"{megabytes / 1024:.1f} GB"
    if megabytes >= 10:
        return f"{megabytes:.0f} MB"
    return f"{megabytes:.1f} MB"
