# ODIN X Collector (Chrome extension)

Manifest V3 extension that collects X (Twitter) posts you view and sends them to your ODIN
instance's inbound endpoint (`POST /api/v1/ingest/x`). This avoids the paid X API — you are the
collector, browsing normally.

## How it works

- A **content script** on `x.com` / `twitter.com` reads visible posts from the DOM (best-effort;
  X's markup changes often) and hands batches to the service worker.
- The **service worker** de-dupes by post id and POSTs new posts to your ODIN API with the
  `X-Ingest-Token` header. Items then flow through ODIN's normal clustering/scoring pipeline.
- Nothing is sent until you set an **endpoint + token** in Settings and leave capturing **ON**.

## Setup

1. In the backend `.env`, set a shared token:
   ```
   INGEST_TOKEN=<some-long-random-string>
   ```
   (Restart the API so it picks it up.)
2. Load the extension: `chrome://extensions` → enable **Developer mode** → **Load unpacked** →
   select this `extension/` folder.
3. Open the extension's **Settings** and enter:
   - **API base URL** — e.g. `http://localhost:8000/api/v1` (or `https://odin.iamcanturk.dev/api/v1`)
   - **Ingest token** — the same value as `INGEST_TOKEN`
4. Browse X. The toolbar badge flashes the number of posts accepted; the popup shows the running
   total and a capture ON/OFF toggle.

> If you point the extension at an API origin other than `localhost` or `odin.iamcanturk.dev`, add
> that origin to `host_permissions` in `manifest.json`.

## Privacy

Posts are sent **only** to the API URL you configure, with your token. No third parties. Respect
X's Terms of Service and rate limits — capture is throttled and driven by your own browsing.

## Notes

- Icons are intentionally omitted (Chrome shows a default) to keep the unpacked build dependency-free.
- The DOM selectors (`article[data-testid="tweet"]`, `[data-testid="tweetText"]`, …) may need
  updating when X changes its markup.
