from datetime import UTC, datetime
from agents.ai_scout.clients.gitlab_client import GitLabClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem
class GitLabCollector(BaseCollector):
    def __init__(self, client: GitLabClient, max_items=10): self.client, self.max_items = client, max_items
    @classmethod
    def name(cls): return "gitlab"
    async def collect(self):
        started=datetime.now(UTC); rows=await self.client.fetch_projects(self.max_items); now=datetime.now(UTC)
        items=tuple(SourceItem(source="gitlab", external_id=str(x["id"]), collected_at=now, payload={"title":x.get("name_with_namespace",x.get("name","")),"url":x["web_url"],"summary":x.get("description") or "","stars":x.get("star_count",0),"published_at":x.get("last_activity_at"),"category":"Open Source"}, metadata={"published_at":x.get("last_activity_at")}) for x in rows)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, now, items=items)
