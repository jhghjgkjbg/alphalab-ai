import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.arxiv_client import ArxivItem, ArxivResult


class FakeArxivClient:
    async def search(self, query, max_items):
        return ArxivResult(True, (ArxivItem("id", "Paper", "Summary", "https://arxiv.org/id", None, ("A",), ("cs.AI",)),), None)


class ArxivSourceManagerPipelineTests(unittest.TestCase):
    def test_arxiv_runs_through_source_manager_and_scheduler(self):
        scout = AIScout(output=io.StringIO(), rss_enabled=False, arxiv_client=FakeArxivClient())
        results = asyncio.run(scout.run_once())
        result = next(item for item in results if item.source_id == "arxiv")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(scout._collector_registry.create("arxiv").name(), "arxiv")
        self.assertIn("source:arxiv", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
