from __future__ import annotations

from datetime import UTC, datetime

from agents.ai_scout.clients.github_client import GitHubClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


class GitHubTrendingCollector(BaseCollector):
    def __init__(self, client: GitHubClient, max_items: int = 10) -> None:
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        self._client = client
        self._max_items = max_items

    @classmethod
    def name(cls) -> str:
        return "github_trending"

    async def collect(self) -> CollectorResult:
        started = datetime.now(UTC)
        result = await self._client.fetch_trending(self._max_items)
        finished = datetime.now(UTC)
        if not result.success:
            return CollectorResult(
                self.name(), CollectorStatus.FAILED, started, finished,
                errors=(result.error_message or "GitHub client failed",),
            )
        collected_at = finished
        items = tuple(self._to_source_item(repo, collected_at) for repo in result.repositories)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, finished, items=items)

    @staticmethod
    def _to_source_item(repo, collected_at: datetime) -> SourceItem:
        tags = ["github"]
        if repo.language:
            tags.append(repo.language)
        return SourceItem(
            source="github",
            external_id=repo.full_name,
            collected_at=collected_at,
            payload={
                "title": repo.full_name,
                "url": repo.html_url,
                "summary": repo.description or "",
                "published_at": None,
                "tags": tuple(tags),
                "stars": repo.stars,
            },
            metadata={"published_at": None, "tags": tuple(tags)},
        )
