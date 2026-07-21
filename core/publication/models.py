from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Mapping, Protocol

@dataclass(frozen=True, slots=True)
class LanguageVariant:
    language: str; title: str; summary: str; body: str = ""; description: str = ""; keywords: tuple[str, ...] = (); canonical_url: str = ""; publication_id: str = ""; metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class Publication:
    publication_id: str
    article_id: str
    language: str
    title: str
    summary: str
    url: str
    canonical_url: str
    source: str
    category: str
    published_at: str
    score: float
    trend_bonus: float = 0.0
    editorial_score: float = 0.0
    editorial_verdict: str = ""
    why_this_matters: str = ""
    target_audience: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    variants: Mapping[str, LanguageVariant] = field(default_factory=dict)
    quality_scores: Mapping[str, float] = field(default_factory=dict)
    final_quality_score: float = 0.0
    ranking_score: float = 0.0
    ranking_details: Mapping[str, float] = field(default_factory=dict)
    ai_context: object = None
    metrics: object = None
    priority: object = None
    publication_window: object = None
    channels: object = None

class PublicationRenderer(Protocol):
    def render(self, publication: Publication) -> Any: ...
