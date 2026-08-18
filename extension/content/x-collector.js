// Content script: best-effort scrape of visible X posts, forwarded to the service worker.
// X's DOM is obfuscated and changes often — selectors are defensive and may need updates.

const SEND_DEBOUNCE_MS = 2500;
const buffer = new Map(); // id -> item
let sendTimer = null;

// When the extension is reloaded/updated, this script keeps running on the page but its
// chrome.* bridge is dead ("Extension context invalidated"). Detect that and stand down
// instead of throwing on every mutation.
let contextAlive = true;

function extAlive() {
  if (!contextAlive) return false;
  try {
    if (!chrome.runtime?.id) contextAlive = false;
  } catch {
    contextAlive = false;
  }
  if (!contextAlive) shutdown();
  return contextAlive;
}

function shutdown() {
  try {
    observer?.disconnect();
  } catch {
    /* observer may not exist yet */
  }
  document.getElementById(BTN_ID)?.remove();
  console.debug("[ODIN] extension context gone — content script standing down (reload the page)");
}

function text(el) {
  return el ? el.innerText.trim() : null;
}

// Magnitude suffixes differ by X's UI language, and so do the separators:
//   English "1,234" = 1234, "1.2K" = 1200
//   Turkish "1.234" = 1234, "1,2 B" = 1200   (B = bin, Mn = milyon)
// Getting this wrong is silent and severe: the old parser read Turkish "1,2 B" as 12
// and "1.234" as 1 (parseFloat("1.234")).
const MULTIPLIERS_EN = { K: 1e3, M: 1e6, B: 1e9, G: 1e9 };
const MULTIPLIERS_TR = { B: 1e3, BIN: 1e3, K: 1e3, MN: 1e6, M: 1e6, MR: 1e9 };

function isTurkishUI() {
  return (document.documentElement.lang || "").toLowerCase().startsWith("tr");
}

function parseCount(label, { turkish = isTurkishUI() } = {}) {
  if (!label) return null;
  const s = String(label).replace(/\u00a0/g, " ").trim();
  const m = s.match(/(\d[\d.,]*)\s*(Bin|Mn|Mr|B|K|M|G)?/i);
  if (!m) return null;

  let digits = m[1];
  if (turkish) {
    digits = digits.replace(/\./g, "").replace(",", "."); // 1.234 -> 1234 ; 1,2 -> 1.2
  } else {
    digits = digits.replace(/,/g, ""); // 1,234 -> 1234 ; 1.2 stays 1.2
  }
  const n = parseFloat(digits);
  if (!Number.isFinite(n)) return null;

  const suffix = (m[2] || "").toUpperCase();
  const mult = (turkish ? MULTIPLIERS_TR : MULTIPLIERS_EN)[suffix] || 1;
  return Math.round(n * mult);
}

function metricFor(article, testid) {
  const el = article.querySelector(`[data-testid="${testid}"]`);
  return el ? parseCount(el.getAttribute("aria-label")) : null;
}

// "Views" has no stable data-testid, so try the analytics link first and fall back to
// any aria-label that mentions views in either language.
const VIEWS_LABEL_RE = /(views?|görüntülenme|gösterim|izlenme)/i;

function viewsFor(article) {
  const a = article.querySelector('a[href*="/analytics"]');
  if (a) {
    const v = parseCount(a.getAttribute("aria-label")) ?? parseCount(a.textContent);
    if (v != null) return v;
  }
  for (const el of article.querySelectorAll("[aria-label]")) {
    const label = el.getAttribute("aria-label") || "";
    if (VIEWS_LABEL_RE.test(label)) {
      const v = parseCount(label);
      if (v != null) return v;
    }
  }
  return null;
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
  if (!extAlive()) return;
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
  if (!handle || !extAlive()) return;
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
  if (!extAlive()) return;
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
  if (!handle) return { error: "Profil sayfası değil" };
  if (!extAlive()) return { error: "Uzantı yeniden yüklendi — sayfayı yenile" };

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
// Injected into X's own profile action bar (next to Message / Follow) by CLONING one of
// their buttons, so it inherits their exact classes and looks native even when X changes
// its CSS. Falls back to a floating button if the action bar can't be found.

const BTN_ID = "odin-style-btn";
const TOAST_ID = "odin-toast";
const SVG_NS = "http://www.w3.org/2000/svg";
// Sparkles — reads as "learn / infer style".
const ICON_PATH =
  "M11 2l1.5 4.2L17 8l-4.5 1.8L11 14 9.5 9.8 5 8l4.5-1.8L11 2z" +
  "M18.5 12l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z" +
  "M6 15.5l.6 1.7 1.9.8-1.9.8L6 20.5l-.6-1.7-1.9-.8 1.9-.8.6-1.7z";

const COLORS = { idle: "", busy: "#f2c14e", ok: "#3dd4a0", err: "#ff6b5e" };

function showToast(msg, color) {
  let el = document.getElementById(TOAST_ID);
  if (!el) {
    el = document.createElement("div");
    el.id = TOAST_ID;
    el.style.cssText = [
      "position:fixed", "right:20px", "bottom:20px", "z-index:2147483647",
      "padding:10px 14px", "border-radius:10px", "border:1px solid",
      "background:#0d1017", "font:500 13px system-ui,sans-serif",
      "box-shadow:0 6px 24px rgba(0,0,0,.45)", "pointer-events:none",
      "transition:opacity .2s", "max-width:320px",
    ].join(";");
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.color = color;
  el.style.borderColor = color;
  el.style.opacity = "1";
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.style.opacity = "0"), 4000);
}

