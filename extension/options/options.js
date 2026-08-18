const endpointEl = document.getElementById("endpoint");
const tokenEl = document.getElementById("token");
const handleEl = document.getElementById("handle");
const statusEl = document.getElementById("status");

async function load() {
  const cfg = await chrome.storage.local.get({
    odinEndpoint: "http://localhost:8000/api/v1",
    odinToken: "",
    odinHandle: "",
  });
  endpointEl.value = cfg.odinEndpoint;
  tokenEl.value = cfg.odinToken;
  handleEl.value = cfg.odinHandle;
}

async function save() {
  const odinEndpoint = endpointEl.value.trim().replace(/\/$/, "");
  const odinToken = tokenEl.value.trim();
  const odinHandle = handleEl.value.trim();
  await chrome.storage.local.set({ odinEndpoint, odinToken, odinHandle });
  statusEl.textContent = "Saved.";
  setTimeout(() => (statusEl.textContent = ""), 1500);
}

document.getElementById("save").addEventListener("click", save);
load();
