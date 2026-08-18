// Content script: best-effort scrape of visible X posts, forwarded to the service worker.
// X's DOM is obfuscated and changes often — selectors are defensive and may need updates.

const SEND_DEBOUNCE_MS = 2500;
const buffer = new Map(); // id -> item
let sendTimer = null;

function text(el) {
  return el ? el.innerText.trim() : null;
}

function parseCount(label) {
  // aria-labels look like "12 Likes". Extract the leading number.
  if (!label) return null;
  const m = label.replace(/,/g, "").match(/(\d+(?:\.\d+)?)([KM]?)/);
  if (!m) return null;
  let n = parseFloat(m[1]);
  if (m[2] === "K") n *= 1_000;
  if (m[2] === "M") n *= 1_000_000;
  return Math.round(n);
}

function metricFor(article, testid) {
  const el = article.querySelector(`[data-testid="${testid}"]`);
  return el ? parseCount(el.getAttribute("aria-label")) : null;
}

function viewsFor(article) {
  // View count sits behind the analytics link in the action bar (best-effort).
  const a = article.querySelector('a[href$="/analytics"]');
  if (!a) return null;
  return parseCount(a.getAttribute("aria-label")) ?? parseCount(a.textContent);
}

function extractTweet(article) {
  const link = article.querySelector('a[href*="/status/"]');
  const href = link ? link.getAttribute("href") : null;
  const idMatch = href ? href.match(/\/status\/(\d+)/) : null;
  if (!idMatch) return null;
  const id = idMatch[1];

  const body = text(article.querySelector('[data-testid="tweetText"]'));
  if (!body) return null;

  const timeEl = article.querySelector("time");
  const nameBlock = article.querySelector('[data-testid="User-Name"]');
  const handleLink = nameBlock
    ? nameBlock.querySelector('a[href^="/"]:not([href*="/status/"])')
    : null;
  const handle = handleLink ? `@${handleLink.getAttribute("href").replace(/^\//, "")}` : null;

  return {
    id,
    text: body,
    author_handle: handle,
    url: href ? `https://x.com${href}` : null,
    created_at: timeEl ? timeEl.getAttribute("datetime") : null,
    lang: document.documentElement.lang || null,
    metrics: {
      likes: metricFor(article, "like"),
      replies: metricFor(article, "reply"),
      reposts: metricFor(article, "retweet"),
      bookmarks: metricFor(article, "bookmark"),
      impressions: viewsFor(article),
    },
  };
}

function scan() {
  // Prefer the stable testid; fall back to role if X changes markup.
  let articles = document.querySelectorAll('article[data-testid="tweet"]');
  if (articles.length === 0) articles = document.querySelectorAll('article[role="article"]');
  let added = 0;
  for (const article of articles) {
    const item = extractTweet(article);
    if (item && !buffer.has(item.id)) {
      buffer.set(item.id, item);
      added += 1;
    }
  }
  if (added > 0) console.debug(`[ODIN] captured ${added} post(s), buffer=${buffer.size}`);
  scheduleSend();
  scanProfile();
  ensureStyleButton();
}

// ---- Profile stats capture (PROJECT.md §12: follower/following over time) ----

const RESERVED_PATHS = new Set([
  "home", "explore", "notifications", "messages", "search", "settings",
  "i", "compose", "bookmarks", "hashtag", "lists", "communities", "jobs",
]);

let lastProfileKey = null;

function currentHandle() {
  const seg = location.pathname.split("/").filter(Boolean);
  if (seg.length !== 1) return null; // profile pages are single-segment (x.com/<handle>)
  const h = seg[0].toLowerCase();
  return RESERVED_PATHS.has(h) ? null : h;
}

function statCount(handle, suffix) {
  // Header stat anchors: /<handle>/following and /<handle>/verified_followers (or /followers).
  const sel = suffix
    .map((s) => `a[href="/${handle}/${s}"]`)
    .join(",");
  const el = document.querySelector(sel);
  if (!el) return null;
  // Prefer an exact value in a title attribute (X abbreviates the visible text at scale).
  const titled = el.querySelector("[title]");
  const raw = (titled && titled.getAttribute("title")) || el.textContent || "";
  return parseCount(raw);
}

