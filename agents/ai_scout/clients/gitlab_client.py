from collections.abc import Awaitable, Callable, Mapping
from typing import Any
HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Awaitable[Any]]
class GitLabClient:
    URL = "https://gitlab.com/api/v4/projects"
    def __init__(self, timeout: float, request: HttpRequest):
        if timeout <= 0: raise ValueError("timeout must be positive")
        self.timeout, self.request = timeout, request
    async def fetch_projects(self, limit: int):
        try:
            response = await self.request(self.URL, {}, {"order_by": "star_count", "sort": "desc", "per_page": str(limit)}, self.timeout)
            status, data = response if isinstance(response, tuple) and len(response) == 2 else (None, response)
            if status is not None and not 200 <= status < 300 or not isinstance(data, list): return ()
            return tuple(x for x in data[:limit] if isinstance(x, dict) and x.get("id") and x.get("web_url"))
        except Exception: return ()
