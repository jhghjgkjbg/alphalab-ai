import asyncio
import unittest

from agents.ai_scout.clients.arxiv_client import ArxivClient
from agents.ai_scout.collectors.arxiv import ArxivCollector
from core.collector.types import CollectorStatus


XML = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>id1</id><title> Paper </title><summary> Summary </summary><published>2024</published><author><name>Alice</name></author><category term="cs.AI"/><link rel="alternate" href="https://arxiv.org/1"/></entry></feed>'''


class ArxivPipelineIntegrationTests(unittest.TestCase):
    def test_atom_response_maps_to_source_item(self):
        calls = []
        async def request(url, headers, params, timeout): calls.append(params); return XML
        result = asyncio.run(ArxivCollector(ArxivClient(2, request), "cat:cs.AI", 1).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "Paper"); self.assertEqual(item.payload["url"], "https://arxiv.org/1")
        self.assertEqual(item.payload["summary"], "Summary"); self.assertEqual(item.source, "arxiv")
        self.assertEqual(item.payload["published_at"], "2024"); self.assertEqual(item.payload["tags"], ("cs.AI",)); self.assertEqual(item.payload["authors"], ("Alice",))
        self.assertEqual(calls[0], {"search_query": "cat:cs.AI", "max_results": "1"})

    def test_empty_http_error_and_invalid_xml(self):
        async def empty(*_): return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        result = asyncio.run(ArxivCollector(ArxivClient(1, empty), "x").collect()); self.assertEqual(result.items, ())
        async def error(*_): return (500, b"")
        self.assertEqual(asyncio.run(ArxivCollector(ArxivClient(1, error), "x").collect()).status, CollectorStatus.FAILED)
        async def invalid(*_): return b"bad"
        self.assertEqual(asyncio.run(ArxivCollector(ArxivClient(1, invalid), "x").collect()).status, CollectorStatus.FAILED)


if __name__ == "__main__": unittest.main()
