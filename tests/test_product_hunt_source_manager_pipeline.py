import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.product_hunt_client import ProductHuntItem, ProductHuntResult


class FakeProductHuntClient:
    async def fetch_new_products(self, max_items):
        return ProductHuntResult(True, (ProductHuntItem("1", "Tool", "https://tool", "Tag", None, 1, ("AI",)),), None)


class ProductHuntSourceManagerTests(unittest.TestCase):
    def test_product_hunt_runs_through_source_manager(self):
        scout = AIScout(output=io.StringIO(), rss_enabled=False, product_hunt_client=FakeProductHuntClient())
        results = asyncio.run(scout.run_once())
        result = next(item for item in results if item.source_id == "product_hunt")
        self.assertEqual(result.collected_count, 1)
        self.assertIn("source:product_hunt", {task.task_id for task in scout._scheduler.tasks()})
        self.assertEqual(scout._collector_registry.create("product_hunt").name(), "product_hunt")


if __name__ == "__main__": unittest.main()
