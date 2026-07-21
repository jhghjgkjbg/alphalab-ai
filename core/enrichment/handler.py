from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from core.enrichment.engine import EnrichmentEngine
from core.enrichment.events import KnowledgeEnriched
from core.knowledge.events import KnowledgeStored
from core.knowledge.models import KnowledgeDocument


class EventPublisher(Protocol):
    async def publish(self, event: Any) -> None: ...


class KnowledgeRepositoryPort(Protocol):
    def get(self, document_id: UUID) -> KnowledgeDocument | None: ...

    def update(self, document: KnowledgeDocument, expected_version: int) -> bool: ...


class EnrichmentHandler:
    def __init__(
        self,
        engine: EnrichmentEngine,
        repository: KnowledgeRepositoryPort,
        event_publisher: EventPublisher,
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._event_publisher = event_publisher

    async def handle(self, event: KnowledgeStored) -> None:
        document = self._repository.get(event.document_id)
        if document is None:
            raise LookupError(f"Knowledge document not found: {event.document_id}")

        result = await self._engine.enrich(document)
        enriched = replace(
            document,
            summary=result.summary,
            keywords=result.keywords,
            tags=result.tags,
            version=document.version + 1,
            updated_at=datetime.now(UTC),
        )
        if not self._repository.update(enriched, expected_version=document.version):
            return

        await self._event_publisher.publish(
            KnowledgeEnriched(
                event_id=uuid4(),
                event_version=1,
                occurred_at=datetime.now(UTC),
                document_id=document.id,
                previous_version=document.version,
                current_version=enriched.version,
                correlation_id=event.correlation_id,
                warnings=result.warnings,
            )
        )
