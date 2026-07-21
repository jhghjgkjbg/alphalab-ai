import asyncio
import unittest

from agents.ai_scout.clients.arxiv_client import ArxivClient


XML = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1</id><title>Title</title><summary>Summary</summary><published>2024-01-01</published><author><name>Alice</name></author><category term="cs.AI"/><link rel="alternate" href="https://arxiv.org/abs/1"/></entry></feed>'''


class ArxivClientTests(unittest.TestCase):
    def test_parses_atom_and_limits_results(self):
        calls = []
        async def request(url, headers, params, timeout): calls.append(params); return XML
        result = asyncio.run(ArxivClient(2, request).search("cat:cs.AI", 1))
        self.assertTrue(result.success); self.assertEqual(result.items[0].title, "Title"); self.assertEqual(result.items[0].authors, ("Alice",)); self.assertEqual(result.items[0].categories, ("cs.AI",)); self.assertEqual(calls[0]["max_results"], "1")

    def test_errors_empty_and_invalid_xml(self):
        async def error(*_): return (500, b"")
        self.assertFalse(asyncio.run(ArxivClient(1, error).search("x")).success)
        async def empty(*_): return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        result = asyncio.run(ArxivClient(1, empty).search("x")); self.assertTrue(result.success); self.assertEqual(result.items, ())
        async def invalid(*_): return b"bad"
        self.assertFalse(asyncio.run(ArxivClient(1, invalid).search("x")).success)
        async def timeout(*_): raise TimeoutError()
        result = asyncio.run(ArxivClient(1, timeout).search("x")); self.assertIn("timed out", result.error_message)


if __name__ == "__main__": unittest.main()
