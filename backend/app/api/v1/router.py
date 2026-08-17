"""Aggregate v1 API router. Feature routers (events, sources, topics) mount here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import events, sources, topics

api_router = APIRouter()
api_router.include_router(events.router)
api_router.include_router(sources.router)
api_router.include_router(topics.router)
