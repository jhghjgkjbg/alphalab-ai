import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.arxiv_client import ArxivClient


class ArxivCompositionTests(unittest.TestCase):
    def test_injected_client_registers_collector(self):
        async def request(*_): return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        scout = AIScout(output=io.StringIO(), rss_enabled=False, arxiv_client=ArxivClient(1, request), arxiv_search_query="cat:cs.AI")
        self.assertEqual(scout._collector_registry.create("arxiv").name(), "arxiv")

    def test_source_and_scheduler_are_registered(self):
        async def request(*_): return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        scout = AIScout(output=io.StringIO(), rss_enabled=False, arxiv_request=request)
        self.assertIn("arxiv", scout._source_manager._source_registry._sources)
        self.assertIn("source:arxiv", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
