import asyncio
import unittest

from agents.ai_scout.clients.arxiv_client import ArxivItem, ArxivResult
from agents.ai_scout.collectors.arxiv import ArxivCollector
from core.collector.types import CollectorStatus


PAPER = ArxivItem("id1", "Title", "Summary", "https://arxiv.org/1", "2024", ("Alice",), ("cs.AI",))


class FakeClient:
    def __init__(self, result): self.result = result; self.args = None
    async def search(self, query, max_items): self.args = (query, max_items); return self.result


class ArxivCollectorTests(unittest.TestCase):
    def test_maps_paper_and_options(self):
        client = FakeClient(ArxivResult(True, (PAPER,), None))
        result = asyncio.run(ArxivCollector(client, "cat:cs.AI", 2).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS); self.assertEqual(client.args, ("cat:cs.AI", 2))
        item = result.items[0]
        self.assertEqual(item.source, "arxiv"); self.assertEqual(item.payload["title"], "Title"); self.assertEqual(item.payload["url"], PAPER.url)
        self.assertEqual(item.payload["summary"], "Summary"); self.assertEqual(item.payload["published_at"], "2024"); self.assertEqual(item.payload["tags"], ("cs.AI",))

    def test_client_error_returns_empty_failed_result(self):
        result = asyncio.run(ArxivCollector(FakeClient(ArxivResult(False, (), "failed")), "x").collect())
        self.assertEqual(result.status, CollectorStatus.FAILED); self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
