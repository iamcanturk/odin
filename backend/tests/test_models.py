"""Model registration smoke tests (no DB connection required)."""

from __future__ import annotations

from app.core.db import Base
from app.models import ContentItem, Event, EventSource, EventTopic, Source, Topic


def test_all_tables_registered() -> None:
    tables = set(Base.metadata.tables)
    assert {
        "sources",
        "content_items",
        "events",
        "event_sources",
        "event_topics",
        "topics",
    } <= tables


def test_content_item_metadata_column_name() -> None:
    # The 'metadata' attribute is reserved by Declarative -> mapped as item_metadata.
    col = ContentItem.__table__.c["metadata"]
    assert col.name == "metadata"
    assert hasattr(ContentItem, "item_metadata")


def test_embedding_columns_present() -> None:
    assert "embedding" in ContentItem.__table__.c
    assert "centroid" in Event.__table__.c


def test_associations_composite_pk() -> None:
    assert {c.name for c in EventSource.__table__.primary_key} == {"event_id", "source_id"}
    assert {c.name for c in EventTopic.__table__.primary_key} == {"event_id", "topic_id"}
    # referenced models are importable
    assert Source.__tablename__ == "sources"
    assert Topic.__tablename__ == "topics"
