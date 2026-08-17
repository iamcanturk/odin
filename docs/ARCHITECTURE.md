# ODIN Architecture

Living technical overview. Product spec: [../PROJECT.md](../PROJECT.md).

## System shape

```
Internet
  → Source adapters (RSS, Hacker News, …)   app/sources/
  → normalize → dedup                        app/pipeline/
  → ContentItem (Postgres, pgvector)         app/models/
  → embed (local e5) + event clustering      app/providers/, app/pipeline/
  → Event (canonical)                        app/models/
  → TrendScore + lifecycle                   app/pipeline/
  → v1 API                                   app/api/v1/
  → Next.js dashboard                        frontend/
```

Background ingestion runs on an **ARQ** worker (Redis-backed); the FastAPI process serves the API.

## Components

| Concern | Choice | Notes |
|---------|--------|-------|
| API | FastAPI (async) | `app/main.py` app factory, `/api/v1` router |
| DB | PostgreSQL 16 + pgvector | embeddings stored on `content_items` |
| ORM / migrations | SQLAlchemy 2 (async) + Alembic | never mutate prod schema by hand |
| Queue | ARQ + Redis | poll/normalize/cluster/score tasks |
| Embeddings | `multilingual-e5-small` (local, CPU) | no API cost; TR + EN |
| LLM | DeepSeek via OpenAI-compatible SDK | `LLMProvider` abstraction, swappable |
| Frontend | Next.js 15 + TS + Tailwind + shadcn/ui | dark intelligence-dashboard aesthetic |

## Key principles (from PROJECT.md)

- **Event-first**: many sources → one canonical `Event`; don't treat each item as a trend.
- **Source-agnostic**: every source implements `SourceAdapter`; no source config hard-coded in logic.
- **Explainable, versioned scoring**: deterministic/statistical over black-box; store `scoring_version`.
- **Human-in-the-loop**: ODIN recommends; the user approves before publishing (later phases).
- **Cost control**: cheap filtering + dedup + local embeddings before any paid LLM call.

## Environments

- **Local dev**: `infra/docker-compose.dev.yml` (Postgres+pgvector, Redis). Backend/frontend run on host.
- **Production**: native CloudPanel sites at `odin.iamcanturk.dev` — Node site (Next.js), Python site
  (FastAPI behind reverse proxy), CloudPanel-managed Postgres (pgvector extension), Redis. See
  `infra/deploy/`. No Docker in production.

## Roadmap

Milestone **M0** delivers the vertical slice: RSS + Hacker News → clustering → trend score → dashboard.
Later phases (PROJECT.md §47): X/Reddit sources, user profile + style analysis, viral simulation,
publish workflow + feedback loop.
