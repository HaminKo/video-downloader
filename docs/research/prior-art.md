# Prior art: existing video downloaders and what to reuse

Researched 2026-11-10 during project setup: two quick web searches, not a deep review. Each point says whether it comes from a source or from Claude's general knowledge (not yet checked).

## yt-dlp does the downloading
- yt-dlp is the standard free downloader (a fork of youtube-dl). It supports thousands of sites and works both as a command-line tool and as a Python library. License: Unlicense. Source: [yt-dlp on GitHub](https://github.com/yt-dlp/yt-dlp).
- Sites beyond YouTube (checked 2026-11-10 in [supportedsites.md](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)): Reddit, Twitter, Bluesky, Imgur, Facebook, Instagram, TikTok, Vimeo and Twitch are all listed. Single posts are not marked broken; some Instagram profile and TikTok tag/sound pages are marked "Currently broken". Our app passes the link to yt-dlp unchanged, so no site needs code of its own in our app. Whether a given site really downloads hasn't been tested yet; To do 3's test includes Reddit and X.
  - Tested 2026-11-11 (To do 3, step A): YouTube works (MP4 and MP3). Reddit fails: Reddit blocks yt-dlp unless it can impersonate a browser (the `curl_cffi` package); details in [yt-dlp-library.md](yt-dlp-library.md#sites).
  - Not checked (general knowledge): x.com links go through the "twitter" extractor; Instagram often asks for a login, and age-restricted X posts, private posts and some Reddit NSFW posts need one too. A login needs browser cookies, which is on the "Later" list in docs/todo.md.
- It needs ffmpeg to join separate video and audio streams and to convert to MP3. (General knowledge; it's in the yt-dlp README.)
- **YouTube needs a JavaScript runtime since yt-dlp 2025.11.12.** Deno is recommended and is the only runtime enabled by default; Node, Bun and QuickJS also work but must be turned on (`--js-runtimes`). YouTube without a runtime is now "deprecated". yt-dlp also needs the yt-dlp-ejs package, which the official .exe already includes. Sources: [yt-dlp issue #15012](https://github.com/yt-dlp/yt-dlp/issues/15012), [EJS wiki](https://github.com/yt-dlp/yt-dlp/wiki/EJS), [GIGAZINE](https://www.gigazine.net/gsc_news/en/20251113-yt-dlp-required-deno-javascript-runtime).
  - Confirmed 2026-11-10 (To do 1): `pip install "yt-dlp[default]"` installed yt-dlp 2026.10.26 with yt-dlp-ejs 0.8.0, and `yt-dlp -v` lists `yt_dlp_ejs-0.8.0` under optional libraries and `deno-2.9.8` under JS runtimes.
  - Node 26 is already installed on this PC, so it could replace Deno with one setting. Deno is still the suggestion because it works with no extra settings.

## Existing apps built on yt-dlp
Using one of these needs no building at all. The user chose to build their own (docs/decisions.md, 2026-11-10).
- **Stacher:** free desktop app (optional paid Premium) for Windows, Mac and Linux; the most often recommended for Windows. Source: [VideoHelp](https://videohelp.com/software/Stacher).
- **Parabolic** (formerly Tube Converter): sources disagree on whether there are official Windows builds; check its releases page. Source: [Linux Adictos](https://en.linuxadictos.com/parabolic-perhaps-the-best-gui-interface-for-yt-dlp-that-is-also-multiplatform.html).
- **Media Downloader** (free, open source, Windows), **yt-dlg** (formerly youtube-dl-gui), **kannagi0303/yt-dlp-gui** (Windows only). Source: [BrightCoding guide, 2025](https://blog.brightcoding.dev/2025/12/06/the-ultimate-guide-to-gui-front-ends-for-youtube-dl-yt-dlp-download-videos-like-a-pro-2025-edition).
- Not checked: their licenses, or whether any of their code or design is worth borrowing.

## Browser extensions
The search found nothing on extensions. Everything in this section is general knowledge, not checked; research it before building the Edge button.
- Most sites stream video in small chunks (HLS/DASH), often with video and audio separate. An extension alone can't join them well, so the known downloader extensions (for example Video DownloadHelper) need a companion program on the PC.
- Chrome Web Store policy bars extensions that download YouTube videos; Edge's store is thought to be similar. This doesn't matter for a personal extension loaded unpacked.
- An extension talks to a program on the PC through **native messaging**: a small JSON manifest plus a registry key (for Edge under `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\`) that names the extension's ID. The other way, a local web server on localhost, is simpler but any web page could call it unless it's protected with a secret token.

## What we reuse
- yt-dlp as a Python library (its `YoutubeDL` class with progress hooks), plus ffmpeg and Deno as separate programs.
- No code from the existing apps.
