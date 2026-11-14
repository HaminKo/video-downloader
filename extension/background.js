// The toolbar button: a click sends the tab's link to the app's helper on
// this PC (native messaging), which hands it to the app's window or opens
// one. A "!" on the button means it didn't work; its tooltip says why. The
// next click that works takes the "!" away.

const HOST = "video_downloader";
const TITLE = "Send this page to Video Downloader";
const NOT_INSTALLED =
  "The helper isn't installed: run python -m video_downloader.browser install.";

chrome.action.onClicked.addListener(async (tab) => {
  let problem = "";
  try {
    const reply = await chrome.runtime.sendNativeMessage(HOST, {
      link: tab.url ?? "",
    });
    if (!reply?.ok) {
      problem = reply?.error ?? "The helper gave no answer.";
    }
  } catch (error) {
    // Chrome: "Specified native messaging host not found."
    problem = /not found/i.test(error.message) ? NOT_INSTALLED : error.message;
  }
  await chrome.action.setBadgeBackgroundColor({ color: "#a00000" });
  await chrome.action.setBadgeText({ text: problem ? "!" : "" });
  await chrome.action.setTitle({
    title: problem ? `Video Downloader didn't get the link. ${problem}` : TITLE,
  });
});
