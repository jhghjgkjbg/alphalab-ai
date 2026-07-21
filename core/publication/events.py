from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from core.publication.types import PublishResult


@dataclass(frozen=True, slots=True)
class PublicationCandidateCreated:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    candidate_id: UUID
    document_id: UUID
    channels: tuple[str, ...]
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class PublicationCompleted:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    candidate_id: UUID
    document_id: UUID
    results: tuple[PublishResult, ...]
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class PublicationRejected:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    document_id: UUID
    reason: str
    policy_name: str
    policy_version: int
    correlation_id: UUID
