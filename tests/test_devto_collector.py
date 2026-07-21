import asyncio
import unittest

from agents.ai_scout.clients.devto_client import DevToArticle, DevToResult
from agents.ai_scout.collectors.devto import DevToCollector
from core.collector.types import CollectorStatus


ARTICLE = DevToArticle(1, "Article", "https://dev.to/a", "Description", "2024-01-01", ("python",), 2)


class FakeClient:
    def __init__(self, result): self.result = result; self.args = None
    async def fetch_articles(self, max_items, tag): self.args = (max_items, tag); return self.result


class DevToCollectorTests(unittest.TestCase):
    def test_maps_article_and_passes_options(self):
        client = FakeClient(DevToResult(True, (ARTICLE,), None))
        result = asyncio.run(DevToCollector(client, 3, "python").collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS); self.assertEqual(client.args, (3, "python"))
        item = result.items[0]
        self.assertEqual(item.source, "devto"); self.assertEqual(item.payload["title"], "Article")
        self.assertEqual(item.payload["url"], ARTICLE.url); self.assertEqual(item.payload["summary"], "Description")
        self.assertEqual(item.payload["published_at"], ARTICLE.published_at); self.assertEqual(item.payload["tags"], ("python",))

    def test_client_error_returns_empty_failed_result(self):
        result = asyncio.run(DevToCollector(FakeClient(DevToResult(False, (), "failed"))).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED); self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
