import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.devto_client import DevToArticle, DevToResult


class FakeDevToClient:
    async def fetch_articles(self, max_items, tag):
        return DevToResult(True, (DevToArticle(1, "Article", "https://dev.to/a", "Desc", None, ("python",), 1),), None)


class DevToSourceManagerTests(unittest.TestCase):
    def test_devto_runs_through_source_manager_and_scheduler(self):
        scout = AIScout(output=io.StringIO(), rss_enabled=False, devto_client=FakeDevToClient())
        results = asyncio.run(scout.run_once())
        result = next(item for item in results if item.source_id == "devto")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(scout._collector_registry.create("devto").name(), "devto")
        self.assertIn("source:devto", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
