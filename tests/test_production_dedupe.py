from datetime import UTC, datetime

from core.collector.types import SourceItem
from core.production_runner import ProductionRunner


def item(external_id, title, url, source="rss"):
    return SourceItem(source, external_id, datetime.now(UTC), {"title": title, "url": url, "summary": "summary"})


def test_production_batch_dedupe_keeps_one_url_and_distinct_urls_with_same_title():
    first = item("1", "Same title", "https://example.test/a")
    duplicate = item("2", "Same title", "https://example.test/a?utm_source=x")
    distinct = item("3", "Same title", "https://example.test/b")

    result = ProductionRunner._batch_deduplicate((first, duplicate, distinct))

    assert len(result) == 2
    assert {x.payload["url"].split("?")[0] for x in result} == {"https://example.test/a", "https://example.test/b"}


def test_production_published_filter_skips_existing_id_and_url():
    class Store:
        def contains(self, article_id, url):
            return article_id == "existing-id" or url == "https://example.test/published"

    runner = ProductionRunner(store=Store())
    result = runner._published_filter((item("existing-id", "A", "https://example.test/a"), item("new", "B", "https://example.test/published"), item("ok", "C", "https://example.test/new")))

    assert [x.external_id for x in result] == ["ok"]
