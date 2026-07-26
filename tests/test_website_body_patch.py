import asyncio
import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agents.ai_scout.collectors.rss import normalize_rss_text
from core.publication.builder import PublicationBuilder
from core.renderers.website import WebsiteRenderer
from core.renderers.website import WebsiteView
from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore


class WebsiteBodyPatchTests(unittest.TestCase):
    def test_rss_normalization(self):
        value = "<p>One&nbsp;two</p><script>drop()</script><style>x{}</style><p>Three</p>"
        self.assertEqual(normalize_rss_text(value), "One two\nThree")
        self.assertEqual(normalize_rss_text(""), "")

    def test_builder_keeps_preview_and_body_separate(self):
        publication = PublicationBuilder().build({
            "id": "a",
            "title": "Title",
            "summary": "Short preview",
            "content": "Full normalized article text",
            "url": "https://example.test/a",
        })
        self.assertEqual(publication.summary, "Short preview")
        variant = publication.variants["en"]
        self.assertEqual(variant.summary, "Short preview")
        self.assertEqual(variant.body, "Full normalized article text")
        view = WebsiteRenderer("en").render(publication)
        self.assertEqual(view.body, "Full normalized article text")

    def test_store_migrates_and_persists_body(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            database = SQLiteDatabase(Path(td) / "body.db")
            store = SQLitePublishedArticlesStore(database)
            store.append({"id": "a", "title": "Title", "summary": "Preview", "en_body": "Full body", "url": "https://example.test/a"})
            with sqlite3.connect(database.path) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(published_articles)")}
                row = connection.execute("SELECT summary,en_body FROM published_articles WHERE id='a'").fetchone()
            self.assertIn("en_body", columns)
            self.assertEqual(row, ("Preview", "Full body"))
            del store, database
            gc.collect()

    def test_website_view_old_positional_contract(self):
        view = WebsiteView("t", "s", "src", "cat", "en", "date", 0.5, "url", "why", "audience")
        self.assertEqual(view.why_this_matters, "why")
        self.assertEqual(view.target_audience, "audience")
        self.assertEqual(view.body, "")

    def test_inline_rss_boundaries(self):
        self.assertEqual(normalize_rss_text("<span>Hello</span><span>world</span>"), "Hello world")
        self.assertEqual(normalize_rss_text("<p>Hello <strong>world</strong>.</p>"), "Hello world.")
        self.assertIn("First\nSecond", normalize_rss_text("<div>First</div><div>Second</div>"))
        self.assertEqual(normalize_rss_text("<p>Hello&nbsp;world</p>"), "Hello world")


if __name__ == "__main__":
    unittest.main()
