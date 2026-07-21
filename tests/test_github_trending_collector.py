import asyncio
import unittest
from datetime import UTC, datetime

from agents.ai_scout.collectors.github import GitHubTrendingCollector
from agents.ai_scout.clients.github_client import GitHubRepository, GitHubResult
from core.collector.types import CollectorStatus


REPO = GitHubRepository("repo", "org/repo", "https://github.com/org/repo", "A project", 10, "Python")


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.max_items = None

    async def fetch_trending(self, max_items):
        self.max_items = max_items
        return self.result


class GitHubTrendingCollectorTests(unittest.TestCase):
    def test_maps_repository_and_respects_limit(self):
        client = FakeClient(GitHubResult(True, (REPO,), None))
        result = asyncio.run(GitHubTrendingCollector(client, 3).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(client.max_items, 3)
        item = result.items[0]
        self.assertEqual(item.source, "github")
        self.assertEqual(item.external_id, "org/repo")
        self.assertEqual(item.payload["title"], "org/repo")
        self.assertEqual(item.payload["url"], REPO.html_url)
        self.assertEqual(item.payload["summary"], "A project")
        self.assertIn("Python", item.payload["tags"])
        self.assertIsNone(item.payload["published_at"])

    def test_client_error_returns_empty_failed_result(self):
        client = FakeClient(GitHubResult(False, (), "unavailable"))
        result = asyncio.run(GitHubTrendingCollector(client).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())
        self.assertIn("unavailable", result.errors)


if __name__ == "__main__":
    unittest.main()
