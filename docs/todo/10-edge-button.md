# To do 10: Edge button (large): "Edge button: send the page you're on to the app"

- **Goal:** on a video page in Edge, one click sends the link to the app. Example: on a YouTube video, click the button; the app comes to the front with the link filled in.
- **Read first:** docs/research/prior-art.md "Browser extensions" (general knowledge, not checked: research it first); `start()` and `main()` in app.py.
- **Approach:** a small extension loaded unpacked in Edge, plus native messaging (a JSON manifest and a registry key under `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\`) that starts a small script; the script hands the link to the running app (which needs a way to receive it, e.g. a local socket) or starts it. Research first, then a step plan in docs/todo/10-edge-button.md.
- **Ask the user:** (a) start downloading right away, or only fill in the link? Suggested: fill it in and bring the window to the front, so you still choose MP4 or MP3. (b) after the queue (To do 9), so a link sent during a download isn't lost? Suggested: yes, that's why it comes after it.
- **Test:** Claude: tests for the link hand-over without a browser. User: load the extension, click it on a YouTube page.
