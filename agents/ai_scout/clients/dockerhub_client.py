from collections.abc import Awaitable, Callable, Mapping
from typing import Any
HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Awaitable[Any]]
class DockerHubClient:
    URL = "https://hub.docker.com/v2/repositories/library/"
    def __init__(self, timeout: float, request: HttpRequest):
        if timeout <= 0: raise ValueError("timeout must be positive")
        self.timeout, self.request = timeout, request
    async def fetch_repositories(self, limit: int):
        try:
            response = await self.request(self.URL, {}, {"page_size": str(limit), "ordering": "-last_updated"}, self.timeout)
            status, data = response if isinstance(response, tuple) and len(response) == 2 else (None, response)
            rows = data.get("results") if isinstance(data, dict) else None
            if status is not None and not 200 <= status < 300 or not isinstance(rows, list): return ()
            return tuple(x for x in rows[:limit] if isinstance(x, dict) and x.get("name"))
        except Exception: return ()
