# ODIN Backend

FastAPI service: source ingestion, event clustering, trend scoring, and the v1 API.

## Setup

```bash
uv sync                       # install runtime + dev deps
uv run uvicorn app.main:app --reload   # (available after issue #3)
uv run ruff check .
uv run pytest
```

Heavy ML deps (embeddings) are an optional extra installed later:

```bash
uv sync --extra ml
```

## Layout

```
app/
  core/       config, logging, DB session
  models/     SQLAlchemy models
  schemas/    Pydantic DTOs
  api/v1/     HTTP routers
  sources/    SourceAdapter interface + adapters (rss, hackernews)
  pipeline/   normalize, dedup, embed, clustering, trend scoring
  providers/  LLMProvider (DeepSeek) + EmbeddingProvider (local e5)
  workers/    ARQ background tasks
alembic/      migrations
tests/
```
