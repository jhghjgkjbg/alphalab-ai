import io
import unittest

from agents.ai_scout.agent import AIScout


class FakeClient:
    async def fetch_top_stories(self, max_items):
        return None


class HackerNewsCompositionTests(unittest.TestCase):
    def test_hacker_news_factory_uses_injected_client_and_limit(self):
        scout = AIScout(
            output=io.StringIO(), rss_enabled=False,
            hacker_news_client=FakeClient(), hacker_news_max_items=6,
        )
        collector = scout._collector_registry.create("hacker_news", max_items=6)
        self.assertEqual(collector.name(), "hacker_news")

    def test_hacker_news_scheduler_task_exists(self):
        scout = AIScout(output=io.StringIO(), rss_enabled=False)
        self.assertIn("source:hacker_news", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
