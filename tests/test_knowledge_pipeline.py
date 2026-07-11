import asyncio
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from core.collector.events import CollectionCompleted
from core.collector.types import CollectorStatus, SourceItem
from core.knowledge.handler import KnowledgeHandler
from core.knowledge.repository import InMemoryKnowledgeRepository


def make_item(source: str = "hacker_news", external_id: str = "1") -> SourceItem:
    return SourceItem(
        source=source,
        external_id=external_id,
        collected_at=datetime.now(UTC),
        payload={"title": "Story", "url": "https://example.com/story"},
    )


def make_event(*items: SourceItem) -> CollectionCompleted:
    return CollectionCompleted(
        event_id=uuid4(),
        event_version=1,
        occurred_at=datetime.now(UTC),
        collector_name="hacker_news",
        status=CollectorStatus.SUCCESS,
        items=items,
        errors=(),
        correlation_id=uuid4(),
    )


class KnowledgePipelineTests(unittest.TestCase):
    def test_handler_saves_items(self) -> None:
        repository = InMemoryKnowledgeRepository()
        handler = KnowledgeHandler(repository)
        event = make_event(make_item(external_id="1"), make_item(external_id="2"))

        asyncio.run(handler.handle(event))

        self.assertEqual(repository.count(), 2)
        self.assertEqual(handler.saved_count(event.event_id), 2)

    def test_repository_deduplicates_by_source_and_external_id(self) -> None:
        repository = InMemoryKnowledgeRepository()

        self.assertTrue(repository.save(make_item("hacker_news", "7")))
        self.assertFalse(repository.save(make_item("hacker_news", "7")))
        self.assertTrue(repository.save(make_item("another_source", "7")))
        self.assertEqual(repository.count(), 2)
