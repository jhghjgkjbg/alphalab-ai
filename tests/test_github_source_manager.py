import asyncio
import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector


class GitHubSourceManagerTests(unittest.TestCase):
    def test_github_source_is_registered_and_runs(self):
        def hn(url, _):
            return [] if url.endswith("topstories.json") else {}

        async def github(*_):
            return {"items": [{"name": "x", "full_name": "o/x", "html_url": "https://github.com/o/x", "description": "x", "stargazers_count": 1, "language": "Python"}]}

        scout = AIScout(
            collector=HackerNewsCollector(fetch_json=hn), output=io.StringIO(),
            rss_enabled=False, github_request=github, github_max_items=1,
        )
        results = asyncio.run(scout.run_once())
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].source_id, "github")
        self.assertEqual(results[1].collected_count, 1)


if __name__ == "__main__":
    unittest.main()
