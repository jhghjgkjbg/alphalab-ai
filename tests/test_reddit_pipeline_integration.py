import asyncio
import unittest

from agents.ai_scout.clients.reddit_client import RedditClient
from agents.ai_scout.collectors.reddit import RedditCollector
from core.collector.types import CollectorStatus


class RedditPipelineIntegrationTests(unittest.TestCase):
    def test_mock_http_maps_post_to_source_item_and_honors_limit(self):
        calls = []

        async def request(url, headers, params, timeout):
            calls.append((url, params, timeout))
            return {"data": {"children": [
                {"data": {"id": "a", "title": "Post A", "url": "https://a", "permalink": "/r/x/a", "selftext": "Summary A", "author": "u", "score": 3}},
                {"data": {"id": "b", "title": "Post B", "url": "https://b", "permalink": "/r/x/b", "selftext": "Summary B", "author": None, "score": 2}},
            ]}}

        result = asyncio.run(RedditCollector(RedditClient("python", 2, request), 1).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "Post A")
        self.assertEqual(item.payload["url"], "https://a")
        self.assertEqual(item.payload["summary"], "Summary A")
        self.assertEqual(item.source, "reddit")
        self.assertIsNone(item.payload["published_at"])
        self.assertEqual(item.payload["tags"], ("reddit",))
        self.assertEqual(calls[0][1]["limit"], "1")

    def test_empty_response_and_http_error(self):
        async def empty(*_):
            return {"data": {"children": []}}
        result = asyncio.run(RedditCollector(RedditClient("x", 1, empty)).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(result.items, ())

        async def error(*_):
            return (429, {})
        result = asyncio.run(RedditCollector(RedditClient("x", 1, error)).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())


if __name__ == "__main__":
    unittest.main()
