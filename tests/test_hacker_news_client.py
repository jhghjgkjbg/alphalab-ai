import asyncio
import unittest

from agents.ai_scout.clients.hacker_news_client import HackerNewsClient


ITEM = {"id": 1, "title": "Story", "url": "https://example.com", "by": "user", "score": 5, "time": 10}


class HackerNewsClientTests(unittest.TestCase):
    def test_fetches_top_stories_and_items_with_limit(self):
        calls = []
        async def request(url, timeout):
            calls.append(url)
            return [1, 2] if url.endswith("topstories.json") else ITEM | {"id": int(url.split("/")[-1].split(".")[0])}
        result = asyncio.run(HackerNewsClient(2, request).fetch_top_stories(1))
        self.assertTrue(result.success)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "Story")
        self.assertEqual(len(calls), 2)

    def test_errors_empty_and_invalid_json(self):
        async def error(*_): return (500, {})
        self.assertFalse(asyncio.run(HackerNewsClient(1, error).fetch_top_stories()).success)

        async def empty(*_): return []
        result = asyncio.run(HackerNewsClient(1, empty).fetch_top_stories())
        self.assertTrue(result.success)
        self.assertEqual(result.items, ())

        async def invalid(*_): return {"bad": True}
        result = asyncio.run(HackerNewsClient(1, invalid).fetch_top_stories())
        self.assertFalse(result.success)

        async def timeout(*_): raise TimeoutError()
        result = asyncio.run(HackerNewsClient(1, timeout).fetch_top_stories())
        self.assertIn("timed out", result.errors[0])


if __name__ == "__main__": unittest.main()
