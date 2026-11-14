# Using the app

The details behind the summary in the [README](../README.md).

Paste a link, choose **Video (MP4)** or **Audio only (MP3)** and, for a video, its quality and whether you want English subtitles, then press Download (or Enter). The link goes into the list of downloads, and the bar and the line under the list show the progress.
- **More links while one downloads:** paste the next link and press Download again; the link box empties each time. Each link waits in the list ("Waiting") and starts when the ones above it have ended, with the choices it was added with, so you can pick MP3 for one and 720p for the next. A failed or cancelled one doesn't stop the rest. Closing the window drops the links still waiting.
- **The list** shows your downloads, oldest at the top: the video's title (the link until it has been looked up), its choices, and how far it got (Waiting, Downloading 40%, Done, Already there, Failed in red, Cancelled). Click a row to see its message under the list, such as why it failed. A download that starts gets selected, unless you clicked another row meanwhile.
- **Past downloads** (the history): when the window opens, the list already holds the downloads from earlier sessions that saved a file (Done or Already there; the newest 200), scrolled to the newest. This session's downloads go below them. Play and Show in folder work on them as on new ones. Failed and cancelled downloads aren't kept, nor is a file Play found moved or deleted. The history is the file `%APPDATA%\video-downloader\history.json`; deleting it while the app is closed empties the list. If it is broken, the list starts empty and the next download writes it anew; if another program holds it when the window opens, the list starts empty and the app leaves the file alone until the next start.
- **Remove** (or the Delete key) takes the selected row out of the list, and out of the history: a waiting link won't be downloaded. It never deletes a video or audio file. The running download can't be removed; Cancel stops it.
- Files go to the **Videos** folder inside your Downloads folder, named after the video's title.
- MP4s use H.264 video with AAC sound, so they play everywhere (Windows' own player, phones).
- **Video quality:** **Best** is the best that plays everywhere, which on YouTube means at most 1080p. **720p** and **480p** save space: on a long YouTube video, 720p was a little over half the size of Best, and 480p about a fifth. A video with nothing that small comes in its smallest size above it. A 720p or 480p file has the quality after its title (`Title (720p).mp4`), so it sits next to a copy at Best instead of counting as already there. The choice starts at Best each time the app opens.
- **English subtitles:** saved as a separate file next to the video (`Title.en.srt`), because Windows can't read subtitles inside an MP4. You get the video's real English subtitles when it has them, otherwise the site's automatic ones (on YouTube, sometimes its automatic translation into English). A video without English subtitles still downloads, and the window says so. If the video is already there, only the subtitles are added. If the subtitles can't be downloaded, nothing is saved and the window says so: try again later, or untick the box. The box starts unticked each time the app opens.
- A file that is already there isn't downloaded again; the window says so.
- **Play** opens the selected row's file in your default player (VLC also picks up the subtitles next to it); double-clicking a finished row does the same. **Show in folder** opens the Videos folder with that file selected. Both work while another download runs. Nothing opens by itself. When the selected row has no file (waiting, running, failed or cancelled), Play is greyed out and Show in folder just opens the folder.
- **Cancel** stops the running download (the next waiting one then starts): its row says "Cancelled" and the window deletes what that download had saved (half-downloaded pieces, and its subtitles); files that were in the folder before are never touched (a half-downloaded file left by closing the window included). While ffmpeg joins video and audio or converts to MP3, Cancel takes effect when that step is done. Closing the window also stops a download, but leaves the half-downloaded file, which yt-dlp continues from if you download the same video again.
- **A link from outside:** `python -m video_downloader LINK` (with the `.venv` active) puts the link in the box of the window that is open, replacing what was there, and brings that window to the front, also when it was minimized; with no window open, it opens one with the link in the box. It never starts the download: choose MP4 or MP3, then press Download. The line under the list says "Link received" until the selected row's next progress replaces it. With two windows open, the first one opened gets the links. The [Chrome button](#the-chrome-button) does the same with one click. If Windows doesn't let the window come to the front, its taskbar button flashes instead.
- **Downloading a link from outside at once:** `python -m video_downloader LINK --download mp3` (or `--download mp4`, with `--quality 720p` or `--quality 480p` and `--subtitles` if wanted; without them Best and no subtitles) adds the link to the list of the window that is open, with those choices, as if you had chosen them and pressed Download. The window stays where it is, and its link box and its own choices stay as they were. With no window open, one opens minimized on the taskbar with the download running. `python -m video_downloader --help` lists the options.
- A link to a playlist or channel downloads only its first video, and the window says so.
- When a download fails, the line under the bar says why in plain words, in red: not a link, a site or page with no video, no internet, a private or removed video, one that needs signing in, or ffmpeg missing. Anything else shows yt-dlp's own message. yt-dlp's full message is also printed in the terminal the app runs from.
- Reddit only gives a post's video to people who are signed in. To sign in, you export Reddit's sign-in from your browser once, as a file the app uses: see [Signing in](signing-in.md). The app doesn't sign in to YouTube (it could get the account banned).

## The Chrome button
A button in Chrome's toolbar that sends the page you're on to the app: on a YouTube video, click it, and the app comes to the front with the link in the box (or opens with it), the same as a link from outside above. Then choose MP4 or MP3 and press Download.

**Setting it up**, once (in PowerShell, in the project folder, with the `.venv` active):
1. Install the helper Chrome starts for each click:
   ```powershell
   python -m video_downloader.browser install
   ```
   It prints the folder to load in the next step and the extension's ID.
2. In Chrome, open `chrome://extensions`, turn on **Developer mode** (top right), click **Load unpacked** and choose the `extension` folder in the project folder. Check that the ID under Video Downloader is the one the command printed.
3. Pin the button: click the puzzle piece in Chrome's toolbar, then the pin next to Video Downloader.

**Using it:** click the button on a page with a video. Nothing shows in Chrome when it works; the app coming to the front is the sign. A red **!** on the button means the link didn't reach the app; point at the button to see why:
- "Only web pages can be sent": the New Tab page, Chrome's own pages (`chrome://`) and files opened from disk can't be sent.
- "The helper isn't installed": run the install command from step 1.
- Anything else is Chrome's own message, for example when the helper can't start.

The **!** goes away at the next click that works.

**After moving the project or making the `.venv` anew**, run the install command again, and in `chrome://extensions` click the reload arrow under Video Downloader (or load it again from the new folder). The helper runs the project's Python, and Chrome loads the button from the project folder.

**Removing it:**
```powershell
python -m video_downloader.browser uninstall
```
Then remove the button in `chrome://extensions` (Remove under Video Downloader). Uninstalling removes only the helper's two files (`host.bat` and `host.json` in `%APPDATA%\video-downloader`) and its registry entry; the history and the sign-in file stay.
