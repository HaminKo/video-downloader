// Stands in for Chrome's extension functions when tests/gui/popup.py loads
// extension/popup.html as a plain page in headless Chrome (loaded before
// popup.js). The case comes in the page's query string, as JSON (popup.Case).
// Once the popup has started, the case's clicks are made; at the end, what
// the popup shows and what it did (sent, stored, closed) goes into the
// <html> element's data-seen attribute, as JSON, for the test to read.

"use strict";

const CASE = JSON.parse(decodeURIComponent(location.search.slice(1)));
const did = { sent: [], stored: [], closedAfter: null };
let lastClick = 0;

globalThis.chrome = {
  tabs: {
    query: async () => [{ url: CASE.url ?? undefined }],
  },
  storage: {
    local: {
      // As Chrome's: the kept values, the defaults for those not kept.
      get: async (defaults) => ({ ...defaults, ...(CASE.stored ?? {}) }),
      set: async (items) => {
        did.stored.push(items);
      },
    },
  },
  runtime: {
    sendNativeMessage: async (host, message) => {
      did.sent.push({ host, message });
      await new Promise((done) => setTimeout(done, CASE.reply_after ?? 0));
      if (CASE.error) {
        throw new Error(CASE.error);
      }
      return CASE.reply;
    },
  },
};

// Kept open, so the end can be seen; when, in ms after the last click.
window.close = () => {
  did.closedAfter ??= Math.round(performance.now() - lastClick);
};

function seen() {
  const form = document.getElementById("choices");
  const checked = (name) =>
    form.querySelector(`input[name="${name}"]:checked`)?.value ?? null;
  const status = document.getElementById("status");
  const body = document.body.getBoundingClientRect();
  return {
    kind: checked("kind"),
    quality: checked("quality"),
    subtitles: document.getElementById("subtitles").checked,
    // :disabled, not .disabled: a disabled fieldset's inputs keep
    // .disabled false.
    disabled: [...form.querySelectorAll("input, button")]
      .filter((element) => element.matches(":disabled"))
      .map((element) => element.id),
    focused: document.activeElement?.id ?? "",
    status: status.textContent,
    error: status.classList.contains("error"),
    size: [Math.ceil(body.width), Math.ceil(body.height)],
    ...did,
  };
}

window.addEventListener("load", () => {
  setTimeout(() => {
    for (const selector of CASE.clicks ?? []) {
      lastClick = performance.now();
      document.querySelector(selector).click();
    }
  }, 100);
  setTimeout(() => {
    document.documentElement.dataset.seen = JSON.stringify(seen());
  }, CASE.read_at ?? 2500);
});
