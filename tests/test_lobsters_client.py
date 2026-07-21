import asyncio
import unittest

from agents.ai_scout.clients.lobsters_client import LobstersClient


ITEM = {"short_id": "abc", "title": "Story", "url": "https://lobste.rs/s/abc", "description": "Desc", "submitter_user": "u", "tags": ["python"], "created_at": "2024-01-01"}


class LobstersClientTests(unittest.TestCase):
    def test_fetches_new_items_with_limit(self):
        calls = []
        async def request(url, headers, params, timeout): calls.append((url, timeout)); return [ITEM, {**ITEM, "short_id": "def"}]
        result = asyncio.run(LobstersClient(2, request).fetch_new(1))
        self.assertTrue(result.success); self.assertEqual(len(result.items), 1); self.assertEqual(calls[0][0], LobstersClient.API_URL)

    def test_errors_empty_invalid_and_timeout(self):
        async def error(*_): return (500, {})
        self.assertFalse(asyncio.run(LobstersClient(1, error).fetch_new()).success)
        async def empty(*_): return []
        result = asyncio.run(LobstersClient(1, empty).fetch_new()); self.assertTrue(result.success); self.assertEqual(result.items, ())
        async def invalid(*_): return {"bad": True}
        self.assertFalse(asyncio.run(LobstersClient(1, invalid).fetch_new()).success)
        async def timeout(*_): raise TimeoutError()
        result = asyncio.run(LobstersClient(1, timeout).fetch_new()); self.assertIn("timed out", result.error_message)


if __name__ == "__main__": unittest.main()
