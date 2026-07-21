from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5
from typing import Any

@dataclass(frozen=True, slots=True)
class PublicationRequest:
    items: tuple[Any, ...]
    minimum_score: float = 0.0
    top_n: int = 10
    dry_run: bool = False

@dataclass(frozen=True, slots=True)
class PublishedItem:
    item: Any
    success: bool
    external_id: str | None = None

@dataclass(frozen=True, slots=True)
class PublicationStats:
    total_items: int
    eligible_items: int
    published_items: int
    skipped_duplicates: int

@dataclass(frozen=True, slots=True)
class PublicationResult:
    items: tuple[PublishedItem, ...]
    stats: PublicationStats


PUBLICATION_CANDIDATE_NAMESPACE = uuid5(
    NAMESPACE_URL,
    "https://alphalab.ai/publication-candidate",
)


def build_candidate_id(document_id: UUID, policy_version: int) -> UUID:
    return uuid5(PUBLICATION_CANDIDATE_NAMESPACE, f"{document_id}\x00{policy_version}")


@dataclass(frozen=True, slots=True)
class PublicationCandidate:
    candidate_id: UUID
    document_id: UUID
    source: str
    title: str
    url: str | None
    summary: str
    keywords: tuple[str, ...]
    tags: tuple[str, ...]
    total_score: int
    reasons: tuple[str, ...]
    channels: tuple[str, ...]
    correlation_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PublicationDecision:
    accepted: bool
    channels: tuple[str, ...]
    reason: str
    policy_name: str
    policy_version: int
    minimum_score: int
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class PublishResult:
    channel: str
    success: bool
    external_id: str | None
    published_at: datetime
    error_message: str | None


@dataclass(frozen=True, slots=True)
class PublicationPlan:
    decision: PublicationDecision
    candidate: PublicationCandidate | None


@dataclass(frozen=True, slots=True)
class PublicationHandlingResult:
    accepted: bool
    candidate_id: UUID | None
    results: tuple[PublishResult, ...]
    rejected: bool
    idempotent: bool
