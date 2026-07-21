import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.lobsters_client import LobstersItem, LobstersResult


class FakeLobstersClient:
    async def fetch_new(self, max_items):
        return LobstersResult(True, (LobstersItem("a", "Story", "https://lobste.rs/a", "Desc", "u", ("python",), None),), None)


class LobstersSourceManagerPipelineTests(unittest.TestCase):
    def test_lobsters_is_registered_and_runs_through_source_manager(self):
        scout = AIScout(output=io.StringIO(), rss_enabled=False, lobsters_client=FakeLobstersClient())
        results = asyncio.run(scout.run_once())
        result = next(item for item in results if item.source_id == "lobsters")
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(scout._collector_registry.create("lobsters").name(), "lobsters")
        self.assertIn("source:lobsters", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
