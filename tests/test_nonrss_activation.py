import unittest

from agents.ai_scout.agent import AIScout
from backend.app.core.config import Settings


class NonRSSActivationTests(unittest.TestCase):
    def test_production_defaults_and_product_hunt_disabled(self):
        fields = Settings.model_fields
        self.assertTrue(fields["github_enabled"].default)
        self.assertTrue(fields["reddit_enabled"].default)
        self.assertFalse(fields["product_hunt_enabled"].default)

    def test_enabled_sources_have_stable_definitions(self):
        async def request(*_args):
            return 200, {"items": []}

        scout = AIScout(github_enabled=True, github_request=request, reddit_enabled=True, reddit_request=request, product_hunt_enabled=False)
        sources = scout._source_manager._source_registry._sources
        self.assertEqual(sources["github"].max_items, 10)
        self.assertEqual(sources["github"].metadata["category"], "Open Source")
        self.assertEqual(sources["reddit"].max_items, 10)
        self.assertEqual(sources["reddit"].metadata["category"], "AI")
        self.assertNotIn("product_hunt", sources)
        self.assertEqual(len([key for key in sources if key in {"github", "reddit", "product_hunt"}]), 2)


if __name__ == "__main__":
    unittest.main()
