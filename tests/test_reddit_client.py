import asyncio
import unittest

from agents.ai_scout.clients.reddit_client import RedditClient


POST = {"id": "abc", "title": "Post", "url": "https://example.com", "permalink": "/r/test/comments/abc/post", "selftext": "Body", "author": "user", "score": 9}


class RedditClientTests(unittest.TestCase):
    def test_fetches_posts_with_limit(self):
        calls = []
        async def request(url, headers, params, timeout):
            calls.append((url, params, timeout))
            return {"data": {"children": [{"data": POST}, {"data": {**POST, "id": "def"}}]}}
        result = asyncio.run(RedditClient("python", 2, request).fetch_posts(1))
        self.assertTrue(result.success)
        self.assertEqual(len(result.posts), 1)
        self.assertEqual(result.posts[0].title, "Post")
        self.assertEqual(calls[0][1]["limit"], "1")

    def test_http_invalid_json_timeout_and_invalid_limit(self):
        async def error(*_): return (500, {})
        result = asyncio.run(RedditClient("x", 1, error).fetch_posts())
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 500)

        async def invalid(*_): return {"bad": True}
        result = asyncio.run(RedditClient("x", 1, invalid).fetch_posts())
        self.assertFalse(result.success)

        async def timeout(*_): raise TimeoutError()
        result = asyncio.run(RedditClient("x", 1, timeout).fetch_posts())
        self.assertIn("timed out", result.error_message)

        async def network(*_): raise AssertionError("network")
        result = asyncio.run(RedditClient("x", 1, network).fetch_posts(0))
        self.assertFalse(result.success)


if __name__ == "__main__": unittest.main()
