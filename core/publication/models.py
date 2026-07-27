from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Mapping, Protocol
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode

DEFAULT_PUBLIC_BASE_URL = "https://alphalabai.online"

def build_public_article_url(public_base_url: str, article_id: str) -> str:
    parts = urlsplit(str(public_base_url or DEFAULT_PUBLIC_BASE_URL))
    path = parts.path.rstrip("/") + "/article/" + quote(str(article_id), safe="")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

def build_tracked_public_url(public_base_url: str, article_id: str, language: str, source: str = "telegram") -> str:
    parts = urlsplit(build_public_article_url(public_base_url, article_id))
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"utm_source": source, "utm_medium": "social", "utm_campaign": "content_distribution", "utm_content": language})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

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
