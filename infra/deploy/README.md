# ODIN — Production Deploy (CloudPanel, `odin.iamcanturk.dev`)

Single domain: `/` → Next.js, `/api/*` → FastAPI (reverse proxy). Postgres+pgvector and
Redis run in Docker (localhost-only); API, worker and web run natively via systemd behind
CloudPanel's nginx.

> **Roles:** Claude prepared these files. You run the privileged steps (Docker, systemd,
> CloudPanel vhost, editing `.env`) — they need `sudo` and secrets.

**Disk footprint:** ~1.5 GB (hash embeddings) to ~3.5 GB (local e5 + torch) — well under 10 GB.

---

## 0. Pre-flight — check what's installed

Run on the server and note the results:

```bash
docker --version && docker compose version   # need Docker + compose plugin
redis-cli --version 2>/dev/null || echo "redis client not installed (fine if using Docker redis)"
python3 --version                              # informational; uv manages Python
node --version                                 # need Node 20+
pnpm --version || echo "pnpm missing"
which uv || echo "uv missing"
df -h /                                         # confirm >5 GB free
```

Install anything missing:

```bash
# uv (Python manager) — installs to ~/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh
# pnpm (via corepack, ships with Node)
corepack enable && corepack prepare pnpm@latest --activate
# Docker + Node: install via your distro / CloudPanel if absent.
```

If Docker is **not** available and can't be installed, tell Claude — we'll switch to the
managed-Postgres path (needs a pgvector-capable DB) instead.

---

## 1. Get the code

```bash
sudo adduser --disabled-password --gecos "" odin || true
sudo -iu odin
git clone https://github.com/iamcanturk/odin.git /home/odin/app
cd /home/odin/app
```

## 2. Configure secrets

```bash
cp infra/deploy/.env.production.example .env
# Edit .env: set POSTGRES_PASSWORD, matching DATABASE_URL, INGEST_TOKEN.
# Generate strong values, e.g.:  openssl rand -hex 24
nano .env
chmod 600 .env
```

## 3. Backing services (Docker)

```bash
cd /home/odin/app/infra/deploy
docker compose -f docker-compose.prod.yml --env-file /home/odin/app/.env up -d
docker exec odin-postgres psql -U odin -d odin -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
# → should print a version (e.g. 0.8.x). If empty, the init script didn't run — see Troubleshooting.
```

## 4. First build + migrate

```bash
cd /home/odin/app
./infra/deploy/deploy.sh            # sync deps, alembic upgrade, pnpm build (does NOT start systemd yet on first run if units aren't installed)
```

> On the very first deploy the `systemctl restart` step fails because the units aren't installed
> yet — that's expected. Install them next (step 5), then re-run `deploy.sh`.

## 5. Install & start systemd services

```bash
sudo cp /home/odin/app/infra/deploy/systemd/odin-*.service /etc/systemd/system/
# If uv/pnpm live elsewhere than the unit paths, edit ExecStart accordingly:
#   which uv   →  update odin-api.service / odin-worker.service
#   which pnpm →  update odin-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now odin-api odin-worker odin-web
sudo systemctl status odin-api odin-worker odin-web --no-pager
```

Smoke test locally:

```bash
curl -s http://127.0.0.1:8000/health          # {"status":"ok",...}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # 200
```

## 6. CloudPanel site + reverse proxy

1. CloudPanel → **Sites** → create a site (Reverse Proxy or Node.js) for `odin.iamcanturk.dev`.
2. Issue the **Let's Encrypt** SSL certificate for the domain.
3. Open the site **Vhost** editor and paste the two `location` blocks from
   [`nginx-odin.conf`](nginx-odin.conf) inside the `server { }` block (don't duplicate
   `listen`/`ssl`/`server_name` — CloudPanel manages those).
4. Save; CloudPanel reloads nginx.

Verify:

```bash
curl -s https://odin.iamcanturk.dev/api/v1/events?limit=1
```

## 7. Seed + first ingestion

```bash
cd /home/odin/app/backend
uv run python -m app.scripts.manage seed
uv run python -m app.scripts.manage ingest    # the worker also runs this every 15 min
```

Open https://odin.iamcanturk.dev — the dashboard should show events.

## 8. Ongoing deploys

```bash
cd /home/odin/app && ./infra/deploy/deploy.sh
```

---

## Optional: browser extension

Point the X collector's **API base URL** to `https://odin.iamcanturk.dev/api/v1` and its token to
your `INGEST_TOKEN`. (The extension origin is already allowed in `manifest.json`.)

## Optional: enable the real LLM later

Set `LLM_API_KEY` in `.env` (DeepSeek) and `sudo systemctl restart odin-api odin-worker`.
Enrichment + content generation then produce real text instead of mock.

## Troubleshooting

- **pgvector missing after compose up:** the init SQL only runs on an *empty* data volume.
  Enable it manually: `docker exec -it odin-postgres psql -U odin -d odin -c "CREATE EXTENSION IF NOT EXISTS vector;"`
- **502 from nginx:** check `systemctl status odin-api odin-web` and `journalctl -u odin-api -n 50`.
- **CI is billing-blocked** — GitHub Actions won't run; deploys are manual via `deploy.sh`.

## CI/CD note

GitHub Actions is billing-blocked on the account, so there is no push-to-deploy. Deploy manually
with `deploy.sh`. Once Actions is restored, a deploy workflow (SSH → `deploy.sh`) can be added.
