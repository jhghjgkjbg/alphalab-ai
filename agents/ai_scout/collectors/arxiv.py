from __future__ import annotations

from datetime import UTC, datetime

from agents.ai_scout.clients.arxiv_client import ArxivClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


class ArxivCollector(BaseCollector):
    def __init__(self, client: ArxivClient, search_query: str, max_items: int = 10) -> None:
        if not search_query:
            raise ValueError("search_query must not be empty")
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        self._client, self._query, self._max_items = client, search_query, max_items

    @classmethod
    def name(cls) -> str:
        return "arxiv"

    async def collect(self) -> CollectorResult:
        started = datetime.now(UTC)
        result = await self._client.search(self._query, self._max_items)
        finished = datetime.now(UTC)
        if not result.success:
            return CollectorResult(self.name(), CollectorStatus.FAILED, started, finished, errors=(result.error_message or "arXiv client failed",))
        items = tuple(SourceItem(
            source="arxiv", external_id=paper.id, collected_at=finished,
            payload={"title": paper.title, "url": paper.url, "summary": paper.summary, "published_at": paper.published_at, "tags": paper.categories, "authors": paper.authors},
            metadata={"published_at": paper.published_at, "tags": paper.categories},
        ) for paper in result.items)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, finished, items=items)
