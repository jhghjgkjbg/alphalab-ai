import asyncio
import io
import unittest
from datetime import UTC, datetime

from agents.ai_scout.agent import AIScout
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from agents.ai_scout.knowledge_store import KnowledgeStore
from core.collector.types import CollectorStatus, SourceItem


def make_source_item(external_id: str = "1") -> SourceItem:
    return SourceItem(
        source="hacker_news",
        external_id=external_id,
        collected_at=datetime.now(UTC),
        payload={"title": f"Story {external_id}", "url": f"https://example.com/{external_id}"},
    )


class HackerNewsCollectorTests(unittest.TestCase):
    def test_transforms_api_response_to_source_item(self) -> None:
        item = HackerNewsCollector.to_source_item(
            {
                "id": 42,
                "title": "AlphaLab launches",
                "url": "https://example.com/alphalab",
                "by": "alice",
                "score": 100,
                "time": 1_700_000_000,
                "type": "story",
            }
        )

        self.assertEqual(item.external_id, "42")
        self.assertEqual(item.source, "hacker_news")
        self.assertEqual(item.payload["title"], "AlphaLab launches")
        self.assertEqual(item.payload["url"], "https://example.com/alphalab")
        self.assertEqual(item.metadata["author"], "alice")

    def test_keeps_other_items_when_one_item_fails(self) -> None:
        def fetch_json(url: str, _: float) -> object:
            if url.endswith("topstories.json"):
                return [1, 2]
            if url.endswith("/item/1.json"):
                return {
                    "id": 1,
                    "title": "Working story",
                    "url": "https://example.com/working",
                }
            raise TimeoutError("request timed out")

        result = asyncio.run(HackerNewsCollector(fetch_json=fetch_json).collect())

        self.assertEqual(result.status, CollectorStatus.PARTIAL)
        self.assertEqual([item.external_id for item in result.items], ["1"])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("item 2 skipped", result.errors[0])


class KnowledgeStoreTests(unittest.TestCase):
    def test_deduplicates_items_by_external_id(self) -> None:
        store = KnowledgeStore()
        first = make_source_item("7")
        duplicate = make_source_item("7")

        self.assertTrue(store.save(first))
        self.assertFalse(store.save(duplicate))
        self.assertEqual(store.all(), (first,))


class AIScoutTests(unittest.TestCase):
    def test_successful_run_with_mocked_http(self) -> None:
        def fetch_json(url: str, _: float) -> object:
            if url.endswith("topstories.json"):
                return [10, 11]
            story_id = int(url.removesuffix(".json").rsplit("/", 1)[-1])
            return {
                "id": story_id,
                "title": f"Story {story_id}",
                "url": f"https://example.com/{story_id}",
            }

        output = io.StringIO()
        store = KnowledgeStore()
        scout = AIScout(
            collector=HackerNewsCollector(fetch_json=fetch_json),
            knowledge_store=store,
            output=output,
        )

        result = asyncio.run(scout.run())

        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(len(store.all()), 2)
        self.assertIn("Collected records: 2", output.getvalue())
        self.assertIn("New records: 2", output.getvalue())
        self.assertIn("Title: Story 10", output.getvalue())
        self.assertIn("URL: https://example.com/10", output.getvalue())
        self.assertIn("Source: hacker_news", output.getvalue())


if __name__ == "__main__":
    unittest.main()
