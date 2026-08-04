from datetime import UTC, datetime
from agents.ai_scout.clients.dockerhub_client import DockerHubClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem
class DockerHubCollector(BaseCollector):
    def __init__(self, client: DockerHubClient, max_items=10): self.client, self.max_items = client, max_items
    @classmethod
    def name(cls): return "dockerhub"
    async def collect(self):
        started=datetime.now(UTC); rows=await self.client.fetch_repositories(self.max_items); now=datetime.now(UTC)
        items=tuple(SourceItem(source="dockerhub", external_id=f"{x.get('user','library')}/{x['name']}", collected_at=now, payload={"title":x["name"],"url":f"https://hub.docker.com/r/{x.get('user','library')}/{x['name']}","summary":x.get("description") or "","stars":x.get("star_count",0),"published_at":x.get("last_updated"),"category":"Developer Tools"}, metadata={"published_at":x.get("last_updated")}) for x in rows)
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, now, items=items)
