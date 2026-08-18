// Service worker: receives batches from the content script, de-dupes, and POSTs them
// to the configured ODIN inbound endpoint. State lives in chrome.storage (SW is ephemeral).

const SEEN_CAP = 2000;

async function getConfig() {
  return chrome.storage.local.get({
    odinEndpoint: "http://localhost:8000/api/v1",
    odinToken: "",
    odinEnabled: true,
    odinSent: 0,
    odinSeen: [],
    odinHandle: "",
  });
}

async function flashBadge(text, color) {
  await chrome.action.setBadgeBackgroundColor({ color });
  await chrome.action.setBadgeText({ text });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 2500);
}

async function setStatus(error) {
  await chrome.storage.local.set({ odinLastError: error || "", odinLastAt: Date.now() });
}

async function handleCollect(items) {
  const cfg = await getConfig();
  if (!cfg.odinEnabled) return { skipped: "disabled" };
  if (!cfg.odinToken || !cfg.odinEndpoint) {
    await flashBadge("SET", "#f2c14e");
    await setStatus("Not configured — set the API URL and token in Settings.");
    return { skipped: "unconfigured" };
  }

  const seen = new Set(cfg.odinSeen);
  const fresh = items.filter((it) => it.id && !seen.has(it.id));
  if (fresh.length === 0) return { created: 0 };

  try {
    const res = await fetch(`${cfg.odinEndpoint}/ingest/x`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Ingest-Token": cfg.odinToken },
      body: JSON.stringify({ items: fresh }),
    });
    if (!res.ok) {
      await flashBadge("ERR", "#ff6b5e");
      const msg = res.status === 401 ? "Bad token (401)" : `HTTP ${res.status}`;
      await setStatus(msg);
      console.warn("[ODIN] ingest failed:", msg);
      return { error: msg };
    }
    const body = await res.json();

    for (const it of fresh) seen.add(it.id);
    const seenArr = Array.from(seen).slice(-SEEN_CAP);
    await chrome.storage.local.set({
      odinSeen: seenArr,
      odinSent: (cfg.odinSent || 0) + (body.created || 0),
    });
    await flashBadge(String(body.created || 0), "#37d39b");
    await setStatus("");
    console.debug("[ODIN] ingested:", body);
    return body;
  } catch (err) {
    await flashBadge("ERR", "#ff6b5e");
    await setStatus(String(err));
    console.warn("[ODIN] ingest error:", err);
    return { error: String(err) };
  }
}

