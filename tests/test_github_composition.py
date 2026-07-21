import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.clients.github_client import GitHubClient


class GitHubCompositionTests(unittest.TestCase):
    def test_injected_github_client_registers_collector_factory(self):
        async def request(*_):
            return {"items": []}
        scout = AIScout(
            output=io.StringIO(), rss_enabled=False,
            github_client=GitHubClient(2, request), github_max_items=4,
        )
        collector = scout._collector_registry.create("github_trending", max_items=4)
        self.assertEqual(collector.name(), "github_trending")

    def test_token_is_optional_and_public_request_factory_is_injected(self):
        calls = []
        async def request(*args):
            calls.append(args)
            return {"items": []}
        scout = AIScout(output=io.StringIO(), rss_enabled=False, github_request=request)
        collector = scout._collector_registry.create("github_trending", max_items=2)
        self.assertEqual(collector.name(), "github_trending")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
