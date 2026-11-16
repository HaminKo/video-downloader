# Changelog

All notable changes to video-downloader are listed here, newest first.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- When a downloaded yt-dlp doesn't work with the app, the app's own yt-dlp update no longer waits an extra day before getting the last version that does.

## [0.1.1] - 2026-11-15

### Fixed
- When a new yt-dlp drops support for the app's Python version, the app's own yt-dlp update now gets the last yt-dlp that still works with the app, instead of staying on the one it has.

## [0.1.0] - 2026-11-15
The first version, for Windows (built and tested on Windows 11).

### Added
- Paste a link and press Download (or Enter): the video is saved as an MP4 that plays everywhere, or just the audio as an MP3, into the Videos folder inside Downloads, with a progress bar.
- Video quality Best, 720p or 480p, and English subtitles as a separate file next to the video.
- A list of downloads: links added while one downloads wait their turn, each with the choices it was added with. Cancel stops the running download.
- Playlists and channels: all their videos, into a folder named after the playlist. A playlist of more than 50 videos asks first.
- The newest 200 saved downloads stay in the list after a restart. Play and Show in folder open a download's file; Remove takes it out of the list and never deletes a file.
- Plain-language messages when a download fails, such as no internet, a private or removed video, or YouTube's bot check.
- Reddit videos, with a sign-in file exported from your browser ([Signing in](docs/signing-in.md)).
- A Chrome button that downloads the video on the page you're on, as MP4 or MP3, and can cancel it again.
- An installer for your account only, without admin rights, to download from the Releases page. The installed app keeps yt-dlp up to date by itself and offers a restart when a new version is ready.
- One window: starting the app again brings the open window to the front.
