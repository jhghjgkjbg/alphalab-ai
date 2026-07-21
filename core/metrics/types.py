from dataclasses import dataclass
from typing import Protocol
@dataclass(frozen=True, slots=True)
class PublicationMetrics:
    editorial_score: float; quality_score: float; ranking_score: float; language: str; source: str; category: str; trend_bonus: float; freshness: float; summary_length: int; title_length: int
class MetricsCollector(Protocol):
    def collect(self, metrics: PublicationMetrics) -> None: ...
class NoOpCollector:
    def collect(self, metrics): return None
