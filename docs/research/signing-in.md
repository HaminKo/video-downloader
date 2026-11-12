# Signing in: browser cookies for yt-dlp on Windows

Found while planning To do 5 (2026-11-11), with yt-dlp 2026.10.26 and Edge 157.0.4341.46. "Measured" means checked on this PC; "read in the source" means `.venv/Lib/site-packages/yt_dlp`. Only metadata was looked at (key names, cookie counts), never a cookie's value.

## yt-dlp can't read Edge's or Chrome's cookies here
- **Measured:** Edge's and Chrome's `Local State` both have an `app_bound_encrypted_key` under `os_crypt`: their newer "app-bound" cookie encryption is on.
- **Measured:** copying either browser's `Default\Network\Cookies` file while the browser runs fails with PermissionError 13. yt-dlp copies the file the same way (`shutil.copy` in `_open_database_copy`) and then stops with "Could not copy Chrome cookie database" (yt-dlp issue #7271). Edge kept running in the background (5 `msedge` processes) at the time.
- **Read in the source** (`WindowsChromeCookieDecryptor` in cookies.py): yt-dlp only knows `v10` cookies (AES with a key protected by Windows' DPAPI) and plain DPAPI ones. Anything else, so also the app-bound `v20` cookies, is handed to DPAPI, fails with "Failed to decrypt with DPAPI" and stops the whole download.
- **yt-dlp issue #10927** (open, labelled "external-issue", last activity 2026-01-07): a maintainer expects that Chrome's change "will likely mean `--cookies-from-browser chrome` will be permanently broken on Windows". Workarounds named there: Firefox, or exporting cookies with a browser extension. Turning app-bound encryption off by policy (`ApplicationBoundEncryptionEnabled`) is called risky (it removes all cookies and a protection) and was reported not to help.
- Not measured: yt-dlp itself with Edge fully closed. Not needed: the key above and the source say it would fail on the `v20` cookies.

## Firefox
- yt-dlp reads Firefox's cookies (Firefox doesn't encrypt them and doesn't lock the file).
- **Measured:** Firefox is installed, but its profile has no cookies at all: it isn't used for browsing on this PC.

## A cookies.txt file (`cookiefile`)
- yt-dlp's FAQ ("How do I pass cookies to yt-dlp?") recommends the extensions "Get cookies.txt LOCALLY" (Chrome) and "cookies.txt" (Firefox), and warns that the older "Get cookies.txt" (without LOCALLY) was reported as malware. It also warns that an exported file holds your sign-ins: "take care in not letting this text file fall into the wrong hands."
- **Get cookies.txt LOCALLY** (kairi003, MIT, open source; Chrome Web Store and Firefox Add-ons; Edge installs Chrome Web Store extensions). Read in its source (`src/popup.mjs`): "Export" saves the current site's cookies as `<hostname>_cookies.txt` (on Reddit: `www.reddit.com_cookies.txt`), "Export All" saves every site's as `cookies.txt`; the format is Netscape (yt-dlp's) or JSON.
- **The file must be Netscape format.** Measured: a JSON file gives a `DownloadError` "Cookies file must be Netscape formatted, not JSON. See https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp".
- **yt-dlp writes the file back** when it closes (read in the source: `YoutubeDL.close()` calls `save_cookies()`, which opens the file with `'w'`). So after every download the file holds the refreshed sign-in cookies plus any cookies the sites set meanwhile (also anonymous ones, such as YouTube's visitor cookies).
- **The app gives yt-dlp a copy in memory instead** (To do 5, after the code review): `cookiefile` also takes a text stream (yt-dlp's own description of the setting, and `YoutubeDLCookieJar.open`), which yt-dlp empties and writes into instead of the file. pyright's yt-dlp stub types the setting `str | None` only, hence a `pyright: ignore`. Measured (tests/test_downloader.py, against the test's own web server): the cookie reaches the server, and the file is byte-for-byte unchanged afterwards.
- **A broken file fails every download**, whatever the link (yt-dlp loads the cookies before the first request). Measured texts: JSON gives "Cookies file must be Netscape formatted, not JSON ..."; a file without the `# Netscape HTTP Cookie File` first line gives "... does not look like a Netscape format cookies file". The app shows its own message for both (pattern "Netscape format").
- Cookies go only to the site they belong to (the standard cookie rules, which yt-dlp's cookie jar follows), so a file with only Reddit's cookies changes nothing for YouTube.

## Reddit
- yt-dlp's Reddit code counts as signed in when the `reddit_session` cookie is there (read in extractor/reddit.py, `_is_logged_in`); it then skips the anonymous session request that Reddit blocks (docs/research/yt-dlp-library.md "Sites").

## YouTube
- yt-dlp's wiki, "Exporting YouTube cookies": "By using your account with yt-dlp, you run the risk of it being banned (temporarily or permanently)." It advises using it only when necessary, or a throwaway account.
- YouTube changes the sign-in cookies of open YouTube tabs often, so the wiki says to export them from a private window and close it straight after.

## Sources
- yt-dlp FAQ: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
- yt-dlp wiki, Extractors, "Exporting YouTube cookies": https://github.com/yt-dlp/yt-dlp/wiki/Extractors
- yt-dlp issue #10927 (Chrome cookies on Windows): https://github.com/yt-dlp/yt-dlp/issues/10927
- Get cookies.txt LOCALLY: https://github.com/kairi003/Get-cookies.txt-LOCALLY
- The installed yt-dlp source, as noted above.
