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

// ---- Background refresh ----
// MV3 service workers are ephemeral, so a periodic alarm wakes us up. We can't scrape X
// without a tab, but any OPEN x.com tab (even a background one) can be asked to re-scan,
// which refreshes your own posts' metrics and profile stats without you doing anything.
const REFRESH_ALARM = "odin-refresh";
const REFRESH_MINUTES = 30;

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(REFRESH_ALARM, { periodInMinutes: REFRESH_MINUTES });
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(REFRESH_ALARM, { periodInMinutes: REFRESH_MINUTES });
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== REFRESH_ALARM) return;
  const { odinEnabled = true } = await chrome.storage.local.get(["odinEnabled"]);
  if (!odinEnabled) return;
  const tabs = await chrome.tabs.query({ url: ["https://x.com/*", "https://twitter.com/*"] });
  for (const tab of tabs) {
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "odin/rescan" });
    } catch {
      // no content script in that tab (still loading) — skip it
    }
  }
  console.debug(`[ODIN] background refresh pinged ${tabs.length} X tab(s)`);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "odin/collect") {
    (async () => {
      const result = await handleCollect(message.items || []);
      sendResponse(result);
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