function tweetCount() {
  const header = document.querySelector('[data-testid="primaryColumn"]');
  if (!header) return null;
  for (const el of header.querySelectorAll('div[dir="ltr"], h2 ~ div, span')) {
    const m = (el.textContent || "").trim().match(/^([\d.,]+\s*[KMB]?)\s+(posts|gönderi|tweets)/i);
    if (m) return parseCount(m[1]);
  }
  return null;
}

async function scanProfile() {
  const handle = currentHandle();
  if (!handle) return;
  const { odinEnabled = true, odinHandle = "" } = await chrome.storage.local.get([
    "odinEnabled",
    "odinHandle",
  ]);
  // Only track the user's own profile (matches the is_self handle in Settings).
  if (!odinEnabled || !odinHandle || normHandle(odinHandle) !== handle) return;

  const followers = statCount(handle, ["verified_followers", "followers"]);
  const following = statCount(handle, ["following"]);
  const tweets = tweetCount();
  if (followers == null && following == null) return;

  const key = `${handle}:${followers}:${following}:${tweets}`;
  if (key === lastProfileKey) return; // don't re-send identical stats within a page view
  lastProfileKey = key;

  try {
    const res = await chrome.runtime.sendMessage({
      type: "odin/profile",
      profile: { handle, followers, following, tweets },
    });
    console.debug("[ODIN] profile stats →", res);
  } catch (err) {
    console.warn("[ODIN] failed to hand off profile stats:", err);
  }
}

function scheduleSend() {
  if (sendTimer || buffer.size === 0) return;
  sendTimer = setTimeout(flush, SEND_DEBOUNCE_MS);
}

function normHandle(h) {
  return (h || "").replace(/^@/, "").toLowerCase();
}

async function flush() {
  sendTimer = null;
  const { odinEnabled = true, odinHandle = "" } = await chrome.storage.local.get([
    "odinEnabled",
    "odinHandle",
  ]);
  const me = normHandle(odinHandle);
  if (!odinEnabled || !me || buffer.size === 0) {
    if (!me && buffer.size > 0) {
      console.debug("[ODIN] set your handle in Settings to capture your own posts");
    }
    buffer.clear();
    return;
  }
  // X is output-only: we only send the user's OWN posts (matched by handle) so the
  // backend can import them for style + personal-performance analysis. Everyone else's
  // tweets are ignored — ODIN pulls event content from other sources.
  const items = Array.from(buffer.values())
    .filter((it) => normHandle(it.author_handle) === me)
    .map((it) => ({ ...it, is_self: true }));
  buffer.clear();
  if (items.length === 0) return;
  try {
    const res = await chrome.runtime.sendMessage({ type: "odin/collect", items });
    console.debug(`[ODIN] handed off ${items.length} own post(s) →`, res);
  } catch (err) {
    console.warn("[ODIN] failed to hand off batch:", err);
  }
}

// ---- Style sampling ----
// Collect the tweets of the profile you're viewing, keep the ones that ACTUALLY PERFORMED,
// and send them as STYLE REFERENCES so ODIN writes new posts inspired by that style.

const SAMPLE_SCROLL_ROUNDS = 6;
const SAMPLE_SCROLL_WAIT_MS = 900;
const SAMPLE_KEEP_TOP = 25;

function engagementOf(item) {
  const m = item.metrics || {};
  // Weight the signals X itself rewards most: reposts/replies over raw likes.
  return (m.likes || 0) + 3 * (m.reposts || 0) + 2 * (m.replies || 0) + (m.bookmarks || 0);
}

function collectAuthorTweets(handle, into) {
  let articles = document.querySelectorAll('article[data-testid="tweet"]');
  if (articles.length === 0) articles = document.querySelectorAll('article[role="article"]');
  for (const article of articles) {
    const item = extractTweet(article);
    // Only that account's own tweets (skip retweets/replies from others in the timeline).
    if (item && normHandle(item.author_handle) === handle) into.set(item.id, item);
  }
}

