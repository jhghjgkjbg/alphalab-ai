import asyncio
import unittest
from agents.ai_scout.clients.hacker_news_client import HackerNewsItem, HackerNewsResult
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from core.collector.types import CollectorStatus


class FakeClient:
    def __init__(self, result): self.result = result; self.limit = None
    async def fetch_top_stories(self, limit): self.limit = limit; return self.result


class HackerNewsClientCollectorTests(unittest.TestCase):
    def test_maps_item_and_honors_max_items(self):
        item = HackerNewsItem(1, "Title", "https://example.com", "Summary", "author", 4, 100)
        client = FakeClient(HackerNewsResult(True, (item,), ()))
        result = asyncio.run(HackerNewsCollector(client=client, max_items=2).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(client.limit, 2)
        source = result.items[0]
        self.assertEqual(source.source, "hacker_news")
        self.assertEqual(source.payload["title"], "Title")
        self.assertEqual(source.payload["url"], item.url)
        self.assertEqual(source.payload["summary"], "Summary")
        self.assertIsNotNone(source.payload["published_at"])
        self.assertEqual(source.payload["tags"], ("hacker_news",))

    def test_client_error_returns_empty_failed_result(self):
        client = FakeClient(HackerNewsResult(False, (), ("failed",)))
        result = asyncio.run(HackerNewsCollector(client=client).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
