import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.lobsters_client import LobstersClient


class LobstersCompositionTests(unittest.TestCase):
    def test_injected_client_registers_collector(self):
        async def request(*_): return []
        scout = AIScout(output=io.StringIO(), rss_enabled=False, lobsters_client=LobstersClient(1, request))
        self.assertEqual(scout._collector_registry.create("lobsters").name(), "lobsters")

    def test_source_and_scheduler_are_registered(self):
        async def request(*_): return []
        scout = AIScout(output=io.StringIO(), rss_enabled=False, lobsters_request=request)
        self.assertIn("lobsters", scout._source_manager._source_registry._sources)
        self.assertIn("source:lobsters", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
