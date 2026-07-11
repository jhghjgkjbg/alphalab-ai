import asyncio
import sys
from datetime import UTC, datetime
from typing import TextIO
from uuid import uuid4

from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from agents.ai_scout.knowledge_store import KnowledgeStore
from core.collector.base import BaseCollector
from core.collector.events import CollectionCompleted
from core.collector.types import CollectorResult
from core.event_bus.base import BaseEventBus
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.handler import KnowledgeHandler
from core.knowledge.repository import KnowledgeRepository


class AIScout:
    def __init__(
        self,
        collector: BaseCollector | None = None,
        event_bus: BaseEventBus | None = None,
        knowledge_handler: KnowledgeHandler | None = None,
        knowledge_store: KnowledgeRepository | None = None,
        output: TextIO | None = None,
    ) -> None:
        self._collector = collector or HackerNewsCollector()
        self._event_bus = event_bus or InMemoryEventBus()
        repository = knowledge_store or KnowledgeStore()
        self._knowledge_handler = knowledge_handler or KnowledgeHandler(repository)
        self._event_bus.subscribe(CollectionCompleted, self._knowledge_handler.handle)
        self._output = output or sys.stdout

    async def run(self) -> CollectorResult:
        result = await self._collector.collect()
        event = CollectionCompleted(
            event_id=uuid4(),
            event_version=1,
            occurred_at=datetime.now(UTC),
            collector_name=result.collector_name,
            status=result.status,
            items=result.items,
            errors=result.errors,
            correlation_id=uuid4(),
        )
        await self._event_bus.publish(event)
        new_items = self._knowledge_handler.saved_count(event.event_id)

        print(f"Collected records: {len(result.items)}", file=self._output)
        print(f"New records: {new_items}", file=self._output)

        for item in result.items:
            print(f"Title: {item.payload['title']}", file=self._output)
            print(f"URL: {item.payload['url']}", file=self._output)
            print(f"Source: {item.source}", file=self._output)
            print(file=self._output)

        if result.errors:
            print(f"Skipped records: {len(result.errors)}", file=self._output)
            for error in result.errors:
                print(f"Warning: {error}", file=self._output)

        return result


async def main() -> None:
    scout = AIScout()
    await scout.run()


if __name__ == "__main__":
    asyncio.run(main())
