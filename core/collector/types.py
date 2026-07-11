from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class CollectorStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SourceItem:
    source: str
    external_id: str
    collected_at: datetime
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CollectorResult:
    collector_name: str
    status: CollectorStatus
    started_at: datetime
    finished_at: datetime
    items: tuple[SourceItem, ...] = ()
    errors: tuple[str, ...] = ()
