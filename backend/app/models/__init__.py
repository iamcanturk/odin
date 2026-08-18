"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.models.associations import EventSource, EventTopic
from app.models.content_candidate import ContentCandidate
from app.models.content_item import ContentItem
from app.models.event import Event
from app.models.notification import Notification
from app.models.post import Post, PostMetric, PostPrediction
from app.models.source import Source
from app.models.style_profile import StyleProfile
from app.models.topic import Topic

__all__ = [
    "ContentCandidate",
    "ContentItem",
    "Event",
    "EventSource",
    "EventTopic",
    "Notification",
    "Post",
    "PostMetric",
    "PostPrediction",
    "Source",
    "StyleProfile",
    "Topic",
]
