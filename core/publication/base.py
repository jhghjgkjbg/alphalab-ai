from datetime import datetime
from typing import Protocol
from uuid import UUID

from core.publication.types import (
    PublicationCandidate,
    PublicationDecision,
    PublishResult,
)


class PublicationDocument(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def source(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def url(self) -> str | None: ...

    @property
    def summary(self) -> str: ...

    @property
    def keywords(self) -> tuple[str, ...]: ...

    @property
    def tags(self) -> tuple[str, ...]: ...


class ScoringView(Protocol):
    @property
    def total_score(self) -> int: ...

    @property
    def reasons(self) -> tuple[str, ...]: ...

    @property
    def correlation_id(self) -> UUID: ...


class PublicationPolicy(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> int: ...

    def evaluate(self, total_score: int) -> PublicationDecision: ...


class Publisher(Protocol):
    @property
    def channel_name(self) -> str: ...

    async def publish(self, candidate: PublicationCandidate) -> PublishResult: ...


class PublicationLedger(Protocol):
    def is_processed(self, candidate_id: UUID) -> bool: ...

    def mark_processed(self, candidate_id: UUID) -> bool: ...
