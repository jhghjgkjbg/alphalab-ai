import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.reddit_client import RedditClient


class RedditCompositionTests(unittest.TestCase):
    def test_reddit_registration_uses_injected_client(self):
        async def request(*_):
            return {"data": {"children": []}}
        scout = AIScout(
            output=io.StringIO(), rss_enabled=False,
            reddit_client=RedditClient("python", 2, request), reddit_limit=4,
        )
        collector = scout._collector_registry.create("reddit", max_items=4)
        self.assertEqual(collector.name(), "reddit")

    def test_reddit_source_and_scheduler_are_opt_in(self):
        async def request(*_):
            return {"data": {"children": []}}
        scout = AIScout(output=io.StringIO(), rss_enabled=False, reddit_request=request)
        self.assertIn("reddit", scout._source_manager._source_registry._sources)
        self.assertIn("source:reddit", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__":
    unittest.main()
