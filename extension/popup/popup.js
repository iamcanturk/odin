const toggleBtn = document.getElementById("toggle");
const sentEl = document.getElementById("sent");
const statusEl = document.getElementById("status");

async function render() {
  const { odinEnabled = true, odinSent = 0, odinLastError = "" } = await chrome.storage.local.get({
    odinEnabled: true,
    odinSent: 0,
    odinLastError: "",
  });
  toggleBtn.textContent = odinEnabled ? "ON" : "OFF";
  toggleBtn.classList.toggle("on", odinEnabled);
  sentEl.textContent = String(odinSent);
  if (statusEl) {
    statusEl.textContent = odinLastError || "OK";
    statusEl.style.color = odinLastError ? "#ff6b5e" : "#37d39b";
  }
}

toggleBtn.addEventListener("click", async () => {
  const { odinEnabled = true } = await chrome.storage.local.get("odinEnabled");
  await chrome.storage.local.set({ odinEnabled: !odinEnabled });
  await render();
});

const syncBtn = document.getElementById("sync-now");
const syncResult = document.getElementById("sync-result");

syncBtn?.addEventListener("click", async () => {
  syncBtn.disabled = true;
  syncResult.textContent = "Çekiliyor…";
  syncResult.style.color = "#8b93a3";
  try {
    const res = await chrome.runtime.sendMessage({ type: "odin/sweep" });
    if (res?.error) throw new Error(res.error);
    syncResult.textContent = `Tamam (${res.via})`;
    syncResult.style.color = "#3dd4a0";
    await render();
  } catch (err) {
    syncResult.textContent = String(err.message || err);
    syncResult.style.color = "#ff6b5e";
  } finally {
    syncBtn.disabled = false;
  }
});

// "Take style sample": ask the active X profile tab to collect that account's visible
// tweets and send them as STYLE REFERENCES (not events, not your own posts).
const sampleBtn = document.getElementById("sample-style");
const sampleResult = document.getElementById("sample-result");

sampleBtn?.addEventListener("click", async () => {
  sampleBtn.disabled = true;
  sampleResult.textContent = "Sampling…";
  sampleResult.style.color = "#8b93a3";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !/^https:\/\/(x|twitter)\.com\//.test(tab.url || "")) {
      throw new Error("Open an X profile first");
    }
    const res = await chrome.tabs.sendMessage(tab.id, { type: "odin/sample-style" });
    if (res?.error) throw new Error(res.error);
    sampleResult.textContent = `@${res.handle}: ${res.stored} new / ${res.received} seen`;
    sampleResult.style.color = "#37d39b";
  } catch (err) {
    sampleResult.textContent = String(err.message || err);
    sampleResult.style.color = "#ff6b5e";
  } finally {
    sampleBtn.disabled = false;
  }
});

document.getElementById("open-options").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

render();
