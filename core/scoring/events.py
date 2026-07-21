from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from core.scoring.types import RuleResult


@dataclass(frozen=True, slots=True)
class ScoringCompleted:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    source: str
    external_id: str
    total_score: int
    details: tuple[RuleResult, ...]
    reasons: tuple[str, ...]
    correlation_id: UUID
