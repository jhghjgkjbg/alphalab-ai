from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from core.collector.types import CollectorStatus, SourceItem


@dataclass(frozen=True, slots=True)
class CollectionCompleted:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    collector_name: str
    status: CollectorStatus
    items: tuple[SourceItem, ...]
    errors: tuple[str, ...]
    correlation_id: UUID
