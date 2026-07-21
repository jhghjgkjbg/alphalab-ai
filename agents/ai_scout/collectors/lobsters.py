from __future__ import annotations

from datetime import UTC, datetime

from agents.ai_scout.clients.lobsters_client import LobstersClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


class LobstersCollector(BaseCollector):
    def __init__(self, client: LobstersClient, max_items: int = 10) -> None:
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        self._client, self._max_items = client, max_items

    @classmethod
    def name(cls) -> str:
        return "lobsters"

    async def collect(self) -> CollectorResult:
        started = datetime.now(UTC)
        result = await self._client.fetch_new(self._max_items)
        finished = datetime.now(UTC)
        if not result.success:
            return CollectorResult(self.name(), CollectorStatus.FAILED, started, finished, errors=(result.error_message or "Lobsters client failed",))
        items = tuple(SourceItem(
            source="lobsters", external_id=post.short_id, collected_at=finished,
            payload={"title": post.title, "url": post.url, "summary": post.description or "", "published_at": post.created_at, "tags": post.tags, "author": post.submitter_user},
            metadata={"published_at": post.created_at, "tags": post.tags},
        ) for post in result.items)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, finished, items=items)
