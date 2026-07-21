from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class RankingRequest:
    item: Any
    text: str

@dataclass(frozen=True, slots=True)
class RankedItem:
    item: Any
    relevance_score: float
    novelty_score: float
    technical_depth: float
    business_value: float
    final_score: float

@dataclass(frozen=True, slots=True)
class RankingStats:
    total_items: int
    ranked_items: int
    failed_items: int
    cached_items: int
    failures: tuple[tuple[str, str, str], ...] = ()

@dataclass(frozen=True, slots=True)
class RankingResult:
    items: tuple[RankedItem, ...]
    stats: RankingStats
