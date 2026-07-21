import tempfile
import unittest
import gc
from pathlib import Path

from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore


class PublishedStoreRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLitePublishedArticlesStore(SQLiteDatabase(Path(self.tmp.name) / "repair.db"))

    def tearDown(self):
        self.store.database.connect().close()
        self.store = None
        gc.collect()
        self.tmp.cleanup()

    def test_incomplete_legacy_row_is_repaired_without_duplicate(self):
        self.store.append({"id": "a", "title": "Old", "summary": "", "url": "https://example/a", "score": 0})
        self.store.append({"id": "a", "title": "Enriched", "summary": "Useful summary", "url": "https://example/a", "score": .84})
        rows = self.store.latest()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Enriched")
        self.assertEqual(rows[0]["summary"], "Useful summary")
        self.assertEqual(rows[0]["score"], .84)

    def test_complete_row_is_never_overwritten(self):
        self.store.append({"id": "a", "title": "Complete", "summary": "Existing", "url": "https://example/a", "score": .72})
        self.assertIsNone(self.store.append({"id": "a", "title": "New", "summary": "Replacement", "url": "https://example/a", "score": .99}))
        row = self.store.latest()[0]
        self.assertEqual(row["title"], "Complete")
        self.assertEqual(row["summary"], "Existing")
        self.assertEqual(row["score"], .72)
