from __future__ import annotations
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, str], float], Awaitable[Any]]

class PyPIClient:
    BASE_URL = "https://pypi.org/pypi"
    def __init__(self, timeout_seconds: float, request: HttpRequest) -> None:
        if timeout_seconds <= 0: raise ValueError("timeout_seconds must be positive")
        self._timeout, self._request = timeout_seconds, request
    async def fetch_packages(self, packages: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
        results = []
        for package in packages:
            try:
                response = await self._request(f"{self.BASE_URL}/{package}/json", {}, {}, self._timeout)
                status, data = response if isinstance(response, tuple) and len(response) == 2 else (None, response)
                if status is not None and not 200 <= status < 300 or not isinstance(data, dict): continue
                info = data.get("info") or {}; version = str(info.get("version") or "").strip()
                if not version: continue
                releases = data.get("releases") or {}; files = releases.get(version) or []
                uploaded = next((f.get("upload_time_iso_8601") for f in files if isinstance(f, dict) and f.get("upload_time_iso_8601")), None)
                results.append({"name": str(info.get("name") or package), "version": version, "summary": str(info.get("summary") or ""), "url": str(info.get("project_url") or f"https://pypi.org/project/{package}/"), "published_at": uploaded})
            except Exception:
                continue
        return tuple(results)
