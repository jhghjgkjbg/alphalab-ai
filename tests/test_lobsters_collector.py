import asyncio
import unittest

from agents.ai_scout.clients.lobsters_client import LobstersItem, LobstersResult
from agents.ai_scout.collectors.lobsters import LobstersCollector
from core.collector.types import CollectorStatus


POST = LobstersItem("abc", "Story", "https://lobste.rs/s/abc", "Desc", "user", ("python",), "2024-01-01")


class FakeClient:
    def __init__(self, result): self.result = result; self.limit = None
    async def fetch_new(self, limit): self.limit = limit; return self.result


class LobstersCollectorTests(unittest.TestCase):
    def test_maps_item_and_honors_limit(self):
        client = FakeClient(LobstersResult(True, (POST,), None))
        result = asyncio.run(LobstersCollector(client, 3).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS); self.assertEqual(client.limit, 3)
        item = result.items[0]
        self.assertEqual(item.source, "lobsters"); self.assertEqual(item.payload["title"], "Story")
        self.assertEqual(item.payload["url"], POST.url); self.assertEqual(item.payload["summary"], "Desc")
        self.assertEqual(item.payload["published_at"], POST.created_at); self.assertEqual(item.payload["tags"], ("python",))

    def test_client_error_returns_empty_failed_result(self):
        result = asyncio.run(LobstersCollector(FakeClient(LobstersResult(False, (), "failed"))).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED); self.assertEqual(result.items, ())


if __name__ == "__main__": unittest.main()
