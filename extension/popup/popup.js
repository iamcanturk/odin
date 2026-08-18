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

document.getElementById("open-options").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

render();
