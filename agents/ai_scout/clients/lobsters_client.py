from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, str], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class LobstersItem:
    short_id: str
    title: str
    url: str
    description: str | None
    submitter_user: str | None
    tags: tuple[str, ...]
    created_at: str | None


@dataclass(frozen=True, slots=True)
class LobstersResult:
    success: bool
    items: tuple[LobstersItem, ...]
    error_message: str | None
    status_code: int | None = None


class LobstersClient:
    API_URL = "https://lobste.rs/newest.json"

    def __init__(self, timeout_seconds: float, request: HttpRequest) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout, self._request = timeout_seconds, request

    async def fetch_new(self, max_items: int = 10) -> LobstersResult:
        if max_items <= 0:
            return LobstersResult(False, (), "max_items must be positive")
        try:
            response = await self._request(self.API_URL, {"Accept": "application/json"}, {}, self._timeout)
            status, payload = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return LobstersResult(False, (), "Lobsters HTTP request failed", status)
            if not isinstance(payload, list):
                return LobstersResult(False, (), "invalid Lobsters response", status)
            items = tuple(self._parse(item) for item in payload[:max_items] if isinstance(item, dict) and self._valid(item))
            return LobstersResult(True, items, None, status)
        except TimeoutError:
            return LobstersResult(False, (), "Lobsters request timed out")
        except Exception as exc:
            return LobstersResult(False, (), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int):
            return response[0], response[1]
        return None, response

    @staticmethod
    def _valid(item: dict[str, Any]) -> bool:
        return all(isinstance(item.get(k), str) for k in ("short_id", "title", "url"))

    @staticmethod
    def _parse(item: dict[str, Any]) -> LobstersItem:
        tags = item.get("tags") or []
        return LobstersItem(item["short_id"], item["title"], item["url"], item.get("description"), item.get("submitter_user"), tuple(t for t in tags if isinstance(t, str)), item.get("created_at"))
