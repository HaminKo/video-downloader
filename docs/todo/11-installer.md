# To do 11: An .exe installer (large): "An .exe installer"

- **Goal:** install and start the app like any Windows program: a Start-menu entry, no terminal, no Python setup.
- **Read first:** README "Install and run"; pyproject.toml; docs/decisions.md (ffmpeg and Deno from winget; "updating yt-dlp automatically" in the Reddit entry).
- **Approach:** research first: a bundler (e.g. PyInstaller) packs Python, tkinter and yt-dlp into an .exe, and an installer (e.g. Inno Setup) adds the Start-menu entry. Inside an .exe, `pip install -U` no longer updates yt-dlp, so updates need their own answer here (the start-up update idea from To do 4 fits).
- **Note from To do 18:** the window's icon is read from extension/icons (bundle that folder, or point `app.ICONS` at the bundled copy), and `start()` gives the process the taskbar ID `VideoDownloader.App`: the Start-menu shortcut should carry the same ID (`System.AppUserModel.ID`), so a pinned taskbar button starts the app. The installer's .ico can be made from the same PNGs.
- **Ask the user:** (a) bundle ffmpeg and Deno, or keep them from winget? Suggested: keep winget (smaller; `winget upgrade` updates them). (b) one .exe or an installer? Suggested: an installer. (c) code signing? Suggested: no; Windows SmartScreen warns on the first run ("Run anyway").
- **Test:** Claude: the build runs and the .exe starts. User: install, start from the Start menu, download a YouTube video, uninstall.
