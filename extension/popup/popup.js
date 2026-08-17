const toggleBtn = document.getElementById("toggle");
const sentEl = document.getElementById("sent");

async function render() {
  const { odinEnabled = true, odinSent = 0 } = await chrome.storage.local.get({
    odinEnabled: true,
    odinSent: 0,
  });
  toggleBtn.textContent = odinEnabled ? "ON" : "OFF";
  toggleBtn.classList.toggle("on", odinEnabled);
  sentEl.textContent = String(odinSent);
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
