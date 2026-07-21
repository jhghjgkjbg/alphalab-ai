import asyncio
import unittest

from agents.ai_scout.clients.lobsters_client import LobstersClient
from agents.ai_scout.collectors.lobsters import LobstersCollector
from core.collector.types import CollectorStatus


class LobstersPipelineIntegrationTests(unittest.TestCase):
    def test_api_response_maps_to_source_item_and_honors_limit(self):
        calls = []
        async def request(url, headers, params, timeout):
            calls.append((url, timeout))
            return [{"short_id": "a", "title": "Story", "url": "https://lobste.rs/s/a", "description": "Desc", "submitter_user": "u", "tags": ["python"], "created_at": "2024"}, {"short_id": "b", "title": "Other", "url": "https://b"}]
        result = asyncio.run(LobstersCollector(LobstersClient(2, request), 1).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "Story"); self.assertEqual(item.payload["url"], "https://lobste.rs/s/a")
        self.assertEqual(item.payload["summary"], "Desc"); self.assertEqual(item.source, "lobsters")
        self.assertEqual(item.payload["published_at"], "2024"); self.assertEqual(item.payload["tags"], ("python",))
        self.assertEqual(len(calls), 1)

    def test_empty_http_error_and_invalid_json(self):
        async def empty(*_): return []
        result = asyncio.run(LobstersCollector(LobstersClient(1, empty)).collect()); self.assertEqual(result.items, ())
        async def error(*_): return (500, {})
        self.assertEqual(asyncio.run(LobstersCollector(LobstersClient(1, error)).collect()).status, CollectorStatus.FAILED)
        async def invalid(*_): return {"bad": True}
        self.assertEqual(asyncio.run(LobstersCollector(LobstersClient(1, invalid)).collect()).status, CollectorStatus.FAILED)


if __name__ == "__main__": unittest.main()
