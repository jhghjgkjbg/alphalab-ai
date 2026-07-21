import asyncio
import unittest

from agents.ai_scout.clients.product_hunt_client import ProductHuntClient
from agents.ai_scout.collectors.product_hunt import ProductHuntCollector
from core.collector.types import CollectorStatus


class ProductHuntPipelineIntegrationTests(unittest.TestCase):
    def test_graphql_response_flows_into_source_item(self):
        calls = []

        async def request(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"data": {"posts": {"nodes": [{
                "id": "p1", "name": "Product", "url": "https://product",
                "tagline": "A useful product", "description": "Details",
                "votesCount": 12, "topics": [{"name": "AI"}],
            }, {"id": "p2", "name": "Other", "url": "https://other", "tagline": "Other", "topics": []}]}}}

        result = asyncio.run(ProductHuntCollector(ProductHuntClient("token", 2, request), 1).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "Product")
        self.assertEqual(item.payload["url"], "https://product")
        self.assertEqual(item.payload["summary"], "A useful product")
        self.assertEqual(item.source, "product_hunt")
        self.assertIsNone(item.payload["published_at"])
        self.assertEqual(item.payload["tags"], ("AI",))
        self.assertEqual(calls[0][2]["variables"]["first"], 1)

    def test_empty_response_and_http_error(self):
        async def empty(*_): return {"data": {"posts": {"nodes": []}}}
        result = asyncio.run(ProductHuntCollector(ProductHuntClient("x", 1, empty)).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(result.items, ())
        async def error(*_): return (500, {})
        result = asyncio.run(ProductHuntCollector(ProductHuntClient("x", 1, error)).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
