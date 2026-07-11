from uuid import UUID

from core.collector.events import CollectionCompleted
from core.knowledge.repository import KnowledgeRepository


class KnowledgeHandler:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository
        self._saved_counts: dict[UUID, int] = {}

    async def handle(self, event: CollectionCompleted) -> None:
        saved_count = sum(self._repository.save(item) for item in event.items)
        self._saved_counts[event.event_id] = saved_count

    def saved_count(self, event_id: UUID) -> int:
        return self._saved_counts.get(event_id, 0)
