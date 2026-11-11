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
    BOT_CHECK,
    COUNTRY,
    FFMPEG_MISSING,
    NO_CONNECTION,
    NO_VIDEO,
    NOT_A_LINK,
    NOT_AVAILABLE,
    PRESETS,
    PRIVATE,
    RATE_LIMITED,
    REDDIT,
    SIGN_IN,
    Done,
    Event,
    Failed,
    Kind,
    Progress,
    download,
    options,
    plain_message,
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


# yt-dlp's error texts, measured 2026-11-11 unless marked "from the source"
# (docs/research/yt-dlp-library.md "Errors"). The long ones are cut short.
COOKIES_HINT = (
    "Use --cookies-from-browser or --cookies for the authentication. See  "
    "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  "
    "for how to manually pass cookies"
)
ERROR_TEXTS = {
    "not a link": ("[generic] 'hello' is not a valid URL", NOT_A_LINK),
    "no video": ("Unsupported URL: https://example.com/", NO_VIDEO),
    "404": (
        "[generic] missing: Unable to download webpage: HTTP Error 404: File not "
        "found (caused by <HTTPError 404: File not found>)",
        NOT_AVAILABLE,
    ),
    "unknown host": (
        "[generic] watch?v=1: Unable to download webpage: HTTPSConnection("
        "host='nonexistent.invalid', port=443): Failed to resolve "
        "'nonexistent.invalid' ([Errno 11001] getaddrinfo failed) (caused by "
        'TransportError("..."))',
        NO_CONNECTION,
    ),
    "nothing listening": (
        "[generic] video: Unable to download webpage: HTTPConnection("
        "host='127.0.0.1', port=9): Failed to establish a new connection: "
        "[WinError 10061] No connection could be made because the target "
        'machine actively refused it (caused by TransportError("..."))',
        NO_CONNECTION,
    ),
    "connection lost while downloading (from the source)": (
        "unable to download video data: HTTPSConnection(host='rr1.example', "
        "port=443): Read timed out.",
        NO_CONNECTION,
    ),
    "private": (
        "[youtube] yZIXLfi8CZQ: Private video. If the owner of this video has "
        f"granted you access, please sign in. {COOKIES_HINT}",
        PRIVATE,
    ),
    "removed": (
        "[youtube] 6SJNVb0GnPI: This video has been removed for violating "
        "YouTube's policy on hate speech. Learn more about combating hate "
        "speech in your country.",
        NOT_AVAILABLE,
    ),
    "unavailable": ("[youtube] zzzzzzzzzzz: This video is unavailable", NOT_AVAILABLE),
    "reddit": (
        f"[Reddit] 1xsyq9n: Account authentication is required. {COOKIES_HINT}",
        REDDIT,
    ),
    "ffmpeg missing": (
        "Postprocessing: ffprobe and ffmpeg not found. Please install or "
        "provide the path using --ffmpeg-location",
        FFMPEG_MISSING,
    ),
    "age (from the source)": (
        "[youtube] abc: Sign in to confirm your age. This video may be "
        f"inappropriate for some users. {COOKIES_HINT}",
        SIGN_IN,
    ),
    "members only (YouTube's text, from memory)": (
        "[youtube] abc: Join this channel to get access to members-only content "
        "like this video, and other exclusive perks.",
        SIGN_IN,
    ),
    "account needed (from the source)": (
        "[vimeo] 123: This video is only available for registered users. Use "
        "--cookies, --cookies-from-browser, --username and --password",
        SIGN_IN,
    ),
    "bot check (from the source)": (
        f"[youtube] abc: Sign in to confirm you’re not a bot. {COOKIES_HINT}",
        BOT_CHECK,
    ),
    "rate-limited (from the source)": (
        "[youtube] abc: Video unavailable. This content isn't available, try "
        "again later. The current session has been rate-limited by YouTube for "
        "up to an hour.",
        RATE_LIMITED,
    ),
    "country (from the source)": (
        "[youtube] abc: The uploader has not made this video available in your "
        "country\nThis video is available in Germany.\nYou might want to use a "
        "VPN or a proxy server (with --proxy) to workaround.",
        COUNTRY,
    ),
}


@pytest.mark.parametrize(
    ("text", "expected"), list(ERROR_TEXTS.values()), ids=list(ERROR_TEXTS)
)
def test_plain_message(text: str, expected: str) -> None:
    assert plain_message(f"ERROR: {text}") == expected


@pytest.mark.parametrize(
    "text",
    [
        "[youtube] abc: Requested format is not available. Use --list-formats",
        # A server's passing trouble, not a removed video.
        "[generic] abc: Unable to download webpage: HTTP Error 503: Service "
        "Unavailable (caused by <HTTPError 503: Service Unavailable>)",
        # "login" inside a word or a link isn't about signing in.
        "[generic] abc: Unable to parse the catalog index at https://x.example/blogin",
    ],
)
def test_unknown_error_keeps_yt_dlps_text(text: str) -> None:
    assert plain_message(f"ERROR: {text}") == text


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
    # A page with two videos, which yt-dlp treats as a playlist.
    (site / "two.html").write_text(
        "<html><head><title>Two clips</title></head><body>"
        '<video src="clip.mp4"></video><video src="clip2.mp4"></video>'
        "</body></html>"
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
         "testsrc=duration=1:size=160x120:rate=10", "-f", "lavfi", "-i",
         "sine=duration=1", "-c:v", "libx264", "-c:a", "aac", "-shortest",
         str(site / "clip.mp4")],
        check=True,
    )  # fmt: skip
    shutil.copy(site / "clip.mp4", site / "clip2.mp4")
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


def test_broken_link_gives_a_plain_message(clip_link: str, tmp_path: Path) -> None:
    missing = clip_link.replace("clip.mp4", "missing.mp4")
    assert run(missing, Kind.MP4, tmp_path) == [Failed(NOT_AVAILABLE)]
    assert run("hello", Kind.MP4, tmp_path) == [Failed(NOT_A_LINK)]


def test_playlist_downloads_its_first_video_and_says_so(
    clip_link: str, tmp_path: Path
) -> None:
    events = run(clip_link.replace("clip.mp4", "two.html"), Kind.MP4, tmp_path)
    assert isinstance(events[-1], Done)
    assert events[-1].playlist
    assert [path.name for path in tmp_path.iterdir()] == [events[-1].path.name]


def test_missing_ffmpeg_fails_before_downloading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert run("https://example.com/video", Kind.MP4, tmp_path) == [
        Failed(FFMPEG_MISSING)
    ]
