# Signing in (Reddit)

Reddit only gives a post's video to people who are signed in. The app can't use Edge's or Chrome's sign-ins directly: they're locked and encrypted ([research](research/signing-in.md)). So once, you export a copy of Reddit's sign-in from your browser as a file, and the app uses that file whenever it's there. No password goes into the app.

## Set it up (once)
1. In the browser you're signed in to Reddit with (Edge or Chrome), install the extension **Get cookies.txt LOCALLY** by kairi003. The name must include "LOCALLY": an older extension called "Get cookies.txt" was found to be malware. It's on the Chrome Web Store; Edge installs from there once you allow extensions from other stores.
2. Open any reddit.com page while signed in, click the extension's icon, keep the format **Netscape** and click **Export**. Not **Export All**, which puts every site's sign-in in the file (see YouTube below). The browser saves `www.reddit.com_cookies.txt` in your Downloads folder.
3. Move it into the app's own folder (PowerShell):
   ```powershell
   New-Item -ItemType Directory -Force "$env:APPDATA\video-downloader" | Out-Null
   Move-Item -Force "$env:USERPROFILE\Downloads\www.reddit.com_cookies.txt" "$env:APPDATA\video-downloader\cookies.txt"
   ```
   If it says it can't find the file, check that the format was Netscape: JSON saves a `.json` file, which yt-dlp can't read.
4. Download a Reddit link as usual.

## When it stops working
If the window says "Reddit didn't accept your sign-in", Reddit has ended that sign-in (for example, you signed out in the browser). Do steps 2 and 3 again; the new file replaces the old one.

To stop signing in, delete the file:
```powershell
Remove-Item "$env:APPDATA\video-downloader\cookies.txt"
```

## Good to know
- **The file is a key to your Reddit account**, in plain text: anyone who has it can use Reddit as you. Leave it in that folder; don't copy it into the project, share it or send it anywhere.
- Each cookie only goes to its own site, so YouTube and other sites never see your Reddit sign-in.
- The app only reads the file and never changes it.
- If the window says "The sign-in file can't be read", the file isn't in the Netscape cookies format: export it again, or delete it. Until then every download fails, not only Reddit's.
- **Not for YouTube.** yt-dlp's wiki warns: "By using your account with yt-dlp, you run the risk of it being banned (temporarily or permanently)." So the app doesn't sign in to YouTube, and members-only or age-restricted YouTube videos don't work.
