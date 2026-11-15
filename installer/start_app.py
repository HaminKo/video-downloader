"""Video Downloader.exe starts here, as `python -m video_downloader` does,
after loading the newest yt-dlp the app has downloaded (ytdlp_update.py)."""

from video_downloader import ytdlp_update

ytdlp_update.use_newest()  # before the app, which imports yt-dlp

from video_downloader.app import main  # noqa: E402

main()
