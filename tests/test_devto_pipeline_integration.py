import asyncio
import unittest

from agents.ai_scout.clients.devto_client import DevToClient
from agents.ai_scout.collectors.devto import DevToCollector
from core.collector.types import CollectorStatus


class DevToPipelineIntegrationTests(unittest.TestCase):
    def test_api_response_flows_into_source_item(self):
        calls = []
        async def request(url, headers, params, timeout):
            calls.append((url, params))
            return [{"id": 1, "title": "Article", "url": "https://dev.to/a", "description": "Desc", "published_at": "2024-01-01", "tag_list": ["python"], "positive_reactions_count": 2}]
        result = asyncio.run(DevToCollector(DevToClient(2, request), 1, "python").collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "Article"); self.assertEqual(item.payload["url"], "https://dev.to/a")
        self.assertEqual(item.payload["summary"], "Desc"); self.assertEqual(item.source, "devto")
        self.assertEqual(item.payload["published_at"], "2024-01-01"); self.assertEqual(item.payload["tags"], ("python",))
        self.assertEqual(calls[0][1], {"per_page": "1", "tag": "python"})

    def test_empty_response_and_http_error(self):
        async def empty(*_): return []
        result = asyncio.run(DevToCollector(DevToClient(1, empty)).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS); self.assertEqual(result.items, ())
        async def error(*_): return (500, {})
        result = asyncio.run(DevToCollector(DevToClient(1, error)).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED); self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
