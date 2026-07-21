from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


HttpRequest = Callable[[str, float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class HackerNewsItem:
    id: int
    title: str
    url: str | None
    text: str | None
    by: str | None
    score: int
    time: int | None


@dataclass(frozen=True, slots=True)
class HackerNewsResult:
    success: bool
    items: tuple[HackerNewsItem, ...]
    errors: tuple[str, ...]


class HackerNewsClient:
    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, timeout_seconds: float, request: HttpRequest) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout = timeout_seconds
        self._request = request

    async def fetch_top_stories(self, max_items: int = 10) -> HackerNewsResult:
        if max_items <= 0:
            return HackerNewsResult(False, (), ("max_items must be positive",))
        try:
            response = await self._request(f"{self.BASE_URL}/topstories.json", self._timeout)
            status, ids = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return HackerNewsResult(False, (), ("Hacker News HTTP request failed",))
            if not isinstance(ids, list):
                return HackerNewsResult(False, (), ("invalid top stories response",))
        except TimeoutError:
            return HackerNewsResult(False, (), ("Hacker News request timed out",))
        except Exception as exc:
            return HackerNewsResult(False, (), (f"{type(exc).__name__}: {exc}",))

        items: list[HackerNewsItem] = []
        errors: list[str] = []
        for item_id in ids[:max_items]:
            if not isinstance(item_id, int):
                errors.append("invalid story id")
                continue
            try:
                response = await self._request(f"{self.BASE_URL}/item/{item_id}.json", self._timeout)
                status, payload = self._unpack(response)
                if status is not None and not 200 <= status < 300:
                    errors.append(f"item {item_id}: HTTP error")
                elif isinstance(payload, dict) and self._valid(payload):
                    items.append(self._parse(payload))
                else:
                    errors.append(f"item {item_id}: invalid response")
            except TimeoutError:
                errors.append(f"item {item_id}: timeout")
            except Exception as exc:
                errors.append(f"item {item_id}: {type(exc).__name__}")
        return HackerNewsResult(bool(items) or not errors, tuple(items), tuple(errors))

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int):
            return response[0], response[1]
        return None, response

    @staticmethod
    def _valid(data: dict[str, Any]) -> bool:
        return isinstance(data.get("id"), int) and isinstance(data.get("title"), str)

    @staticmethod
    def _parse(data: dict[str, Any]) -> HackerNewsItem:
        return HackerNewsItem(data["id"], data["title"], data.get("url"), data.get("text"), data.get("by"), int(data.get("score", 0)), data.get("time"))
