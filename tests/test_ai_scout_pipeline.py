import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from core.collector.types import CollectorStatus
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.handler import KnowledgeHandler
from core.knowledge.repository import InMemoryKnowledgeRepository


class AIScoutPipelineTests(unittest.TestCase):
    def test_complete_pipeline_with_mocked_http(self) -> None:
        def fetch_json(url: str, _: float) -> object:
            if url.endswith("topstories.json"):
                return [100, 101]
            item_id = int(url.removesuffix(".json").rsplit("/", 1)[-1])
            return {
                "id": item_id,
                "title": f"Pipeline story {item_id}",
                "url": f"https://example.com/{item_id}",
            }

        repository = InMemoryKnowledgeRepository()
        handler = KnowledgeHandler(repository)
        event_bus = InMemoryEventBus()
        output = io.StringIO()
        scout = AIScout(
            collector=HackerNewsCollector(fetch_json=fetch_json),
            event_bus=event_bus,
            knowledge_handler=handler,
            output=output,
        )

        result = asyncio.run(scout.run())

        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(repository.count(), 2)
        self.assertEqual(
            [item.external_id for item in repository.all()],
            ["100", "101"],
        )
        self.assertIn("Collected records: 2", output.getvalue())
        self.assertIn("New records: 2", output.getvalue())
