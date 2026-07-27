from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Mapping
from types import MappingProxyType
import re

EVENT_TYPES = {"delivery_deferred", "delivery_attempted", "delivery_succeeded", "delivery_failed", "delivery_unknown", "delivery_skipped"}
DELIVERY_STATUSES = {"pending", "sent", "failed", "unknown", "skipped"}

@dataclass(frozen=True)
class DistributionEvent:
    event_id: str
    occurred_at: datetime
    event_type: str
    article_id: str
    destination_id: str
    delivery_status: str
    attempt_number: int
    external_id: str | None = None
    scheduled_for: datetime | None = None
    reason: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not str(self.article_id).strip(): raise ValueError("article_id must be non-empty")
        if not str(self.destination_id).strip(): raise ValueError("destination_id must be non-empty")
        if self.event_type not in EVENT_TYPES: raise ValueError("invalid event_type")
        if self.delivery_status not in DELIVERY_STATUSES: raise ValueError("invalid delivery_status")
        if int(self.attempt_number) < 0: raise ValueError("attempt_number must be non-negative")
        if self.reason is not None:
            reason = str(self.reason).strip()
            if not reason or len(reason) > 80 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", reason): raise ValueError("invalid reason")
            object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))
        if self.occurred_at.tzinfo is None: raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        if self.scheduled_for is not None:
            if self.scheduled_for.tzinfo is None: raise ValueError("scheduled_for must be timezone-aware")
            object.__setattr__(self, "scheduled_for", self.scheduled_for.astimezone(UTC))
