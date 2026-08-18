#!/usr/bin/env bash
# ODIN deploy — pull, install, migrate, build, restart. Run as the `odin` user.
#   cd /home/odin/app && ./infra/deploy/deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/home/odin/app}"
# Same-origin API — the reverse proxy routes /api to the backend.
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-/api/v1}"

cd "$APP_DIR"

echo "▶ git pull"
git pull --ff-only

echo "▶ backend deps (uv sync)"
cd "$APP_DIR/backend"
# Add --extra ml for local e5 embeddings (EMBEDDING_BACKEND=local); omit for hash.
if grep -q '^EMBEDDING_BACKEND=local' "$APP_DIR/.env" 2>/dev/null; then
  uv sync --extra ml
else
  uv sync
fi

echo "▶ database migrations"
uv run alembic upgrade head

echo "▶ frontend build (NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL)"
cd "$APP_DIR/frontend"
pnpm install --frozen-lockfile
pnpm build

echo "▶ restart services"
sudo systemctl restart odin-api odin-worker odin-web

echo "✓ deploy complete"
systemctl --no-pager --lines=0 status odin-api odin-worker odin-web || true
