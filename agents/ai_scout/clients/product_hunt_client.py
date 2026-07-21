from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ProductHuntItem:
    id: str
    name: str
    url: str
    tagline: str
    description: str | None
    votes_count: int
    topics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductHuntResult:
    success: bool
    items: tuple[ProductHuntItem, ...]
    error_message: str | None
    status_code: int | None = None


class ProductHuntClient:
    API_URL = "https://api.producthunt.com/v2/api/graphql"

    def __init__(self, token: str, timeout_seconds: float, request: HttpRequest) -> None:
        if not token:
            raise ValueError("token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._token = token
        self._timeout = timeout_seconds
        self._request = request

    async def fetch_new_products(self, max_items: int = 10) -> ProductHuntResult:
        if max_items <= 0:
            return ProductHuntResult(False, (), "max_items must be positive")
        payload = {
            "query": "query($first:Int!){posts(first:$first, order:NEWEST){nodes{id name url tagline description votesCount topics{name}}}}",
            "variables": {"first": max_items},
        }
        try:
            response = await self._request(
                self.API_URL,
                {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                payload,
                self._timeout,
            )
            status, data = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return ProductHuntResult(False, (), "Product Hunt HTTP request failed", status)
            if not isinstance(data, dict) or data.get("errors"):
                return ProductHuntResult(False, (), "invalid Product Hunt response", status)
            nodes = data.get("data", {}).get("posts", {}).get("nodes")
            if not isinstance(nodes, list):
                return ProductHuntResult(False, (), "invalid Product Hunt response", status)
            items = tuple(self._parse(node) for node in nodes[:max_items] if isinstance(node, dict) and self._valid(node))
            return ProductHuntResult(True, items, None, status)
        except TimeoutError:
            return ProductHuntResult(False, (), "Product Hunt request timed out")
        except Exception as exc:
            return ProductHuntResult(False, (), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int):
            return response[0], response[1]
        return None, response

    @staticmethod
    def _valid(node: dict[str, Any]) -> bool:
        return all(isinstance(node.get(k), str) for k in ("id", "name", "url", "tagline"))

    @staticmethod
    def _parse(node: dict[str, Any]) -> ProductHuntItem:
        topics = node.get("topics") or []
        names = tuple(t["name"] for t in topics if isinstance(t, dict) and isinstance(t.get("name"), str))
        return ProductHuntItem(node["id"], node["name"], node["url"], node["tagline"], node.get("description"), int(node.get("votesCount", 0)), names)
