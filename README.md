# ODIN — Personal Internet Intelligence Engine

> "ODIN watches the internet for me, understands what matters, predicts what is worth talking about, creates content in my style, and learns from the results."

ODIN is a personal AI-powered internet intelligence and social-media assistant. It continuously
observes many sources, clusters signals into canonical **Events**, scores their trend momentum and
personal opportunity, and (later) generates platform-specific content in the user's own style.

Full product specification: [PROJECT.md](PROJECT.md).

## Architecture

Monorepo with two deployables:

| Part | Stack |
|------|-------|
| **backend/** | Python 3.11 · FastAPI · SQLAlchemy 2 + Alembic · ARQ (Redis queue) · PostgreSQL 16 + pgvector |
| **frontend/** | Next.js 15 (App Router) · TypeScript · TailwindCSS · shadcn/ui · TanStack Query |

- **LLM**: DeepSeek via an OpenAI-compatible `LLMProvider` abstraction (swappable to OpenAI/Anthropic).
- **Embeddings**: local `multilingual-e5-small` (sentence-transformers, CPU) — no API cost.
- **Deploy target**: native CloudPanel sites at `odin.iamcanturk.dev` (Docker Compose is dev-only).

```
Internet → Sources → ContentItems → Event Detection → Trend Analysis → Opportunity → Dashboard
```

## Repository layout

```
backend/    FastAPI app, source adapters, ingestion pipeline, ARQ workers
frontend/   Next.js dashboard
infra/      docker-compose.dev.yml (local dev) + CloudPanel deploy notes
docs/       ARCHITECTURE.md
```

## Local development

```bash
docker compose -f infra/docker-compose.dev.yml up -d   # Postgres+pgvector + Redis
cp .env.example .env                                   # fill in secrets
# backend & frontend setup — see docs/ARCHITECTURE.md
```

## Workflow

Every change ships through **GitHub issue → branch → PR → merge**. `main` is protected and requires
CI to pass. See open issues and the current milestone for what's in progress.

## Status

🚧 **M0 — Foundation & Vertical Slice** in progress: RSS + Hacker News ingestion → event clustering →
trend scoring → dashboard.
