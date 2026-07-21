import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from core.collector.events import CollectionCompleted
from core.knowledge.events import KnowledgeStored
from core.knowledge.normalizer import KnowledgeNormalizer
from core.knowledge.repository import KnowledgeRepository


logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish(self, event: Any) -> None: ...


@dataclass(frozen=True, slots=True)
class KnowledgeProcessingStats:
    received: int
    stored: int
    duplicates: int
    failed: int


class KnowledgeHandler:
    def __init__(
        self,
        repository: KnowledgeRepository,
        event_publisher: EventPublisher,
        normalizer: KnowledgeNormalizer | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher
        self._normalizer = normalizer or KnowledgeNormalizer()
        self._stats: dict[UUID, KnowledgeProcessingStats] = {}

    async def handle(self, event: CollectionCompleted) -> None:
        received = stored = duplicates = failed = 0

        for item in event.items:
            received += 1
            try:
                document = self._normalizer.normalize(item)
            except Exception:
                failed += 1
                logger.exception(
                    "Knowledge normalization failed",
                    extra={"source": item.source, "external_id": item.external_id},
                )
                continue

            if not self._repository.add(document):
                duplicates += 1
                continue

            stored += 1
            await self._event_publisher.publish(
                KnowledgeStored(
                    event_id=uuid4(),
                    event_version=1,
                    occurred_at=datetime.now(UTC),
                    document_id=document.id,
                    source=document.source,
                    source_external_id=document.source_external_id,
                    correlation_id=event.correlation_id,
                )
            )

        self._stats[event.event_id] = KnowledgeProcessingStats(
            received=received,
            stored=stored,
            duplicates=duplicates,
            failed=failed,
        )

    def stats(self, event_id: UUID) -> KnowledgeProcessingStats:
        return self._stats.get(event_id, KnowledgeProcessingStats(0, 0, 0, 0))

    def saved_count(self, event_id: UUID) -> int:
        return self.stats(event_id).stored
