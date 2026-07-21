import asyncio
import unittest

from agents.ai_scout.clients.hacker_news_client import HackerNewsClient
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from core.collector.types import CollectorStatus


class HackerNewsPipelineIntegrationTests(unittest.TestCase):
    def test_top_stories_flow_into_source_item(self):
        calls = []
        async def request(url, timeout):
            calls.append(url)
            if url.endswith("topstories.json"):
                return [101, 102]
            return {"id": 101, "title": "Top story", "url": "https://example.com/story", "text": "Summary", "by": "author", "score": 8, "time": 100}

        result = asyncio.run(HackerNewsCollector(client=HackerNewsClient(2, request), max_items=1).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "Top story")
        self.assertEqual(item.payload["url"], "https://example.com/story")
        self.assertEqual(item.payload["summary"], "Summary")
        self.assertEqual(item.source, "hacker_news")
        self.assertIsNotNone(item.payload["published_at"])
        self.assertEqual(item.payload["tags"], ("hacker_news",))
        self.assertEqual(len(calls), 2)

    def test_empty_http_error_and_invalid_json(self):
        async def empty(*_): return []
        result = asyncio.run(HackerNewsCollector(client=HackerNewsClient(1, empty)).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(result.items, ())

        async def error(*_): return (503, {})
        result = asyncio.run(HackerNewsCollector(client=HackerNewsClient(1, error)).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())

        async def invalid(*_): return {"invalid": True}
        result = asyncio.run(HackerNewsCollector(client=HackerNewsClient(1, invalid)).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
