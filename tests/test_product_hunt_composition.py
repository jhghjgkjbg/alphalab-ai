import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.product_hunt_client import ProductHuntClient


class ProductHuntCompositionTests(unittest.TestCase):
    def test_injected_client_registers_collector(self):
        async def request(*_): return {"data": {"posts": {"nodes": []}}}
        scout = AIScout(output=io.StringIO(), rss_enabled=False, product_hunt_client=ProductHuntClient("x", 1, request))
        collector = scout._collector_registry.create("product_hunt", max_items=2)
        self.assertEqual(collector.name(), "product_hunt")

    def test_source_and_scheduler_are_registered_without_network(self):
        async def request(*_): return {"data": {"posts": {"nodes": []}}}
        scout = AIScout(output=io.StringIO(), rss_enabled=False, product_hunt_request=request, product_hunt_token="x")
        self.assertIn("product_hunt", scout._source_manager._source_registry._sources)
        self.assertIn("source:product_hunt", {task.task_id for task in scout._scheduler.tasks()})


if __name__ == "__main__": unittest.main()
