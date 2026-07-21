import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from core.collector.registry import CollectorRegistry
from core.collector.types import SourceItem
from core.event_bus.in_memory import InMemoryEventBus
from core.source_manager.manager import SourceManager
from core.source_manager.registry import SourceRegistry
from core.source_manager.types import SourceDefinition, SourcePriority, SourceRunStatus
from agents.ai_scout.collectors.rss import RSSCollector


FEED = b'<rss><channel><item><guid>rss-1</guid><title>RSS item</title><link>https://example.com/rss-1</link></item></channel></rss>'


class RSSIntegrationTests(unittest.TestCase):
    def test_source_manager_creates_rss_through_factory(self) -> None:
        collectors = CollectorRegistry()
        collectors.register_factory(
            "rss",
            lambda **config: RSSCollector(
                str(config["metadata"]["feed_url"]),
                int(config["max_items"]),
                fetch=lambda *_: FEED,
            ),
        )
        sources = SourceRegistry()
        sources.register(
            SourceDefinition(
                source_id="rss", collector_name="rss", enabled=True,
                interval_seconds=60, priority=SourcePriority.NORMAL,
                max_items=1, metadata={"feed_url": "https://example.com/feed"},
            )
        )
        manager = SourceManager(collectors, sources, InMemoryEventBus())

        result = asyncio.run(manager.run_source("rss"))

        self.assertEqual(result.status, SourceRunStatus.SUCCESS)
        self.assertEqual(result.collected_count, 1)

    def test_full_ai_scout_pipeline_runs_rss_without_network(self) -> None:
        def hn_fetch(url: str, _: float) -> object:
            if url.endswith("topstories.json"):
                return [1]
            return {"id": 1, "title": "HN story", "url": "https://example.com/hn"}

        repository = __import__(
            "core.knowledge.repository", fromlist=["InMemoryKnowledgeRepository"]
        ).InMemoryKnowledgeRepository()
        output = io.StringIO()
        scout = AIScout(
            collector=HackerNewsCollector(fetch_json=hn_fetch),
            knowledge_store=repository,
            output=output,
            rss_enabled=True,
            rss_fetch=lambda *_: FEED,
        )

        results = asyncio.run(scout.run_once())

        self.assertEqual(len(results), 2)
        self.assertEqual(repository.count(), 2)
        self.assertEqual(
            repository.get_by_source_key("rss", "rss-1").title,
            "RSS item",
        )
        self.assertIn("Stored records: 2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
