import asyncio
import unittest

from agents.ai_scout.clients.github_client import GitHubClient


ITEM = {
    "name": "repo", "full_name": "org/repo", "html_url": "https://github.com/org/repo",
    "description": "desc", "stargazers_count": 123, "language": "Python",
}


class GitHubClientTests(unittest.TestCase):
    def test_fetches_and_limits_trending_repositories(self):
        calls = []

        async def request(url, headers, params, timeout):
            calls.append((url, headers, params, timeout))
            return {"items": [ITEM, {**ITEM, "name": "repo2"}]}

        result = asyncio.run(GitHubClient(4, request).fetch_trending(1))
        self.assertTrue(result.success)
        self.assertEqual(len(result.repositories), 1)
        self.assertEqual(calls[0][2]["per_page"], "1")

    def test_http_timeout_and_invalid_response(self):
        async def http_error(*_):
            return (500, {"message": "error"})
        result = asyncio.run(GitHubClient(1, http_error).fetch_trending())
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 500)

        async def timeout(*_):
            raise TimeoutError()
        result = asyncio.run(GitHubClient(1, timeout).fetch_trending())
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error_message)

        async def invalid(*_):
            return {"items": [{"bad": True}]}
        result = asyncio.run(GitHubClient(1, invalid).fetch_trending())
        self.assertTrue(result.success)
        self.assertEqual(result.repositories, ())

    def test_rejects_invalid_limit(self):
        async def request(*_):
            raise AssertionError("network must not be called")
        result = asyncio.run(GitHubClient(1, request).fetch_trending(0))
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
