import asyncio
import unittest

from agents.ai_scout.clients.product_hunt_client import ProductHuntClient


NODE = {"id": "1", "name": "Tool", "url": "https://tool", "tagline": "Build", "description": "Desc", "votesCount": 5, "topics": [{"name": "AI"}]}


class ProductHuntClientTests(unittest.TestCase):
    def test_fetches_new_products_with_bearer_and_limit(self):
        calls = []
        async def request(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"data": {"posts": {"nodes": [NODE, {**NODE, "id": "2"}]}}}
        result = asyncio.run(ProductHuntClient("secret", 2, request).fetch_new_products(1))
        self.assertTrue(result.success)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].name, "Tool")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer secret")
        self.assertEqual(calls[0][2]["variables"]["first"], 1)

    def test_errors_empty_invalid_and_timeout(self):
        async def error(*_): return (500, {})
        self.assertFalse(asyncio.run(ProductHuntClient("x", 1, error).fetch_new_products()).success)
        async def empty(*_): return {"data": {"posts": {"nodes": []}}}
        result = asyncio.run(ProductHuntClient("x", 1, empty).fetch_new_products())
        self.assertTrue(result.success); self.assertEqual(result.items, ())
        async def invalid(*_): return {"bad": True}
        self.assertFalse(asyncio.run(ProductHuntClient("x", 1, invalid).fetch_new_products()).success)
        async def timeout(*_): raise TimeoutError()
        result = asyncio.run(ProductHuntClient("x", 1, timeout).fetch_new_products())
        self.assertIn("timed out", result.error_message)


if __name__ == "__main__": unittest.main()
