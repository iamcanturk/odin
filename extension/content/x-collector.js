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
  if (!odinEnabled || buffer.size === 0) {
    buffer.clear();
    return;
  }
  // Mark the user's own posts (matched by handle) so the backend imports them for
  // style + personal-performance analysis.
  const me = normHandle(odinHandle);
  const items = Array.from(buffer.values()).map((it) => ({
    ...it,
    is_self: !!me && normHandle(it.author_handle) === me,
  }));
  buffer.clear();
  try {
    const res = await chrome.runtime.sendMessage({ type: "odin/collect", items });
    console.debug(`[ODIN] handed off ${items.length} post(s) →`, res);
  } catch (err) {
    console.warn("[ODIN] failed to hand off batch:", err);
  }
}

// Observe timeline mutations (new tweets as you scroll) + an initial scan.
const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
scan();