async function sampleStyle({ onProgress } = {}) {
  const handle = currentHandle();
  if (!handle) return { error: "Open a profile page (x.com/<handle>)" };

  // Auto-scroll so we see a real sample, not just the 3 tweets above the fold.
  const found = new Map();
  const startY = window.scrollY;
  for (let round = 0; round < SAMPLE_SCROLL_ROUNDS; round++) {
    collectAuthorTweets(handle, found);
    onProgress?.(found.size);
    const before = found.size;
    window.scrollBy(0, window.innerHeight * 1.5);
    await new Promise((r) => setTimeout(r, SAMPLE_SCROLL_WAIT_MS));
    collectAuthorTweets(handle, found);
    // Stop early if scrolling stopped yielding anything new.
    if (found.size === before && round > 1) break;
  }
  window.scrollTo(0, startY);

  if (found.size === 0) return { error: "No tweets found — is this a profile page?" };

  // Keep the best performers: those are the ones worth being inspired by.
  const ranked = Array.from(found.values()).sort((a, b) => engagementOf(b) - engagementOf(a));
  const items = ranked.slice(0, SAMPLE_KEEP_TOP);
  console.debug(`[ODIN] sampled ${found.size} tweets from @${handle}, sending top ${items.length}`);

  return chrome.runtime.sendMessage({ type: "odin/style", handle, items });
}

// ---- In-page button ----
// A floating "learn this style" button that appears on any profile page.

const BTN_ID = "odin-style-btn";

function toast(el, msg, color) {
  el.textContent = msg;
  el.style.borderColor = color;
  el.style.color = color;
}

function ensureStyleButton() {
  const handle = currentHandle();
  const existing = document.getElementById(BTN_ID);

  if (!handle) {
    existing?.remove();
    return;
  }
  if (existing) {
    if (existing.dataset.handle !== handle) {
      existing.dataset.handle = handle;
      toast(existing, `ODIN: @${handle} tarzını öğren`, "#5aa2ff");
    }
    return;
  }

  const btn = document.createElement("button");
  btn.id = BTN_ID;
  btn.dataset.handle = handle;
  btn.textContent = `ODIN: @${handle} tarzını öğren`;
  btn.style.cssText = [
    "position:fixed", "right:20px", "bottom:20px", "z-index:99999",
    "padding:10px 14px", "border-radius:10px", "border:1px solid #5aa2ff",
    "background:#0d1017", "color:#5aa2ff", "font:500 13px system-ui,sans-serif",
    "cursor:pointer", "box-shadow:0 6px 24px rgba(0,0,0,.45)",
  ].join(";");

  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    const original = `ODIN: @${btn.dataset.handle} tarzını öğren`;
    toast(btn, "Tweetler taranıyor…", "#f2c14e");
    try {
      const res = await sampleStyle({
        onProgress: (n) => toast(btn, `Taranıyor… ${n} tweet`, "#f2c14e"),
      });
      if (res?.error) throw new Error(res.error);
      toast(btn, `✓ ${res.stored} yeni örnek alındı`, "#3dd4a0");
    } catch (err) {
      toast(btn, `✕ ${err.message || err}`, "#ff6b5e");
    } finally {
      setTimeout(() => {
        toast(btn, original, "#5aa2ff");
        btn.disabled = false;
      }, 3500);
    }
  });

  document.body.appendChild(btn);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "odin/rescan") {
    lastProfileKey = null; // force a fresh profile snapshot even if the DOM is unchanged
    scan();
    sendResponse({ ok: true, buffered: buffer.size });
    return true;
  }
  if (message?.type === "odin/sample-style") {
    sampleStyle().then(sendResponse);
    return true; // async response
  }
  return false;
});

// Observe timeline mutations (new tweets as you scroll) + an initial scan.
const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
scan();
