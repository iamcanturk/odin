.PHONY: help dev-up dev-down backend-install backend-run backend-lint backend-test frontend-install frontend-dev frontend-build lint verify setup-hooks

help:
	@echo "ODIN — common tasks"
	@echo "  make dev-up            Start Postgres+pgvector and Redis (docker compose, local dev)"
	@echo "  make dev-down          Stop dev services"
	@echo "  make backend-install   uv sync (backend deps)"
	@echo "  make backend-run       Run FastAPI (uvicorn)"
	@echo "  make backend-lint      ruff check"
	@echo "  make backend-test      pytest"
	@echo "  make frontend-install  pnpm install (frontend)"
	@echo "  make frontend-dev      Next.js dev server"
	@echo "  make frontend-build    Next.js production build"
	@echo "  make lint              Lint backend + frontend"

dev-up:
	docker compose -f infra/docker-compose.dev.yml up -d

dev-down:
	docker compose -f infra/docker-compose.dev.yml down

backend-install:
	cd backend && uv sync

backend-run:
	cd backend && uv run uvicorn app.main:app --reload

backend-lint:
	cd backend && uv run ruff check .

backend-test:
	cd backend && uv run pytest

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

lint: backend-lint
	cd frontend && pnpm lint

# Local CI replacement (GitHub Actions is billing-blocked). Run before pushing.
verify:
	cd backend && uv run ruff check .
	cd backend && uv run pytest -q
	cd frontend && pnpm lint

# Install the committed git hooks (pre-push runs `make verify`).
setup-hooks:
	git config core.hooksPath .githooks
	@echo "✓ git hooks enabled (.githooks). pre-push will run 'make verify'."
