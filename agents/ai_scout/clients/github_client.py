from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, str], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class GitHubRepository:
    name: str
    full_name: str
    html_url: str
    description: str | None
    stars: int
    language: str | None


@dataclass(frozen=True, slots=True)
class GitHubResult:
    success: bool
    repositories: tuple[GitHubRepository, ...]
    error_message: str | None
    status_code: int | None = None


class GitHubClient:
    API_URL = "https://api.github.com/search/repositories"
    DEFAULT_MAX_ITEMS = 10

    def __init__(self, timeout_seconds: float, request: HttpRequest, token: str | None = None) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout = timeout_seconds
        self._request = request
        self._token = token

    async def fetch_trending(self, max_items: int = DEFAULT_MAX_ITEMS) -> GitHubResult:
        if max_items <= 0:
            return GitHubResult(False, (), "max_items must be positive")
        params = {
            "q": "stars:>0",
            "sort": "stars",
            "order": "desc",
            "per_page": str(max_items),
        }
        try:
            response = await self._request(
                self.API_URL,
                {
                    "Accept": "application/vnd.github+json",
                    **({"Authorization": f"Bearer {self._token}"} if self._token else {}),
                },
                params,
                self._timeout,
            )
            status, payload = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return GitHubResult(False, (), "GitHub HTTP request failed", status)
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                return GitHubResult(False, (), "invalid GitHub response", status)
            repositories = tuple(
                self._parse(item) for item in payload["items"][:max_items]
                if isinstance(item, dict) and self._valid(item)
            )
            return GitHubResult(True, repositories, None, status)
        except TimeoutError:
            return GitHubResult(False, (), "GitHub request timed out")
        except Exception as exc:
            return GitHubResult(False, (), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int):
            return response[0], response[1]
        return None, response

    @staticmethod
    def _valid(item: dict[str, Any]) -> bool:
        return all(isinstance(item.get(key), str) for key in ("name", "full_name", "html_url"))

    @staticmethod
    def _parse(item: dict[str, Any]) -> GitHubRepository:
        return GitHubRepository(
            name=item["name"], full_name=item["full_name"], html_url=item["html_url"],
            description=item.get("description") if isinstance(item.get("description"), str) else None,
            stars=int(item.get("stargazers_count", 0)),
            language=item.get("language") if isinstance(item.get("language"), str) else None,
        )
