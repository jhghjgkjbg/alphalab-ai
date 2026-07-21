import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.hacker_news_client import HackerNewsItem, HackerNewsResult


class FakeHackerNewsClient:
    async def fetch_top_stories(self, max_items):
        return HackerNewsResult(
            True,
            (HackerNewsItem(7, "HN title", "https://example.com/hn", "HN summary", "user", 10, 100),),
            (),
        )


class HackerNewsSourceManagerPipelineTests(unittest.TestCase):
    def test_source_manager_runs_hacker_news_and_scheduler_is_registered(self):
        scout = AIScout(
            output=io.StringIO(), rss_enabled=False,
            hacker_news_client=FakeHackerNewsClient(), hacker_news_max_items=3,
        )
        results = asyncio.run(scout.run_once())
        hacker_news = next(result for result in results if result.source_id == "hacker_news")
        self.assertEqual(hacker_news.collected_count, 1)
        self.assertEqual(hacker_news.status.value, "success")
        self.assertIn("source:hacker_news", {task.task_id for task in scout._scheduler.tasks()})
        collector = scout._collector_registry.create("hacker_news", max_items=3)
        self.assertEqual(collector.name(), "hacker_news")


if __name__ == "__main__": unittest.main()
