"""Aggregate v1 API router. Feature routers (events, sources, topics) mount here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import events, ingest, profile, sources, topics

api_router = APIRouter()
api_router.include_router(events.router)
api_router.include_router(sources.router)
api_router.include_router(topics.router)
api_router.include_router(ingest.router)
api_router.include_router(profile.router)
