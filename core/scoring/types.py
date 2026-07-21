from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import Any

@dataclass(frozen=True, slots=True)
class ScoringRequest:
    item: Any
    ranking_score: float = 0.0
    similarity_penalty: float = 0.0
    source_priority: float = 0.0
    freshness_bonus: float = 0.0
    popularity_bonus: float = 0.0
    manual_boost: float = 0.0
    published_at: datetime | None = None

@dataclass(frozen=True, slots=True)
class ScoredItem:
    item: Any
    final_score: float

@dataclass(frozen=True, slots=True)
class ScoringStats:
    total_items: int
    scored_items: int

@dataclass(frozen=True, slots=True)
class ScoringResult:
    items: tuple[ScoredItem, ...]
    stats: ScoringStats


class ScorableItem(Protocol):
    @property
    def source(self) -> str: ...

    @property
    def collected_at(self) -> datetime: ...

    @property
    def title(self) -> str: ...

    @property
    def summary(self) -> str: ...

    @property
    def content(self) -> str: ...


@dataclass(frozen=True, slots=True)
class RuleResult:
    rule_name: str
    score_delta: int
    reason: str


@dataclass(frozen=True, slots=True)
class ScoreResult:
    total_score: int
    details: tuple[RuleResult, ...]
    reasons: tuple[str, ...]
