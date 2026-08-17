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

async function handleCollect(items) {
  const cfg = await getConfig();
  if (!cfg.odinEnabled) return { skipped: "disabled" };
  if (!cfg.odinToken || !cfg.odinEndpoint) {
    await flashBadge("SET", "#f2c14e");
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
      return { error: `HTTP ${res.status}` };
    }
    const body = await res.json();

    // Update the capped seen-list and counters.
    for (const it of fresh) seen.add(it.id);
    const seenArr = Array.from(seen).slice(-SEEN_CAP);
    await chrome.storage.local.set({
      odinSeen: seenArr,
      odinSent: (cfg.odinSent || 0) + (body.created || 0),
    });
    await flashBadge(String(body.created || 0), "#37d39b");
    return body;
  } catch (err) {
    await flashBadge("ERR", "#ff6b5e");
    return { error: String(err) };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "odin/collect") {
    (async () => {
      const result = await handleCollect(message.items || []);
      sendResponse(result);
    })();
    return true; // async response
  }
  return false;
});
