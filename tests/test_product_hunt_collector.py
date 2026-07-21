import asyncio
import unittest

from agents.ai_scout.clients.product_hunt_client import ProductHuntItem, ProductHuntResult
from agents.ai_scout.collectors.product_hunt import ProductHuntCollector
from core.collector.types import CollectorStatus


ITEM = ProductHuntItem("1", "Tool", "https://tool", "Tagline", "Description", 4, ("AI",))


class FakeClient:
    def __init__(self, result): self.result = result; self.limit = None
    async def fetch_new_products(self, limit): self.limit = limit; return self.result


class ProductHuntCollectorTests(unittest.TestCase):
    def test_maps_item_and_honors_limit(self):
        client = FakeClient(ProductHuntResult(True, (ITEM,), None))
        result = asyncio.run(ProductHuntCollector(client, 3).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(client.limit, 3)
        item = result.items[0]
        self.assertEqual(item.source, "product_hunt")
        self.assertEqual(item.payload["title"], "Tool")
        self.assertEqual(item.payload["url"], ITEM.url)
        self.assertEqual(item.payload["summary"], "Tagline")
        self.assertIsNone(item.payload["published_at"])
        self.assertEqual(item.payload["tags"], ("AI",))

    def test_client_error_returns_empty_failed_result(self):
        result = asyncio.run(ProductHuntCollector(FakeClient(ProductHuntResult(False, (), "failed"))).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
