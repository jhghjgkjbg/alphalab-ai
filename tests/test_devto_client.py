import asyncio
import unittest

from agents.ai_scout.clients.devto_client import DevToClient


ARTICLE = {"id": 1, "title": "Article", "url": "https://dev.to/a", "description": "Desc", "published_at": "2024-01-01", "tag_list": ["python"], "positive_reactions_count": 3}


class DevToClientTests(unittest.TestCase):
    def test_fetches_articles_with_limit_and_tag(self):
        calls = []
        async def request(url, headers, params, timeout):
            calls.append((url, params)); return [ARTICLE, {**ARTICLE, "id": 2}]
        result = asyncio.run(DevToClient(2, request).fetch_articles(1, "python"))
        self.assertTrue(result.success); self.assertEqual(len(result.articles), 1)
        self.assertEqual(calls[0][1], {"per_page": "1", "tag": "python"})

    def test_errors_empty_invalid_and_timeout(self):
        async def error(*_): return (500, {})
        self.assertFalse(asyncio.run(DevToClient(1, error).fetch_articles()).success)
        async def empty(*_): return []
        result = asyncio.run(DevToClient(1, empty).fetch_articles()); self.assertTrue(result.success); self.assertEqual(result.articles, ())
        async def invalid(*_): return {"bad": True}
        self.assertFalse(asyncio.run(DevToClient(1, invalid).fetch_articles()).success)
        async def timeout(*_): raise TimeoutError()
        result = asyncio.run(DevToClient(1, timeout).fetch_articles()); self.assertIn("timed out", result.error_message)


if __name__ == "__main__": unittest.main()
