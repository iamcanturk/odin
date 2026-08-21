"""Enumerations used across models. Stored as strings (not native PG enums)."""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    RSS = "rss"
    HACKERNEWS = "hackernews"
    GITHUB = "github"
    REDDIT = "reddit"
    X = "x"
    CISA_KEV = "cisa_kev"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "med"
    LOW = "low"


class EventStatus(StrEnum):
    """Event lifecycle (PROJECT.md §7)."""

    DISCOVERED = "discovered"
    VERIFIED = "verified"
    RISING = "rising"
    TRENDING = "trending"
    SATURATED = "saturated"
    DECLINING = "declining"
    ARCHIVED = "archived"
