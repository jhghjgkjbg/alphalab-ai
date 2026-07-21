from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from core.publication.base import PublicationDocument, PublicationLedger
from core.publication.engine import PublicationEngine
from core.publication.events import (
    PublicationCandidateCreated,
    PublicationCompleted,
    PublicationRejected,
)
from core.publication.types import PublicationHandlingResult
from core.scoring.events import ScoringCompleted


class EventPublisher(Protocol):
    async def publish(self, event: Any) -> None: ...


class KnowledgeReader(Protocol):
    def get_by_source_key(
        self,
        source: str,
        source_external_id: str,
    ) -> PublicationDocument | None: ...


class PublicationHandler:
    def __init__(
        self,
        engine: PublicationEngine,
        knowledge_reader: KnowledgeReader,
        ledger: PublicationLedger,
        event_publisher: EventPublisher,
    ) -> None:
        self._engine = engine
        self._knowledge_reader = knowledge_reader
        self._ledger = ledger
        self._event_publisher = event_publisher

    async def handle(self, event: ScoringCompleted) -> PublicationHandlingResult:
        document = self._knowledge_reader.get_by_source_key(
            event.source,
            event.external_id,
        )
        if document is None:
            raise LookupError(
                f"Knowledge document not found: {event.source}/{event.external_id}"
            )

        plan = self._engine.plan(document, event)
        if not plan.decision.accepted:
            await self._event_publisher.publish(
                PublicationRejected(
                    event_id=uuid4(), event_version=1, occurred_at=datetime.now(UTC),
                    document_id=document.id, reason=plan.decision.reason,
                    policy_name=plan.decision.policy_name,
                    policy_version=plan.decision.policy_version,
                    correlation_id=event.correlation_id,
                )
            )
            return PublicationHandlingResult(False, None, (), True, False)

        candidate = plan.candidate
        assert candidate is not None
        if self._ledger.is_processed(candidate.candidate_id):
            return PublicationHandlingResult(
                True, candidate.candidate_id, (), False, True
            )

        await self._event_publisher.publish(
            PublicationCandidateCreated(
                event_id=uuid4(), event_version=1, occurred_at=datetime.now(UTC),
                candidate_id=candidate.candidate_id, document_id=candidate.document_id,
                channels=candidate.channels, correlation_id=candidate.correlation_id,
            )
        )
        results = await self._engine.publish(candidate)
        self._ledger.mark_processed(candidate.candidate_id)
        await self._event_publisher.publish(
            PublicationCompleted(
                event_id=uuid4(), event_version=1, occurred_at=datetime.now(UTC),
                candidate_id=candidate.candidate_id, document_id=candidate.document_id,
                results=results, correlation_id=candidate.correlation_id,
            )
        )
        return PublicationHandlingResult(
            True, candidate.candidate_id, results, False, False
        )
