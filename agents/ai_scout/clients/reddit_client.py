from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, str], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class RedditPost:
    id: str
    title: str
    url: str
    permalink: str
    selftext: str
    author: str | None
    score: int


@dataclass(frozen=True, slots=True)
class RedditResult:
    success: bool
    posts: tuple[RedditPost, ...]
    error_message: str | None
    status_code: int | None = None


class RedditClient:
    def __init__(self, subreddit: str, timeout_seconds: float, request: HttpRequest) -> None:
        if not subreddit or "/" in subreddit:
            raise ValueError("subreddit must be a simple name")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._subreddit = subreddit
        self._timeout = timeout_seconds
        self._request = request

    async def fetch_posts(self, limit: int = 10) -> RedditResult:
        if limit <= 0:
            return RedditResult(False, (), "limit must be positive")
        url = f"https://www.reddit.com/r/{quote(self._subreddit)}/new.json"
        try:
            response = await self._request(
                url,
                {"Accept": "application/json", "User-Agent": "AlphaLabAI/0.1"},
                {"limit": str(limit)},
                self._timeout,
            )
            status, payload = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return RedditResult(False, (), "Reddit HTTP request failed", status)
            children = payload.get("data", {}).get("children") if isinstance(payload, dict) else None
            if not isinstance(children, list):
                return RedditResult(False, (), "invalid Reddit response", status)
            posts = tuple(
                self._parse(child["data"])
                for child in children[:limit]
                if isinstance(child, dict) and isinstance(child.get("data"), dict)
                and self._valid(child["data"])
            )
            return RedditResult(True, posts, None, status)
        except TimeoutError:
            return RedditResult(False, (), "Reddit request timed out")
        except Exception as exc:
            return RedditResult(False, (), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int):
            return response[0], response[1]
        return None, response

    @staticmethod
    def _valid(data: dict[str, Any]) -> bool:
        return all(isinstance(data.get(key), str) for key in ("id", "title", "permalink"))

    @staticmethod
    def _parse(data: dict[str, Any]) -> RedditPost:
        return RedditPost(
            id=data["id"], title=data["title"],
            url=data.get("url") if isinstance(data.get("url"), str) else "",
            permalink=data["permalink"],
            selftext=data.get("selftext") if isinstance(data.get("selftext"), str) else "",
            author=data.get("author") if isinstance(data.get("author"), str) else None,
            score=int(data.get("score", 0)),
        )
