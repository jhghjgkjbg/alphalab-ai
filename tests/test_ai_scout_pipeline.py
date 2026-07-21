import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from core.collector.types import CollectorStatus
from core.event_bus.in_memory import InMemoryEventBus
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
        event_bus = InMemoryEventBus()
        output = io.StringIO()
        scout = AIScout(
            collector=HackerNewsCollector(fetch_json=fetch_json),
            event_bus=event_bus,
            knowledge_store=repository,
            output=output,
        )

        result = asyncio.run(scout.run())

        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(repository.count(), 2)
        self.assertEqual(
            [document.source_external_id for document in repository.all()],
            ["100", "101"],
        )
        self.assertIn("Collected records: 2", output.getvalue())
        self.assertIn("Stored records: 2", output.getvalue())
        self.assertIn("Accepted for publication: 2", output.getvalue())
        self.assertIn("Published successfully: 2", output.getvalue())
        self.assertIn("Summary:", output.getvalue())
        self.assertIn("Keywords:", output.getvalue())
        self.assertIn("Tags:", output.getvalue())
        self.assertIn("Total score:", output.getvalue())
        self.assertTrue(all(document.version == 2 for document in repository.all()))
