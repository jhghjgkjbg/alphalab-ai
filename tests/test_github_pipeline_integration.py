import asyncio
import unittest

from agents.ai_scout.clients.github_client import GitHubClient
from agents.ai_scout.collectors.github import GitHubTrendingCollector
from core.collector.types import CollectorStatus


class GitHubPipelineIntegrationTests(unittest.TestCase):
    def test_mock_http_flows_into_source_items(self):
        calls = []

        async def request(url, headers, params, timeout):
            calls.append((url, headers, params, timeout))
            return {"items": [
                {"name": "alpha", "full_name": "org/alpha",
                 "html_url": "https://github.com/org/alpha", "description": "Alpha project",
                 "stargazers_count": 100, "language": "Python"},
                {"name": "beta", "full_name": "org/beta",
                 "html_url": "https://github.com/org/beta", "description": None,
                 "stargazers_count": 50, "language": "Go"},
            ]}

        collector = GitHubTrendingCollector(GitHubClient(3, request), max_items=1)
        result = asyncio.run(collector.collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.payload["title"], "org/alpha")
        self.assertEqual(item.payload["url"], "https://github.com/org/alpha")
        self.assertEqual(item.payload["summary"], "Alpha project")
        self.assertEqual(item.source, "github")
        self.assertIsNone(item.payload["published_at"])
        self.assertEqual(item.payload["tags"], ("github", "Python"))
        self.assertEqual(calls[0][2]["per_page"], "1")

    def test_http_error_and_empty_response(self):
        async def error(*_):
            return (503, {"message": "unavailable"})
        result = asyncio.run(GitHubTrendingCollector(GitHubClient(1, error)).collect())
        self.assertEqual(result.status, CollectorStatus.FAILED)
        self.assertEqual(result.items, ())

        async def empty(*_):
            return {"items": []}
        result = asyncio.run(GitHubTrendingCollector(GitHubClient(1, empty)).collect())
        self.assertEqual(result.status, CollectorStatus.SUCCESS)
        self.assertEqual(result.items, ())


if __name__ == "__main__":
    unittest.main()
