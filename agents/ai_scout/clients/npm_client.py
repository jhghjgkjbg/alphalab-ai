from __future__ import annotations
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import quote

HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Awaitable[Any]]
class NpmClient:
    BASE_URL = "https://registry.npmjs.org"
    def __init__(self, timeout_seconds: float, request: HttpRequest) -> None:
        if timeout_seconds <= 0: raise ValueError("timeout_seconds must be positive")
        self._timeout, self._request = timeout_seconds, request
    async def fetch_packages(self, packages: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
        results = []
        for package in packages:
            try:
                response = await self._request(f"{self.BASE_URL}/{quote(package, safe='@/')}", {}, {}, self._timeout)
                status, data = response if isinstance(response, tuple) and len(response) == 2 else (None, response)
                if status is not None and not 200 <= status < 300 or not isinstance(data, dict): continue
                version = str((data.get("dist-tags") or {}).get("latest") or "").strip(); versions = data.get("versions") or {}
                meta = versions.get(version) if version else None
                if not version or not isinstance(meta, dict): continue
                results.append({"name": str(meta.get("name") or package), "version": version, "summary": str(meta.get("description") or ""), "url": f"https://www.npmjs.com/package/{package}", "published_at": (data.get("time") or {}).get(version), "repository": meta.get("repository")})
            except Exception:
                continue
        return tuple(results)