async function handleProfile(profile) {
  const cfg = await getConfig();
  if (!cfg.odinEnabled) return { skipped: "disabled" };
  if (!cfg.odinToken || !cfg.odinEndpoint) return { skipped: "unconfigured" };
  try {
    const res = await fetch(`${cfg.odinEndpoint}/ingest/x/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Ingest-Token": cfg.odinToken },
      body: JSON.stringify(profile),
    });
    if (!res.ok) {
      const msg = res.status === 401 ? "Bad token (401)" : `HTTP ${res.status}`;
      await setStatus(msg);
      return { error: msg };
    }
    const body = await res.json();
    if (body.stored) await flashBadge("👤", "#37d39b");
    console.debug("[ODIN] profile snapshot:", body);
    return body;
  } catch (err) {
    await setStatus(String(err));
    console.warn("[ODIN] profile error:", err);
    return { error: String(err) };
  }
}

async function handleStyle(handle, items) {
  const cfg = await getConfig();
  if (!cfg.odinToken || !cfg.odinEndpoint) return { error: "Not configured — set URL + token" };
  try {
    const res = await fetch(`${cfg.odinEndpoint}/ingest/x/style`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Ingest-Token": cfg.odinToken },
      body: JSON.stringify({ handle, items }),
    });
    if (!res.ok) {
      const msg = res.status === 401 ? "Bad token (401)" : `HTTP ${res.status}`;
      await setStatus(msg);
      return { error: msg };
    }
    const body = await res.json();
    await flashBadge(String(body.stored ?? 0), "#f2c14e");
    console.debug("[ODIN] style sample:", body);
    return body;
  } catch (err) {
    await setStatus(String(err));
    return { error: String(err) };
  }
}

// ---- Background metric sampling ----
// Engagement is front-loaded: most of a tweet's reach lands in the first hour, so ODIN
// wants dense samples early. MV3 service workers are ephemeral, so an alarm wakes us up;
// the backend decides whether anything is actually due, and if so we scrape the user's
// profile (reusing an open X tab, or briefly opening a background one) to capture the
// metrics of every recent post at once.
const REFRESH_ALARM = "odin-refresh";
const REFRESH_MINUTES = 5;

function scheduleAlarm() {
  chrome.alarms.create(REFRESH_ALARM, { periodInMinutes: REFRESH_MINUTES });
}
chrome.runtime.onInstalled.addListener(scheduleAlarm);
chrome.runtime.onStartup.addListener(scheduleAlarm);

async function isSampleDue(cfg) {
  if (!cfg.odinToken || !cfg.odinEndpoint) return false;
  try {
    const res = await fetch(`${cfg.odinEndpoint}/ingest/x/watch`, {
      headers: { "X-Ingest-Token": cfg.odinToken },
    });
    if (!res.ok) return false;
    const body = await res.json();
    if (body.due) {
      console.debug(`[ODIN] ${body.items.length} post(s) due for a metric sample`, body.items);
    }
    return !!body.due;
  } catch {
    return false;
  }
}

/** Ask any already-open X tab to re-scan. Returns true if one handled it. */
async function pingOpenTabs() {
  const tabs = await chrome.tabs.query({ url: ["https://x.com/*", "https://twitter.com/*"] });
  let reached = 0;
  for (const tab of tabs) {
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "odin/rescan" });
      reached += 1;
    } catch {
      // no content script there yet — skip
    }
  }
  return reached > 0;
}

/** Last resort: open the user's profile in a background tab, scrape it, close it. */
async function sampleViaBackgroundTab(handle) {
  if (!handle) return;
  const tab = await chrome.tabs.create({
    url: `https://x.com/${handle}`,
    active: false, // never steals focus
  });
  // Give the SPA time to render the timeline, then let the content script report.
  await new Promise((r) => setTimeout(r, 9000));
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "odin/rescan" });
    await new Promise((r) => setTimeout(r, 4000)); // let the debounced flush fire
  } catch {
    /* tab never got a content script */
  }
  try {
    await chrome.tabs.remove(tab.id);
  } catch {
    /* already closed */
  }
  console.debug("[ODIN] sampled metrics via a background tab");
}

// A tweet ODIN has never seen can't be "due" — it isn't in the database yet. So on top of
// the due-based sampling we sweep the profile periodically to DISCOVER new posts.
const DISCOVERY_INTERVAL_MS = 30 * 60 * 1000;

async function isDiscoveryDue() {
  const { odinLastSweep = 0 } = await chrome.storage.local.get(["odinLastSweep"]);
  return Date.now() - odinLastSweep >= DISCOVERY_INTERVAL_MS;
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== REFRESH_ALARM) return;
  const cfg = await getConfig();
  if (!cfg.odinEnabled) return;

  const due = await isSampleDue(cfg);
  const discover = await isDiscoveryDue();
  if (!due && !discover) return; // nothing to do — don't touch X at all

  await chrome.storage.local.set({ odinLastSweep: Date.now() });
  if (await pingOpenTabs()) return;
  await sampleViaBackgroundTab(normalizeHandle(cfg.odinHandle));
});

function normalizeHandle(h) {
  return (h || "").replace(/^@/, "").trim().toLowerCase();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "odin/collect") {
    (async () => {
      const result = await handleCollect(message.items || []);
      sendResponse(result);
    })();
    return true; // async response
  }
  if (message?.type === "odin/sweep") {
    (async () => {
      const cfg = await getConfig();
      await chrome.storage.local.set({ odinLastSweep: Date.now() });
      if (await pingOpenTabs()) {
        sendResponse({ ok: true, via: "open tab" });
        return;
      }
      await sampleViaBackgroundTab(normalizeHandle(cfg.odinHandle));
      sendResponse({ ok: true, via: "background tab" });
    })();
    return true; // async response
  }
  if (message?.type === "odin/style") {
    (async () => {
      const result = await handleStyle(message.handle, message.items || []);
      sendResponse(result);
    })();
    return true; // async response
  }
  if (message?.type === "odin/profile") {
    (async () => {
      const result = await handleProfile(message.profile || {});
      sendResponse(result);
    })();
    return true; // async response
  }
  return false;
});
