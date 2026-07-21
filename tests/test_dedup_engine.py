import unittest
from core.collector.types import SourceItem
from core.dedup.engine import DedupEngine
from core.dedup.normalize import normalize_url

class DedupTests(unittest.TestCase):
    def item(self, source, title, url, published_at=None): return SourceItem(source, title, __import__('datetime').datetime.now(), {"title": title, "url": url, "published_at": published_at})
    def test_urls_titles_priority_stats_and_empty(self):
        items = [self.item("rss", "Same", "https://EXAMPLE.com/a/?utm_source=x"), self.item("github", "Other", "https://example.com/a")]
        unique, groups, stats = DedupEngine().deduplicate(items); self.assertEqual(unique[0].source, "github"); self.assertEqual(stats.duplicate_items, 1); self.assertEqual(len(groups), 1); self.assertEqual(DedupEngine().deduplicate([])[2].total_items, 0); self.assertEqual(normalize_url("https://x/a/#f?gclid=1"), "https://x/a")

if __name__ == "__main__": unittest.main()
