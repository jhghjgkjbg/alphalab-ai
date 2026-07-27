from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Mapping
import re

EVENT_TYPES = {"link_visited", "subscription_started", "subscription_confirmed", "subscription_cancelled"}
METADATA_KEYS = {"signup_surface", "subscription_provider", "confirmation_method", "content_variant", "locale"}

def sanitize_metadata(metadata):
    safe = {}
    for key, value in dict(metadata or {}).items():
        if key not in METADATA_KEYS or not isinstance(value, (str, bool, int, type(None))): continue
        if isinstance(value, str) and ("@" in value or "http://" in value.lower() or "https://" in value.lower() or re.search(r"(?:token|cookie|password|authorization|api[_-]?key)", value, re.I)): continue
        safe[key] = value
    return safe

@dataclass(frozen=True)
class GrowthEvent:
    event_id: str
    occurred_at: datetime
    event_type: str
    subscriber_id: str | None = None
    anonymous_id: str | None = None
    article_id: str | None = None
    destination_id: str | None = None
    campaign_id: str | None = None
    link_id: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.event_type not in EVENT_TYPES: raise ValueError("invalid growth event type")
        if self.occurred_at.tzinfo is None: raise ValueError("occurred_at must be timezone-aware")
        if not (self.subscriber_id or self.anonymous_id): raise ValueError("identity is required")
        if self.event_type in {"subscription_confirmed", "subscription_cancelled"} and not self.subscriber_id:
            raise ValueError("subscriber_id is required")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        safe = sanitize_metadata(self.metadata)
        object.__setattr__(self, "metadata", MappingProxyType(safe))

class GrowthEventRecorder:
    def __init__(self, store, clock=None):
        self.store, self.clock = store, clock or (lambda: datetime.now(UTC))

    @staticmethod
    def subscriber_id(email):
        import hashlib
        value = str(email or "").strip().casefold()
        if "@" not in value or value.startswith("@") or value.endswith("@"): raise ValueError("invalid email")
        return "email_sha256:v1:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _record(self, event_type, identity, **kwargs):
        import hashlib, json
        source_id = str(kwargs.pop("source_event_id", ""))
        identity_value = json.dumps([event_type, identity, source_id, kwargs.get("article_id"), kwargs.get("link_id"), kwargs.get("campaign_id")], sort_keys=True)
        event = GrowthEvent(hashlib.sha256(identity_value.encode()).hexdigest(), self.clock(), event_type, **identity, **kwargs)
        return self.store.append(event)

    def record_link_visit(self, anonymous_id, article_id, destination_id, campaign_id, content_variant, occurrence_id, **kwargs):
        from .attribution import build_link_id
        link_id = build_link_id(article_id, destination_id, campaign_id, content_variant)
        return self._record("link_visited", {"anonymous_id": str(anonymous_id)}, article_id=str(article_id), destination_id=str(destination_id), campaign_id=str(campaign_id), link_id=link_id, utm_content=str(content_variant), source_event_id=occurrence_id, **kwargs)

    def record_subscription_started(self, *, email=None, anonymous_id=None, source_event_id="", **kwargs):
        identity = {"subscriber_id": self.subscriber_id(email)} if email else {"anonymous_id": str(anonymous_id)}
        return self._record("subscription_started", identity, source_event_id=source_event_id, **kwargs)

    def record_subscription_confirmed(self, *, email=None, subscriber_id=None, source_event_id="", **kwargs):
        identity = {"subscriber_id": subscriber_id or self.subscriber_id(email)}
        return self._record("subscription_confirmed", identity, source_event_id=source_event_id, **kwargs)

    def record_subscription_cancelled(self, *, email=None, subscriber_id=None, source_event_id="", **kwargs):
        identity = {"subscriber_id": subscriber_id or self.subscriber_id(email)}
        return self._record("subscription_cancelled", identity, source_event_id=source_event_id, **kwargs)
