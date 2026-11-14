import shutil
import subprocess
import threading
from collections.abc import Callable, Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yt_dlp

from video_downloader import downloader
from video_downloader.downloader import (
    BOT_CHECK,
    COOKIES_BROKEN,
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
    REDDIT_REFUSED,
    SIGN_IN,
    SUBTITLES_FAILED,
    Cancelled,
    Done,
    Event,
    Failed,
    Kind,
    Log,
    Playlist,
    Progress,
    download,
    options,
    paths_in,
    plain_message,
    progress,
    remove_mp3_sources,
    remove_unfinished,
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


def test_options_save_by_title_a_playlist_in_a_folder(tmp_path: Path) -> None:
    settings = options(Kind.MP4, tmp_path)
    assert settings.get("paths") == {"home": str(tmp_path)}
    assert settings.get("outtmpl") == "%(playlist_title|.).80B/%(title).150B.%(ext)s"
    # A video in a playlist is just that video; a playlist is all of it.
    assert settings.get("noplaylist") is True
    assert "playlist_items" not in settings
    assert settings.get("merge_output_format") == "mp4"
    assert options(Kind.MP3, tmp_path).get("final_ext") == "mp3"


def test_options_use_the_sign_in_file_only_when_it_is_there(tmp_path: Path) -> None:
    # conftest.py points COOKIES into a temporary folder.
    assert "cookiefile" not in options(Kind.MP4, tmp_path)
    downloader.COOKIES.write_text("# Netscape HTTP Cookie File\n")
    cookies: Any = options(Kind.MP4, tmp_path).get("cookiefile")
    assert cookies.read() == "# Netscape HTTP Cookie File\n"


def test_options_are_a_copy() -> None:
    copied = options(Kind.MP3, Path()).get("postprocessors")
    assert copied == PRESETS[Kind.MP3].get("postprocessors")
    assert copied is not PRESETS[Kind.MP3].get("postprocessors")


def test_height_limit_comes_right_after_h264(tmp_path: Path) -> None:
    preset = list(PRESETS[Kind.MP4].get("format_sort") or [])
    assert preset[0] == "vcodec:h264"
    for height in (720, 480):
        sort = options(Kind.MP4, tmp_path, height).get("format_sort")
        assert sort == ["vcodec:h264", f"res:{height}", *preset[1:]]
    assert options(Kind.MP4, tmp_path).get("format_sort") == preset
    assert options(Kind.MP4, tmp_path, 720).get("outtmpl") == (
        "%(playlist_title|.).80B/%(title).150B (720p).%(ext)s"
    )
    assert PRESETS[Kind.MP4].get("format_sort") == preset, "the preset was changed"
    assert options(Kind.MP3, tmp_path, 720) == options(Kind.MP3, tmp_path)


def test_subtitle_settings_are_yt_dlps_own(tmp_path: Path) -> None:
    # The same settings as yt-dlp's command line options, so a misspelt
    # setting (which yt-dlp would quietly ignore) fails here.
    command = ["--ignore-config", "-t", "mp4"]
    plain = yt_dlp.parse_options(command).ydl_opts
    with_subtitles = yt_dlp.parse_options(
        [*command, "--write-subs", "--write-auto-subs", "--sub-langs", "en",
         "--sub-format", "srt/best", "--convert-subs", "srt"]
    ).ydl_opts  # fmt: skip
    changed: dict[str, Any] = {
        key: value for key, value in with_subtitles.items() if plain.get(key) != value
    }
    changed["postprocessors"] = [
        step for step in changed["postprocessors"] if step["key"] != "FFmpegConcat"
    ]
    settings: dict[str, Any] = dict(options(Kind.MP4, tmp_path, subtitles=True))
    assert {key: settings.get(key) for key in changed} == changed
    # Not inside the MP4: Windows' own player doesn't read them there.
    assert "FFmpegEmbedSubtitle" not in str(settings["postprocessors"])
    assert "writesubtitles" not in options(Kind.MP4, tmp_path)
    assert options(Kind.MP3, tmp_path, subtitles=True) == options(Kind.MP3, tmp_path)
    assert len(PRESETS[Kind.MP4].get("postprocessors") or []) == 1, "preset changed"


def youtube_like_video() -> Any:  # yt-dlp's _InfoDict, which lists few keys
    """A video as yt-dlp's YouTube extractor lists it: H.264 up to 1080p, VP9
    up to 2160p, sound apart, and `quality` from YouTube's own labels (480p 7,
    720p 8, 1080p 9, 2160p 11)."""
    videos = [
        ("135", "avc1.4d401f", 854, 480, 7),
        ("136", "avc1.4d401f", 1280, 720, 8),
        ("137", "avc1.640028", 1920, 1080, 9),
        ("244", "vp9", 854, 480, 7),
        ("247", "vp9", 1280, 720, 8),
        ("248", "vp9", 1920, 1080, 9),
        ("313", "vp9", 3840, 2160, 11),
    ]
    formats: list[dict[str, Any]] = [
        {
            "format_id": format_id,
            "url": f"https://example.com/{format_id}",
            "ext": "mp4" if vcodec.startswith("avc1") else "webm",
            "vcodec": vcodec,
            "acodec": "none",
            "width": width,
            "height": height,
            "quality": quality,
        }
        for format_id, vcodec, width, height, quality in videos
    ]
    formats.append(
        {
            "format_id": "140",
            "url": "https://example.com/140",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "quality": 3,
        }
    )
    return {"id": "test", "title": "Test", "formats": formats}


@pytest.mark.parametrize(
    ("height", "expected"),
    [(None, "137+140"), (720, "136+140"), (480, "135+140"), (360, "135+140")],
)
def test_height_limit_picks_that_height_in_h264(
    height: int | None, expected: str, tmp_path: Path
) -> None:
    # yt-dlp's own format choice, without the internet. 360p isn't there: the
    # smallest above it is taken.
    settings = options(Kind.MP4, tmp_path, height)
    # yt-dlp's default when ffmpeg is there, set here so the test doesn't
    # need ffmpeg.
    settings["format"] = "bv*+ba/b"
    settings["quiet"] = True
    with yt_dlp.YoutubeDL(settings) as ydl:
        chosen: Any = ydl.process_ie_result(youtube_like_video(), download=False)
    assert chosen["format_id"] == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            {
                "downloaded_bytes": 12 * 1024**2,
                "total_bytes": 24 * 1024**2,
                "info_dict": {"vcodec": "avc1", "acodec": "none", "title": "A cat"},
            },
            Progress("Downloading video: 50% of 24 MB", 50.0, "A cat"),
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
    "account needed, no cookies hint (from the source, tenplay)": (
        "[TenPlay] 123: Login required to access this video. Use --username "
        "and --password, --netrc-cmd, or --netrc (tenplay) to provide account "
        "credentials",
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
    "subtitles missing (measured 2026-11-12)": (
        "Unable to download video subtitles for 'en': HTTP Error 404: File not found",
        SUBTITLES_FAILED,
    ),
    "subtitles refused (yt-dlp's text from the source, YouTube's from memory)": (
        "Unable to download video subtitles for 'en': HTTP Error 429: Too Many "
        "Requests",
        SUBTITLES_FAILED,
    ),
}


@pytest.mark.parametrize(
    ("text", "expected"), list(ERROR_TEXTS.values()), ids=list(ERROR_TEXTS)
)
def test_plain_message(text: str, expected: str) -> None:
    assert plain_message(f"ERROR: {text}") == expected


def test_reddit_refusing_the_sign_in_file_gets_its_own_message() -> None:
    reddit = ERROR_TEXTS["reddit"][0]
    assert plain_message(f"ERROR: {reddit}", signed_in=True) == REDDIT_REFUSED
    age, expected = ERROR_TEXTS["age (from the source)"]
    assert plain_message(f"ERROR: {age}", signed_in=True) == expected


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


# The Cookie headers the test server received.
cookies_received: list[str] = []


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if cookie := self.headers.get("Cookie"):
            cookies_received.append(cookie)
        super().do_GET()


@pytest.fixture(scope="module")
def clip_link(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """A link to a 1-second MP4 (H.264 and AAC) made by ffmpeg."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("needs ffmpeg")
    site = tmp_path_factory.mktemp("site")
    # Pages with two videos, which yt-dlp treats as a playlist named after
    # the page, its videos "Two clips (1)" and "(2)": both there, one or both
    # missing, with English subtitles for the first only.
    subtitled = '<track kind="subtitles" src="clip.vtt" srclang="{}">'
    for page, first, second in (
        ("two.html", "clip.mp4", "clip2.mp4"),
        ("one-missing.html", "missing.mp4", "clip.mp4"),
        ("both-missing.html", "missing.mp4", "gone.mp4"),
        ("two-subtitled.html", "clip.mp4", "clip2.mp4"),
    ):
        tracks = ("", "")
        if page == "two-subtitled.html":
            tracks = (subtitled.format("en"), subtitled.format("de"))
        (site / page).write_text(
            "<html><head><title>Two clips</title></head><body>"
            f'<video src="{first}">{tracks[0]}</video>'
            f'<video src="{second}">{tracks[1]}</video>'
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
    # The clip as HLS, which yt-dlp downloads in pieces (stream.m3u8, stream0.ts).
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(site / "clip.mp4"), "-c",
         "copy", "-f", "hls", "-hls_list_size", "0", str(site / "stream.m3u8")],
        check=True,
    )  # fmt: skip
    # Pages with the clip and its subtitles (a <track>, which yt-dlp reads):
    # in English, and in German only.
    (site / "clip.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n")
    # A third page's subtitle file isn't there.
    for page, language, subtitles in (
        ("subtitled.html", "en", "clip.vtt"),
        ("german.html", "de", "clip.vtt"),
        ("broken-subtitles.html", "en", "missing.vtt"),
    ):
        (site / page).write_text(
            "<html><head><title>Subtitled clip</title></head><body>"
            '<video src="clip.mp4">'
            f'<track kind="subtitles" src="{subtitles}" srclang="{language}">'
            "</video></body></html>"
        )
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


def run(
    link: str,
    kind: Kind,
    folder: Path,
    height: int | None = None,
    subtitles: bool = False,
) -> list[Event]:
    events: list[Event] = []
    download(link, kind, folder, events.append, height, subtitles)
    return events


@pytest.mark.parametrize("kind", list(Kind))
def test_download_then_already_there(
    clip_link: str, kind: Kind, tmp_path: Path
) -> None:
    folder = tmp_path / "Videos"  # not there yet: download() makes it
    events = run(clip_link, kind, folder)
    assert any(isinstance(event, Progress) for event in events)
    assert all(e.title == "clip" for e in events if isinstance(e, Progress))
    if kind == Kind.MP3:
        assert Progress("Converting to MP3...", None, "clip") in events
    assert events[-1] == Done(folder / f"clip.{kind}", already_there=False)
    assert sorted(path.name for path in folder.iterdir()) == [f"clip.{kind}"]

    # The second time nothing is downloaded. (MP3 still shows "Converting to
    # MP3..." for a moment: yt-dlp checks the existing file.)
    again = run(clip_link, kind, folder)
    bars = [e for e in again if isinstance(e, Progress) and e.percent is not None]
    assert bars == []
    assert again[-1] == Done(folder / f"clip.{kind}", already_there=True)


def test_mp3_keeps_the_mp4_already_there(clip_link: str, tmp_path: Path) -> None:
    # The test site has no separate audio, so yt-dlp makes the MP3 from the
    # MP4 already there, and without `keepvideo` deleted it afterwards.
    run(clip_link, Kind.MP4, tmp_path)
    mp4 = (tmp_path / "clip.mp4").read_bytes()
    events = run(clip_link, Kind.MP3, tmp_path)
    assert events[-1] == Done(tmp_path / "clip.mp3", already_there=False)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["clip.mp3", "clip.mp4"]
    assert (tmp_path / "clip.mp4").read_bytes() == mp4


def test_another_quality_is_a_file_of_its_own(clip_link: str, tmp_path: Path) -> None:
    # Best, then 720p of the same video to save space: the 720p one isn't
    # "already there".
    assert run(clip_link, Kind.MP4, tmp_path)[-1] == Done(tmp_path / "clip.mp4", False)
    smaller = run(clip_link, Kind.MP4, tmp_path, 720)
    assert smaller[-1] == Done(tmp_path / "clip (720p).mp4", already_there=False)
    again = run(clip_link, Kind.MP4, tmp_path, 720)
    assert again[-1] == Done(tmp_path / "clip (720p).mp4", already_there=True)


def test_subtitles_are_saved_next_to_the_video(clip_link: str, tmp_path: Path) -> None:
    page = clip_link.replace("clip.mp4", "subtitled.html")
    events = run(page, Kind.MP4, tmp_path, subtitles=True)
    done = events[-1]
    assert isinstance(done, Done)
    assert not done.no_subtitles
    # The bar shows the video only: it doesn't fill for the subtitles first
    # and then start again.
    bars = [e.percent for e in events if isinstance(e, Progress) and e.percent]
    assert bars, "no progress shown"
    assert bars == sorted(bars), f"the bar went back: {bars}"
    srt = done.path.with_suffix(".en.srt")
    files = sorted(path.name for path in tmp_path.iterdir())
    assert files == sorted([done.path.name, srt.name])
    # Converted from the site's vtt by ffmpeg.
    assert "00:00:00,000 --> 00:00:01,000\nHello" in srt.read_text(encoding="utf-8")


def test_subtitles_for_a_video_already_there_leave_it_alone(
    clip_link: str, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "subtitled.html")
    video = run(page, Kind.MP4, tmp_path)[-1]
    assert isinstance(video, Done)
    assert [path.name for path in tmp_path.iterdir()] == [video.path.name]
    written = video.path.stat().st_mtime_ns
    assert run(page, Kind.MP4, tmp_path, subtitles=True)[-1] == Done(video.path, True)
    assert video.path.with_suffix(".en.srt").is_file()
    assert video.path.stat().st_mtime_ns == written, "the video was written again"


def test_no_english_subtitles_still_downloads_and_says_so(
    clip_link: str, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "german.html")
    done = run(page, Kind.MP4, tmp_path / "German", subtitles=True)[-1]
    assert isinstance(done, Done)
    assert done.no_subtitles
    assert [path.name for path in done.path.parent.iterdir()] == [done.path.name]
    # A video with no subtitles at all.
    plain = run(clip_link, Kind.MP4, tmp_path / "None", subtitles=True)[-1]
    assert plain == Done(tmp_path / "None" / "clip.mp4", False, no_subtitles=True)


def test_subtitles_that_fail_stop_the_download_with_a_plain_message(
    clip_link: str, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "broken-subtitles.html")
    assert run(page, Kind.MP4, tmp_path, subtitles=True) == [Failed(SUBTITLES_FAILED)]
    assert list(tmp_path.iterdir()) == [], "something was saved"


def test_broken_link_gives_a_plain_message(clip_link: str, tmp_path: Path) -> None:
    missing = clip_link.replace("clip.mp4", "missing.mp4")
    assert run(missing, Kind.MP4, tmp_path) == [Failed(NOT_AVAILABLE)]
    assert run("hello", Kind.MP4, tmp_path) == [Failed(NOT_A_LINK)]


def test_download_sends_the_sign_in_files_cookies(
    clip_link: str, tmp_path: Path
) -> None:
    # A cookies.txt (Netscape format, tab-separated) with one cookie for the
    # test server: domain, subdomains too, path, https only, expires, name, value.
    line = "\t".join(["127.0.0.1", "FALSE", "/", "FALSE", "4102444800", "sid", "42"])
    exported = f"# Netscape HTTP Cookie File\n{line}\n"
    downloader.COOKIES.write_text(exported)
    cookies_received.clear()
    assert isinstance(run(clip_link, Kind.MP4, tmp_path / "Videos")[-1], Done)
    assert "sid=42" in cookies_received
    # yt-dlp wrote the cookies back into its copy, not into the file.
    assert downloader.COOKIES.read_text() == exported


def test_broken_sign_in_file_gives_a_plain_message(
    clip_link: str, tmp_path: Path
) -> None:
    # The extension's other format, JSON, then a file that's no cookies file.
    for text in ['[{"domain": ".reddit.com", "name": "a"}]', "hello\n"]:
        downloader.COOKIES.write_text(text)
        assert run(clip_link, Kind.MP4, tmp_path) == [Failed(COOKIES_BROKEN)]
    # Not text at all: the app can't even read it, but the window still hears
    # that the download ended.
    downloader.COOKIES.write_bytes(b"\xff\xfe\x00")
    [event] = run(clip_link, Kind.MP4, tmp_path)
    assert isinstance(event, Failed)
    assert event.message.startswith("Something went wrong")


@pytest.mark.parametrize("kind", list(Kind))
def test_playlist_saves_every_video_into_a_folder_of_its_own(
    clip_link: str, kind: Kind, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "two.html")
    events = run(page, kind, tmp_path)
    folder = tmp_path / "Two clips"
    names = [f"Two clips (1).{kind}", f"Two clips (2).{kind}"]
    assert events[-1] == Done(folder / names[0], False, playlist=Playlist(2, 2, 0))
    # An MP3's source is deleted after each video.
    assert sorted(path.name for path in folder.iterdir()) == names
    assert list(tmp_path.iterdir()) == [folder]
    shown = [event for event in events if isinstance(event, Progress)]
    assert shown[0] == Progress("Video 1 of 2: Looking it up...", None, "Two clips")
    assert Progress("Video 2 of 2: Looking it up...", None, "Two clips") in shown
    assert any(e.text.startswith("Video 2 of 2: Downloading: ") for e in shown)
    assert all(event.title == "Two clips" for event in shown)

    # The second time nothing is downloaded.
    again = run(page, kind, tmp_path)
    assert again[-1] == Done(folder / names[0], True, playlist=Playlist(2, 0, 2))


def test_a_video_that_fails_doesnt_stop_the_playlist(
    clip_link: str, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "one-missing.html")
    first = tmp_path / "Two clips" / "Two clips (2).mp4"  # the first saved
    assert run(page, Kind.MP4, tmp_path)[-1] == Done(
        first, False, playlist=Playlist(2, 1, 0, why=NOT_AVAILABLE)
    )
    none = clip_link.replace("clip.mp4", "both-missing.html")
    assert run(none, Kind.MP4, tmp_path / "None")[-1] == Failed(
        "None of the 2 videos could be downloaded. "
        f"Why the first failed: {NOT_AVAILABLE}"
    )


def test_a_playlist_counts_the_videos_without_english_subtitles(
    clip_link: str, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "two-subtitled.html")
    first = tmp_path / "Two clips" / "Two clips (1).mp4"
    assert run(page, Kind.MP4, tmp_path, subtitles=True)[-1] == Done(
        first, False, playlist=Playlist(2, 2, 0, no_subtitles=1)
    )
    assert first.with_suffix(".en.srt").is_file()


def cancel_at(
    text: str | None,
    link: str,
    kind: Kind,
    folder: Path,
    subtitles: bool = False,
    meanwhile: Callable[[], object] = lambda: None,
) -> list[Event]:
    """Download, and click Cancel when the first progress text starting with
    `text` is reported (None: before the download starts). `meanwhile` runs
    at that moment too."""
    events: list[Event] = []
    cancel = threading.Event()
    if text is None:
        cancel.set()

    def report(event: Event) -> None:
        events.append(event)
        if isinstance(event, Progress) and text and event.text.startswith(text):
            if not cancel.is_set():
                meanwhile()
            cancel.set()

    download(link, kind, folder, report, subtitles=subtitles, cancel=cancel)
    return events


@pytest.mark.parametrize(
    ("page", "kind", "subtitles", "text"),
    [
        ("clip.mp4", Kind.MP4, False, "Downloading"),
        ("clip.mp4", Kind.MP4, False, None),
        ("clip.mp4", Kind.MP3, False, "Downloading"),
        ("clip.mp4", Kind.MP3, False, "Converting to MP3"),
        # The subtitles, finished before the video starts, go too.
        ("subtitled.html", Kind.MP4, True, "Downloading"),
        # yt-dlp leaves a .part (still open), -Frag and .ytdl files.
        ("stream.m3u8", Kind.MP4, False, "Downloading"),
    ],
    ids=[
        "while downloading",
        "while looking up",
        "MP3 while downloading",
        "while converting to MP3",
        "with subtitles",
        "HLS",
    ],
)
def test_cancel_deletes_what_the_download_saved(
    clip_link: str,
    page: str,
    kind: Kind,
    subtitles: bool,
    text: str | None,
    tmp_path: Path,
) -> None:
    link = clip_link.replace("clip.mp4", page)
    events = cancel_at(text, link, kind, tmp_path, subtitles)
    assert events[-1] == Cancelled()
    assert not any(isinstance(event, Done | Failed) for event in events)
    assert [path.name for path in tmp_path.iterdir()] == []
    if text is None:
        assert events == [Cancelled()], "no progress after Cancel"


def test_cancel_leaves_every_other_file_alone(clip_link: str, tmp_path: Path) -> None:
    # Named like the video, but there before: an MP3 of it and the user's
    # own subtitles. And one that lands in the folder during the download.
    before = {"clip.mp3": b"an earlier MP3", "clip.en.srt": b"own subtitles"}
    for name, data in before.items():
        (tmp_path / name).write_bytes(data)
    meanwhile = tmp_path / "another video.mp4"
    events = cancel_at(
        "Downloading",
        clip_link,
        Kind.MP4,
        tmp_path,
        meanwhile=lambda: meanwhile.write_bytes(b"saved meanwhile"),
    )
    assert events[-1] == Cancelled()
    left = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert left == {**before, meanwhile.name: b"saved meanwhile"}


def test_cancel_while_converting_keeps_the_mp4_already_there(
    clip_link: str, tmp_path: Path
) -> None:
    # The MP3 is made from that MP4 (test_mp3_keeps_the_mp4_already_there).
    run(clip_link, Kind.MP4, tmp_path)
    mp4 = (tmp_path / "clip.mp4").read_bytes()
    events = cancel_at("Converting to MP3", clip_link, Kind.MP3, tmp_path)
    assert events[-1] == Cancelled()
    assert [path.name for path in tmp_path.iterdir()] == ["clip.mp4"]
    assert (tmp_path / "clip.mp4").read_bytes() == mp4


@pytest.mark.parametrize(
    ("kind", "text"),
    [
        (Kind.MP4, "Video 2 of 2: Looking it up"),
        (Kind.MP4, "Video 2 of 2: Downloading"),
        (Kind.MP3, "Video 2 of 2: Converting to MP3"),
    ],
    ids=["between videos", "while downloading", "while converting to MP3"],
)
def test_cancel_during_a_playlist_keeps_the_videos_finished(
    clip_link: str, kind: Kind, text: str, tmp_path: Path
) -> None:
    page = clip_link.replace("clip.mp4", "two.html")
    events = cancel_at(text, page, kind, tmp_path)
    first = tmp_path / "Two clips" / f"Two clips (1).{kind}"
    assert events[-1] == Cancelled((first,))
    # The second video's files are gone, the first's MP3 source too.
    assert list(first.parent.iterdir()) == [first]


def test_a_video_named_like_one_finished_before_it(
    clip_link: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two videos of one name: yt-dlp takes the second for the first's file,
    # which is already there. It still converts it to MP3 (and Cancel stops
    # it then); its files have the same names as the first video's.
    monkeypatch.setattr(downloader, "FILE_NAME", "Same.%(ext)s")
    page = clip_link.replace("clip.mp4", "two.html")
    same = tmp_path / "Two clips" / "Same.mp3"
    assert run(page, Kind.MP3, tmp_path)[-1] == Done(
        same, False, playlist=Playlist(2, 1, 1)
    )
    same.unlink()
    events = cancel_at("Video 2 of 2: Converting to MP3", page, Kind.MP3, tmp_path)
    assert events[-1] == Cancelled((same,))
    assert list(same.parent.iterdir()) == [same], "Cancel deleted the first video"


def test_remove_unfinished_deletes_only_new_files_named_like_the_video(
    tmp_path: Path,
) -> None:
    names = [
        "Title.mp4.part",
        "Title.f137.mp4.part-Frag3.part",
        "Title.en.srt",
        "Title.mp3",  # there before
        "Title (720p).mp4",  # another quality: another name
        "Titles.mp4",
        "Other.mp4",
    ]
    for name in names:
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "Title.folder").mkdir()  # only files are deleted
    remove_unfinished(
        tmp_path, {tmp_path / "Title."}, there_before={tmp_path / "Title.mp3"}
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "Other.mp4",
        "Title (720p).mp4",
        "Title.folder",
        "Title.mp3",
        "Titles.mp4",
    ]


def test_remove_mp3_sources_deletes_only_new_sources(tmp_path: Path) -> None:
    for name in ("new.webm", "earlier.mp4", "fetched.mp3"):
        (tmp_path / name).write_bytes(b"")
    # A site with MP3 audio: the download is the MP3 itself, new but kept.
    for source, mp3 in (("new.webm", "new.mp3"), ("fetched.mp3", "fetched.mp3")):
        remove_mp3_sources({tmp_path / source}, tmp_path / mp3, set(), tmp_path)
    earlier = tmp_path / "earlier.mp4"
    remove_mp3_sources({earlier}, tmp_path / "earlier.mp3", {earlier}, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["earlier.mp4", "fetched.mp3"]


def test_cancel_in_a_subfolder_leaves_what_was_there_before(tmp_path: Path) -> None:
    # Where a playlist's videos will go: a folder directly inside the
    # download folder, perhaps there from an earlier download of it.
    playlist = tmp_path / "Playlist"
    (playlist / "Deeper").mkdir(parents=True)
    (playlist / "Title.mp3").write_bytes(b"an earlier MP3")
    there_before = paths_in(tmp_path)
    assert there_before == {playlist, playlist / "Title.mp3", playlist / "Deeper"}
    (playlist / "Title.mp4.part").write_bytes(b"")
    remove_unfinished(tmp_path, {playlist / "Title."}, there_before)
    assert sorted(path.name for path in playlist.iterdir()) == ["Deeper", "Title.mp3"]


def test_a_subfolder_that_cant_be_listed_is_left_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Rather than failing every download (such as "Access is denied").
    locked = tmp_path / "Locked"
    locked.mkdir()
    (locked / "Title.mp4").write_bytes(b"")
    listing = Path.iterdir

    def iterdir(path: Path) -> Iterator[Path]:
        if path == locked:
            raise PermissionError(13, "Access is denied", str(path))
        return listing(path)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    assert paths_in(tmp_path) == {locked}


def test_nothing_is_deleted_outside_the_download_folder(tmp_path: Path) -> None:
    folder = tmp_path / "Videos"
    deeper = folder / "Playlist" / "Deeper"
    deeper.mkdir(parents=True)
    (tmp_path / "Videos old").mkdir()
    # A playlist named ".." would put its videos into the folder above.
    kept = [
        folder / ".." / "Title.mp4",
        folder / ".." / "Videos old" / "Title.mp4",
        deeper / "Title.mp4",
    ]
    deleted = [folder / "Title.mp4", folder / "Playlist" / "Title.mp4"]
    for path in kept + deleted:
        path.write_bytes(b"")
    starts = {path.with_name("Title.") for path in kept + deleted}
    remove_unfinished(folder, starts, there_before=set())
    remove_mp3_sources({kept[0]}, folder / "Title.mp3", set(), folder)
    assert [path for path in kept if not path.is_file()] == []
    assert [path for path in deleted if path.exists()] == []


def test_log_keeps_the_errors_and_prints_like_yt_dlp(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = Log()
    log.debug("[generic] Extracting URL")
    log.warning("No subtitles")
    log.error("\r")
    log.error("ERROR: [generic] missing: HTTP Error 404")
    assert log.errors == ["ERROR: [generic] missing: HTTP Error 404"]
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err == (
        "WARNING: No subtitles\n\r\nERROR: [generic] missing: HTTP Error 404\n"
    )


def test_errors_and_warnings_still_reach_the_terminal(
    clip_link: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(clip_link.replace("clip.mp4", "missing.mp4"), Kind.MP4, tmp_path)
    assert "ERROR: [generic] missing: Unable to download" in capsys.readouterr().err
    # yt-dlp warns about every page it reads with its generic extractor.
    run(clip_link.replace("clip.mp4", "german.html"), Kind.MP4, tmp_path)
    warning = "WARNING: [generic] Falling back on generic information extractor"
    assert warning in capsys.readouterr().err


def test_missing_ffmpeg_fails_before_downloading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert run("https://example.com/video", Kind.MP4, tmp_path) == [
        Failed(FFMPEG_MISSING)
    ]
