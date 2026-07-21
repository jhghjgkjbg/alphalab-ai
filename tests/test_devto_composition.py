import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.devto_client import DevToClient


class DevToCompositionTests(unittest.TestCase):
    def test_injected_client_registers_devto_collector(self):
        async def request(*_): return []
        scout = AIScout(output=io.StringIO(), rss_enabled=False, devto_client=DevToClient(1, request), devto_tag="python")
        self.assertEqual(scout._collector_registry.create("devto", max_items=2).name(), "devto")

    def test_devto_source_and_scheduler_are_registered(self):
        async def request(*_): return []
        scout = AIScout(output=io.StringIO(), rss_enabled=False, devto_request=request)
        self.assertIn("devto", scout._source_manager._source_registry._sources)
        self.assertIn("source:devto", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
