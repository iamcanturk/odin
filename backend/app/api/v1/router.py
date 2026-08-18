"""Aggregate v1 API router. Feature routers mount here.

Protected routers require a valid JWT (via require_auth). Public: auth, ingest
(uses its own X-Ingest-Token). /health lives outside /api/v1 and is always open.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import (
    auth,
    evaluation,
    events,
    ingest,
    notifications,
    posts,
    profile,
    sources,
    tester,
    topics,
)
from app.core.security import require_auth

api_router = APIRouter()

# Public routers.
api_router.include_router(auth.router)
api_router.include_router(ingest.router)  # guarded by its own X-Ingest-Token

# Protected routers (require a valid session token when auth is enabled).
_protected = Depends(require_auth)
api_router.include_router(events.router, dependencies=[_protected])
api_router.include_router(sources.router, dependencies=[_protected])
api_router.include_router(topics.router, dependencies=[_protected])
api_router.include_router(profile.router, dependencies=[_protected])
api_router.include_router(tester.router, dependencies=[_protected])
api_router.include_router(posts.router, dependencies=[_protected])
api_router.include_router(evaluation.router, dependencies=[_protected])
api_router.include_router(notifications.router, dependencies=[_protected])
