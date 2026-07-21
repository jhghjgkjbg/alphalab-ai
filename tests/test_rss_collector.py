import asyncio
import unittest
from urllib.error import HTTPError

from agents.ai_scout.collectors.rss import RSSCollector
from core.collector.types import CollectorStatus


RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><guid>guid-1</guid><title>First story</title><link>https://example.com/1</link>
<description>First description</description><pubDate>Wed, 01 Jan 2025 12:00:00 GMT</pubDate><author>alice</author></item>
<item><title>Second story</title><link>https://example.com/2</link></item>
<item><title>Third story</title><link>https://example.com/3</link></item>
</channel></rss>'''

ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title>
<entry><id>atom-1</id><title>Atom story</title><link href="https://example.com/atom"/>
<summary>Atom summary</summary><updated>2025-01-01T12:00:00Z</updated>
<author><name>bob</name></author></entry></feed>'''


class RSSCollectorTests(unittest.TestCase):
    def test_rss_20_maps_to_source_item(self) -> None:
        collector = RSSCollector("https://example.com/rss", fetch=lambda *_: RSS)

        result = asyncio.run(collector.collect())
        item = result.items[0]

        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(item.external_id, "guid-1")
        self.assertEqual(item.payload["title"], "First story")
        self.assertEqual(item.payload["url"], "https://example.com/1")
        self.assertEqual(item.payload["content"], "First description")
        self.assertEqual(item.metadata["author"], "alice")
        self.assertIsNotNone(item.metadata["published_at"])

    def test_atom_maps_to_source_item(self) -> None:
        collector = RSSCollector("https://example.com/atom", fetch=lambda *_: ATOM)

        result = asyncio.run(collector.collect())

        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(result.items[0].external_id, "atom-1")
        self.assertEqual(result.items[0].payload["url"], "https://example.com/atom")
        self.assertEqual(result.items[0].metadata["author"], "bob")

    def test_missing_guid_uses_deterministic_url_id_and_max_items(self) -> None:
        collector = RSSCollector("https://example.com/rss", max_items=2, fetch=lambda *_: RSS)

        first = asyncio.run(collector.collect())
        second = asyncio.run(collector.collect())

        self.assertEqual(len(first.items), 2)
        self.assertEqual(first.items[1].external_id, second.items[1].external_id)
        self.assertEqual(len(first.items[1].external_id), 36)

    def test_bad_record_is_partial_not_total_failure(self) -> None:
        feed = b'<rss><channel><item><title>valid</title><link>https://valid</link></item><item><link>https://bad</link></item></channel></rss>'
        result = asyncio.run(
            RSSCollector("https://example.com/rss", fetch=lambda *_: feed).collect()
        )

        self.assertEqual(result.status, CollectorStatus.PARTIAL)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(len(result.errors), 1)

    def test_timeout_http_error_invalid_xml_and_size_are_failed(self) -> None:
        cases = [
            lambda *_: (_ for _ in ()).throw(TimeoutError("timeout")),
            lambda *_: (_ for _ in ()).throw(HTTPError("url", 500, "error", {}, None)),
            lambda *_: b"<invalid",
            lambda *_: b"x" * (RSSCollector.MAX_RESPONSE_BYTES + 1),
        ]

        for fetch in cases:
            with self.subTest(fetch=fetch):
                result = asyncio.run(
                    RSSCollector("https://example.com/rss", fetch=fetch).collect()
                )
                self.assertEqual(result.status, CollectorStatus.FAILED)
                self.assertEqual(len(result.errors), 1)

    def test_rejects_non_http_url(self) -> None:
        with self.assertRaises(ValueError):
            RSSCollector("file:///tmp/feed.xml")


if __name__ == "__main__":
    unittest.main()
