from __future__ import annotations

from datetime import UTC, datetime

from agents.ai_scout.clients.reddit_client import RedditClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


class RedditCollector(BaseCollector):
    def __init__(self, client: RedditClient, limit: int = 10) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        self._client = client
        self._limit = limit

    @classmethod
    def name(cls) -> str:
        return "reddit"

    async def collect(self) -> CollectorResult:
        started = datetime.now(UTC)
        result = await self._client.fetch_posts(self._limit)
        finished = datetime.now(UTC)
        if not result.success:
            return CollectorResult(
                self.name(), CollectorStatus.FAILED, started, finished,
                errors=(result.error_message or "Reddit client failed",),
            )
        items = tuple(self._to_source_item(post, finished) for post in result.posts)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, finished, items=items)

    @staticmethod
    def _to_source_item(post, collected_at: datetime) -> SourceItem:
        tags = ("reddit",)
        return SourceItem(
            source="reddit",
            external_id=post.id,
            collected_at=collected_at,
            payload={
                "title": post.title,
                "url": post.url or f"https://www.reddit.com{post.permalink}",
                "summary": post.selftext,
                "published_at": None,
                "tags": tags,
                "author": post.author,
                "score": post.score,
            },
            metadata={"published_at": None, "tags": tags, "permalink": post.permalink},
        )
