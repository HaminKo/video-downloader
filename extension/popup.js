// The toolbar button's popup: the window's choices (MP4 or MP3, the video's
// quality, English subtitles) and Download, which sends the tab's link with
// them to the app's helper on this PC (native messaging, host.py); the app
// adds it to its list and downloads it. "Open in the window instead" sends
// the link alone, which goes into the window's link box. "Cancel this page's
// download" asks the open window to stop the tab's link (or not start it),
// and says whether it did. The popup keeps its own last choices
// (chrome.storage.local), apart from the window's.
//
// Tested in headless Chrome with Chrome's functions faked:
// tests/gui/popup_gui.py.

"use strict";

const HOST = "video_downloader";
const NOT_A_WEB_PAGE = "Only web pages can be sent.";
const NOT_INSTALLED =
  "The helper isn't installed: run Video Downloader Setup again " +
  "(from the project: python -m video_downloader.browser install).";
const NO_ANSWER = "The helper gave no answer.";
const SENDING = "Sending...";
const ADDED = "Added to Video Downloader.";
const CANCELLED = "Cancelled.";

// How long "Added" or "Cancelled" shows before the popup closes, in
// milliseconds.
const CLOSE_AFTER = 1500;

// The choices until some are kept: the window's own when it opens.
const DEFAULTS = { kind: "mp4", quality: "Best", subtitles: false };

const form = document.getElementById("choices");
const video = document.getElementById("video"); // the quality and subtitles
const download = document.getElementById("download");
const openWindow = document.getElementById("open");
const cancel = document.getElementById("cancel");
const status = document.getElementById("status");

// The tab's link; "" until it is known, or when Chrome gives none.
let link = "";

function choices() {
  return {
    kind: form.elements.kind.value,
    quality: form.elements.quality.value,
    subtitles: form.elements.subtitles.checked,
  };
}

// Kept choices that aren't (or no longer are) one of the popup's leave the
// default in place: a radio button's value is only set if one has it.
function showChoices(kept) {
  form.elements.kind.value = kept.kind;
  form.elements.quality.value = kept.quality;
  form.elements.subtitles.checked = kept.subtitles === true;
  greyOut();
}

// The quality and subtitles are for MP4 only, as in the window.
function greyOut() {
  video.disabled = form.elements.kind.value !== "mp4";
}

function say(text, isError = false) {
  status.textContent = text;
  status.classList.toggle("error", isError);
}

function canSend(yes) {
  for (const button of [download, openWindow, cancel]) {
    button.disabled = !yes;
  }
}

// The same check as the helper's (host.web_link), so the popup can say it
// at once; the helper still checks.
function isWebPage(url) {
  return /^https?:\/\//i.test(url.trim());
}

// "" when the helper took the link, else why not.
async function problemSending(message) {
  try {
    const reply = await chrome.runtime.sendNativeMessage(HOST, message);
    return reply?.ok ? "" : (reply?.error ?? NO_ANSWER);
  } catch (error) {
    // Chrome: "Specified native messaging host not found."
    return /not found/i.test(error.message) ? NOT_INSTALLED : error.message;
  }
}

// Send the message to the helper with the button that was used. Once the
// helper took it, the popup says `done` and closes after CLOSE_AFTER, or
// with `done` null closes at once. It closes only after the helper's answer:
// closing it would end this script, and with it the message.
async function send(message, button, done) {
  canSend(false); // at once, so a double click sends once
  say(SENDING);
  const problem = await problemSending(message);
  if (problem) {
    say(problem, true);
    canSend(true);
    // Greying it out took the focus: Enter tries the same again (after a
    // failed Cancel, Enter mustn't download).
    button.focus();
  } else if (done) {
    say(done);
    setTimeout(() => window.close(), CLOSE_AFTER);
  } else {
    window.close();
  }
}

form.addEventListener("change", () => {
  greyOut();
  chrome.storage.local.set(choices());
});

form.addEventListener("submit", (event) => {
  event.preventDefault(); // Download, or Enter
  send({ link, start: choices() }, download, ADDED);
});

// The link alone: the window comes to the front with it in its box.
openWindow.addEventListener("click", () => send({ link }, openWindow, null));

cancel.addEventListener("click", () =>
  send({ link, cancel: true }, cancel, CANCELLED),
);

async function start() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  link = tab?.url ?? ""; // none on New Tab and Chrome's own pages
  showChoices(await chrome.storage.local.get(DEFAULTS));
  if (isWebPage(link)) {
    canSend(true);
    download.focus();
  } else {
    say(NOT_A_WEB_PAGE, true);
  }
}

start().catch((error) => say(error.message, true));
