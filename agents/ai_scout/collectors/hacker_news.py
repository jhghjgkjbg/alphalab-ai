import asyncio
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem
from agents.ai_scout.clients.hacker_news_client import HackerNewsClient


FetchJson = Callable[[str, float], Any]


class HackerNewsCollector(BaseCollector):
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    STORY_LIMIT = 10

    def __init__(
        self,
        *,
        timeout: float = 5.0,
        fetch_json: FetchJson | None = None,
        client: HackerNewsClient | None = None,
        max_items: int | None = None,
    ) -> None:
        self._timeout = timeout
        self._fetch_json = fetch_json or self._default_fetch_json
        self._client = client
        self._max_items = max_items or self.STORY_LIMIT

    @classmethod
    def name(cls) -> str:
        return "hacker_news"

    async def collect(self) -> CollectorResult:
        started_at = datetime.now(UTC)
        if self._client is not None:
            result = await self._client.fetch_top_stories(self._max_items)
            finished_at = datetime.now(UTC)
            if not result.success:
                return CollectorResult(self.name(), CollectorStatus.FAILED, started_at, finished_at, errors=result.errors)
            items = tuple(
                SourceItem(
                    source="hacker_news", external_id=str(item.id), collected_at=finished_at,
                    payload={
                        "title": item.title,
                        "url": item.url or f"https://news.ycombinator.com/item?id={item.id}",
                        "summary": item.text or "",
                        "published_at": datetime.fromtimestamp(item.time, UTC) if item.time else None,
                        "tags": ("hacker_news",),
                        "author": item.by,
                        "score": item.score,
                    },
                    metadata={"published_at": item.time, "tags": ("hacker_news",)},
                )
                for item in result.items
            )
            return CollectorResult(self.name(), CollectorStatus.SUCCESS, started_at, finished_at, items=items)
        items: list[SourceItem] = []
        errors: list[str] = []

        try:
            top_story_ids = await asyncio.to_thread(
                self._fetch_json,
                f"{self.BASE_URL}/topstories.json",
                self._timeout,
            )
            if not isinstance(top_story_ids, list):
                raise ValueError("top stories response must be a list")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            return CollectorResult(
                collector_name=self.name(),
                status=CollectorStatus.FAILED,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                errors=(f"top stories request failed: {exc}",),
            )

        for story_id in top_story_ids[: self.STORY_LIMIT]:
            try:
                response = await asyncio.to_thread(
                    self._fetch_json,
                    f"{self.BASE_URL}/item/{story_id}.json",
                    self._timeout,
                )
                items.append(self.to_source_item(response))
            except (
                HTTPError,
                URLError,
                TimeoutError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ) as exc:
                errors.append(f"item {story_id} skipped: {exc}")

        if errors:
            status = CollectorStatus.PARTIAL if items else CollectorStatus.FAILED
        else:
            status = CollectorStatus.SUCCESS

        return CollectorResult(
            collector_name=self.name(),
            status=status,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            items=tuple(items),
            errors=tuple(errors),
        )

    @classmethod
    def to_source_item(cls, response: Any) -> SourceItem:
        if not isinstance(response, Mapping):
            raise TypeError("item response must be an object")

        item_id = response.get("id")
        title = response.get("title")
        if not isinstance(item_id, int):
            raise ValueError("item id is missing or invalid")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("item title is missing or invalid")

        url = response.get("url")
        if not isinstance(url, str) or not url:
            url = f"https://news.ycombinator.com/item?id={item_id}"

        return SourceItem(
            source=cls.name(),
            external_id=str(item_id),
            collected_at=datetime.now(UTC),
            payload={
                "title": title,
                "url": url,
            },
            metadata={
                "author": response.get("by"),
                "score": response.get("score"),
                "published_at": response.get("time"),
                "type": response.get("type"),
            },
        )

    @staticmethod
    def _default_fetch_json(url: str, timeout: float) -> Any:
        request = Request(url, headers={"User-Agent": "AlphaLab-AI-Scout/0.1"})
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
