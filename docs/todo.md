# To do

## Where we are
- Now: To do 3 (Download from a link)
- Next: none planned yet
- Updated: 2026-11-11

Next number: 4

## To do

### 3. Download from a link (medium): "paste a link, get the video"
- **Goal:** paste a link (for example a YouTube video, or any page yt-dlp supports), pick MP4 (video) or MP3 (audio only), press Download. The file lands in the download folder (default: Videos inside the user's Downloads folder), with progress shown and a clear message when it fails (unsupported site, no internet, private video).
- **Read first:** yt-dlp README "Embedding yt-dlp" (options, `progress_hooks`, MP3 post-processing); docs/research/prior-art.md.
- **Approach:** yt-dlp as a library, running in a background thread so the window keeps responding; progress goes to the window through a queue that the window checks with `after()`. MP4: best video and audio, merged into an MP4. MP3: best audio, converted with ffmpeg. yt-dlp's error messages are often long, so the status line needs to wrap (`wraplength`) instead of making the window wider (found in To do 1's review). Open the window wider: `minsize(480, 0)` counts screen pixels, so at this PC's 150% scaling the window is only about 320 px at normal size and the link box shows about 30 characters of a link (found in To do 2; docs/research/gui-testing.md). Scale the width with the DPI (`root.winfo_fpixels("1i") / 96`), so it looks the same at any scaling; the GUI test checks that a typical YouTube link fits in the link box.
- **Ask the user:** (a) MP4 that plays everywhere (H.264) or the highest quality (often AV1/VP9, which Windows' own player may not open)? Suggested: plays everywhere. (b) File name? Suggested: the video's title. (c) File already there? Suggested: skip it and say so. (d) How wide should the window open? Suggested: about 600 px at normal size, so a typical YouTube link (about 45 characters) fits.
- **Test:** Claude: tests for the download options and error messages that don't touch the internet, plus the GUI test. User: downloads a short YouTube video as MP4 and as MP3 and plays both, downloads one Reddit video and one X video as MP4 (Reddit keeps video and sound separate, so this checks that ffmpeg joins them), then tries a broken link and sees a clear message.

## Later, only if the user asks
- Edge button: send the page you're on to the app (browser extension plus native messaging; see docs/research/prior-art.md).
- Playlists and whole channels.
- Subtitles.
- Signing in (browser cookies) for private or members-only videos.
- A queue or history of downloads.
- Choosing the quality, or formats other than MP4 and MP3.
- An .exe installer.
- Never (not "later"): DRM-protected services such as Netflix, Disney+ or Spotify.

## Writing a to-do
Each to-do starts as an entry in the list above. When one grows past ~10 lines, offer to move it into its own file, docs/todo/NN-name.md.
- **Title** with size (small / medium / large) and the goal in the user's words.
- **Problem / Goal:** what is wrong or wanted, with an example. For a bug or research to-do, also what the user has seen (it exists, where, what works) and what is already ruled out.
- **Read first:** files and functions to look at, outside references.
- **Approach:** the suggested design, what to reuse.
- **Ask the user:** open questions, each with a suggested answer.
- **Test:** what Claude checks, and what the user tests by hand.