function paintButton(btn, color) {
  // Recolor the icon only; everything else stays X's own styling.
  for (const el of btn.querySelectorAll("svg, div")) {
    if (color) el.style.color = color;
    else el.style.removeProperty("color");
  }
}

/** The profile action bar + a button to clone for styling. */
function findActionBar() {
  for (const sel of ['[data-testid="sendDMFromProfile"]', '[data-testid="userActions"]']) {
    const el = document.querySelector(sel);
    if (el?.parentElement) return { bar: el.parentElement, template: el, anchor: el };
  }
  return null;
}

function buildNativeButton(template, handle) {
  const btn = template.cloneNode(true);
  btn.id = BTN_ID;
  btn.dataset.handle = handle;
  // Strip the cloned button's identity so X's own handlers/tests never match it.
  for (const attr of ["data-testid", "aria-haspopup", "aria-expanded", "aria-describedby"]) {
    btn.removeAttribute(attr);
  }
  const label = `ODIN: @${handle} tarzını öğren`;
  btn.setAttribute("aria-label", label);
  btn.setAttribute("title", label);

  // Replace the icon. Build the SVG with DOM APIs — X sets a strict CSP/Trusted Types
  // policy, so assigning innerHTML here would be blocked.
  const svg = btn.querySelector("svg");
  if (svg) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const g = document.createElementNS(SVG_NS, "g");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", ICON_PATH);
    g.appendChild(path);
    svg.appendChild(g);
  }
  // Drop any text label if we cloned a button that had one.
  for (const span of btn.querySelectorAll("span")) {
    if (span.textContent.trim()) span.textContent = "";
  }
  return btn;
}

function buildFloatingButton(handle) {
  const btn = document.createElement("button");
  btn.id = BTN_ID;
  btn.dataset.handle = handle;
  btn.textContent = `ODIN: @${handle} tarzını öğren`;
  btn.style.cssText = [
    "position:fixed", "right:20px", "bottom:20px", "z-index:2147483646",
    "padding:10px 14px", "border-radius:10px", "border:1px solid #5aa2ff",
    "background:#0d1017", "color:#5aa2ff", "font:500 13px system-ui,sans-serif",
    "cursor:pointer", "box-shadow:0 6px 24px rgba(0,0,0,.45)",
  ].join(";");
  return btn;
}

async function onStyleClick(btn) {
  if (btn.dataset.busy === "1") return;
  btn.dataset.busy = "1";
  paintButton(btn, COLORS.busy);
  showToast("Tweetler taranıyor…", COLORS.busy);
  try {
    const res = await sampleStyle({
      onProgress: (n) => showToast(`Taranıyor… ${n} tweet`, COLORS.busy),
    });
    if (!res || res.error) throw new Error(res?.error || "Bilinmeyen hata");
    paintButton(btn, COLORS.ok);
    showToast(`✓ @${btn.dataset.handle}: ${res.stored} yeni örnek alındı`, COLORS.ok);
  } catch (err) {
    paintButton(btn, COLORS.err);
    showToast(`✕ ${err.message || err}`, COLORS.err);
  } finally {
    setTimeout(() => {
      paintButton(btn, COLORS.idle);
      btn.dataset.busy = "0";
    }, 3000);
  }
}

function ensureStyleButton() {
  const handle = currentHandle();
  const existing = document.getElementById(BTN_ID);

  if (!handle) {
    existing?.remove();
    return;
  }
  // Still mounted and pointing at the right profile? Nothing to do.
  if (existing?.isConnected && existing.dataset.handle === handle) return;
  existing?.remove();

  const spot = findActionBar();
  const btn = spot ? buildNativeButton(spot.template, handle) : buildFloatingButton(handle);
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    onStyleClick(btn);
  });

  if (spot) spot.anchor.insertAdjacentElement("afterend", btn);
  else document.body.appendChild(btn);
}

// The popup can close mid-request, which closes the message channel; guard every reply.
function safeRespond(sendResponse, payload) {
  try {
    sendResponse(payload);
  } catch {
    /* channel already closed (popup dismissed) — the work still completed */
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "odin/rescan") {
    lastProfileKey = null; // force a fresh profile snapshot even if the DOM is unchanged
    scan();
    safeRespond(sendResponse, { ok: true, buffered: buffer.size });
    return false; // responded synchronously
  }
  if (message?.type === "odin/sample-style") {
    sampleStyle()
      .then((r) => safeRespond(sendResponse, r))
      .catch((e) => safeRespond(sendResponse, { error: String(e?.message || e) }));
    return true; // async response
  }
  return false;
});

// Observe timeline mutations (new tweets as you scroll) + an initial scan.
const observer = new MutationObserver(() => scan());
observer.observe(document.body, { childList: true, subtree: true });
scan();
