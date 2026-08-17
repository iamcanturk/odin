"""Aggregate v1 API router. Feature routers (sources, events, topics) mount here."""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()

# Feature routers are included as they land:
#   from app.api.v1 import sources, events, topics
#   api_router.include_router(sources.router)
#   api_router.include_router(events.router)
#   api_router.include_router(topics.router)
