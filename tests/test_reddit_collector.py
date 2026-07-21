import asyncio
import unittest

from agents.ai_scout.clients.reddit_client import RedditPost, RedditResult
from agents.ai_scout.collectors.reddit import RedditCollector
from core.collector.types import CollectorStatus


POST = RedditPost("abc", "A post", "https://example.com", "/r/x/comments/abc/a", "Body", "author", 4)


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.limit = None

    async def fetch_posts(self, limit):
        self.limit = limit
        return self.result


class RedditCollectorTests(unittest.TestCase):
    def test_maps_post_and_passes_limit(self):
        client = FakeClient(RedditResult(True, (POST,), None))
        result = asyncio.run(RedditCollector(client, 3).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(client.limit, 3)
        item = result.items[0]
        self.assertEqual(item.source, "reddit")
        self.assertEqual(item.external_id, "abc")
        self.assertEqual(item.payload["title"], "A post")
        self.assertEqual(item.payload["url"], POST.url)
        self.assertEqual(item.payload["summary"], "Body")
        self.assertIsNone(item.payload["published_at"])
        self.assertEqual(item.payload["tags"], ("reddit",))

    def test_client_error_returns_empty_failed_result(self):
        client = FakeClient(RedditResult(False, (), "unavailable"))
        result = asyncio.run(RedditCollector(client).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())
        self.assertIn("unavailable", result.errors)


if __name__ == "__main__":
    unittest.main()
