from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from core.enrichment.events import KnowledgeEnriched
from core.scoring.engine import ScoringEngine
from core.scoring.events import ScoringCompleted
from core.scoring.types import ScorableItem


class EventPublisher(Protocol):
    async def publish(self, event: Any) -> None: ...


class KnowledgeReader(Protocol):
    def get(self, document_id: UUID) -> ScorableItem | None: ...


class ScoringHandler:
    def __init__(
        self,
        engine: ScoringEngine,
        event_publisher: EventPublisher,
        knowledge_reader: KnowledgeReader,
    ) -> None:
        self._engine = engine
        self._event_publisher = event_publisher
        self._knowledge_reader = knowledge_reader

    async def handle(self, event: KnowledgeEnriched) -> None:
        document = self._knowledge_reader.get(event.document_id)
        if document is None:
            raise LookupError(f"Knowledge document not found: {event.document_id}")

        result = await self._engine.score(document)
        await self._event_publisher.publish(
            ScoringCompleted(
                event_id=uuid4(),
                event_version=1,
                occurred_at=datetime.now(UTC),
                source=document.source,
                external_id=document.source_external_id,
                total_score=result.total_score,
                details=result.details,
                reasons=result.reasons,
                correlation_id=event.correlation_id,
            )
        )
