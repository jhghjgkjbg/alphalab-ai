from __future__ import annotations

from datetime import UTC, datetime

from agents.ai_scout.clients.devto_client import DevToClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


class DevToCollector(BaseCollector):
    def __init__(self, client: DevToClient, max_items: int = 10, tag: str | None = None) -> None:
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        self._client, self._max_items, self._tag = client, max_items, tag

    @classmethod
    def name(cls) -> str:
        return "devto"

    async def collect(self) -> CollectorResult:
        started = datetime.now(UTC)
        result = await self._client.fetch_articles(self._max_items, self._tag)
        finished = datetime.now(UTC)
        if not result.success:
            return CollectorResult(self.name(), CollectorStatus.FAILED, started, finished, errors=(result.error_message or "Dev.to client failed",))
        items = tuple(SourceItem(
            source="devto", external_id=str(article.id), collected_at=finished,
            payload={"title": article.title, "url": article.url, "summary": article.description or "", "published_at": article.published_at, "tags": article.tag_list, "reactions": article.positive_reactions_count},
            metadata={"published_at": article.published_at, "tags": article.tag_list},
        ) for article in result.articles)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, finished, items=items)
