from datetime import UTC, datetime
from agents.ai_scout.clients.pypi_client import PyPIClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem
class PyPICollector(BaseCollector):
    def __init__(self, client: PyPIClient, packages: tuple[str, ...], max_items: int = 10) -> None:
        if max_items <= 0: raise ValueError("max_items must be positive")
        self._client, self._packages, self._max_items = client, packages, max_items
    @classmethod
    def name(cls): return "pypi"
    async def collect(self):
        started = datetime.now(UTC)
        try: rows = await self._client.fetch_packages(self._packages)
        except Exception as exc: return CollectorResult(self.name(), CollectorStatus.FAILED, started, datetime.now(UTC), errors=(type(exc).__name__,))
        items = tuple(SourceItem(source="pypi", external_id=f"{r['name']}@{r['version']}", collected_at=datetime.now(UTC), payload={"title": f"{r['name']} {r['version']}", "url": r["url"], "summary": r["summary"], "published_at": r["published_at"], "category": "Developer Tools"}, metadata={"published_at": r["published_at"], "version": r["version"]}) for r in rows[:self._max_items])
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, datetime.now(UTC), items=items)
