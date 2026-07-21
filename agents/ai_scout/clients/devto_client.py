from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, str], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class DevToArticle:
    id: int
    title: str
    url: str
    description: str | None
    published_at: str | None
    tag_list: tuple[str, ...]
    positive_reactions_count: int


@dataclass(frozen=True, slots=True)
class DevToResult:
    success: bool
    articles: tuple[DevToArticle, ...]
    error_message: str | None
    status_code: int | None = None


class DevToClient:
    API_URL = "https://dev.to/api/articles"

    def __init__(self, timeout_seconds: float, request: HttpRequest) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout = timeout_seconds
        self._request = request

    async def fetch_articles(self, max_items: int = 10, tag: str | None = None) -> DevToResult:
        if max_items <= 0:
            return DevToResult(False, (), "max_items must be positive")
        params = {"per_page": str(max_items)}
        if tag:
            params["tag"] = tag
        try:
            response = await self._request(self.API_URL, {"Accept": "application/json"}, params, self._timeout)
            status, payload = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return DevToResult(False, (), "Dev.to HTTP request failed", status)
            if not isinstance(payload, list):
                return DevToResult(False, (), "invalid Dev.to response", status)
            articles = tuple(self._parse(item) for item in payload[:max_items] if isinstance(item, dict) and self._valid(item))
            return DevToResult(True, articles, None, status)
        except TimeoutError:
            return DevToResult(False, (), "Dev.to request timed out")
        except Exception as exc:
            return DevToResult(False, (), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int):
            return response[0], response[1]
        return None, response

    @staticmethod
    def _valid(item: dict[str, Any]) -> bool:
        return isinstance(item.get("id"), int) and all(isinstance(item.get(k), str) for k in ("title", "url"))

    @staticmethod
    def _parse(item: dict[str, Any]) -> DevToArticle:
        tags = item.get("tag_list") or []
        return DevToArticle(item["id"], item["title"], item["url"], item.get("description"), item.get("published_at"), tuple(x for x in tags if isinstance(x, str)), int(item.get("positive_reactions_count", 0)))
