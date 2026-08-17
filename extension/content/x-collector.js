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
  const articles = document.querySelectorAll('article[data-testid="tweet"]');
  for (const article of articles) {
    const item = extractTweet(article);
    if (item && !buffer.has(item.id)) buffer.set(item.id, item);
  }
  scheduleSend();
}

function scheduleSend() {
  if (sendTimer || buffer.size === 0) return;
  sendTimer = setTimeout(flush, SEND_DEBOUNCE_MS);
}

async function flush() {
  sendTimer = null;
  const { odinEnabled = true } = await chrome.storage.local.get("odinEnabled");
  if (!odinEnabled || buffer.size === 0) {
    buffer.clear();
    return;
  }
  const items = Array.from(buffer.values());
  buffer.clear();
  try {
    await chrome.runtime.sendMessage({ type: "odin/collect", items });
  } catch (err) {
    console.warn("[ODIN] failed to hand off batch:", err);
  }
}

// Observe timeline mutations (new tweets as you scroll) + an initial scan.
const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
scan();
