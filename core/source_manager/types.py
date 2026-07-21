from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping
from core.collector.types import SourceItem
from uuid import UUID


class SourcePriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class SourceRunStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    source_id: str
    collector_name: str
    enabled: bool
    interval_seconds: float
    priority: SourcePriority
    max_items: int
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SourceRunResult:
    source_id: str
    collector_name: str
    status: SourceRunStatus
    started_at: datetime
    finished_at: datetime
    collected_count: int
    error_count: int
    correlation_id: UUID
    error_message: str | None
    items: tuple[SourceItem, ...] = ()
