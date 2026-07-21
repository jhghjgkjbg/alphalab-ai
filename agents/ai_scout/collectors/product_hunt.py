from __future__ import annotations

from datetime import UTC, datetime

from agents.ai_scout.clients.product_hunt_client import ProductHuntClient
from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


class ProductHuntCollector(BaseCollector):
    def __init__(self, client: ProductHuntClient, max_items: int = 10) -> None:
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        self._client = client
        self._max_items = max_items

    @classmethod
    def name(cls) -> str:
        return "product_hunt"

    async def collect(self) -> CollectorResult:
        started = datetime.now(UTC)
        result = await self._client.fetch_new_products(self._max_items)
        finished = datetime.now(UTC)
        if not result.success:
            return CollectorResult(self.name(), CollectorStatus.FAILED, started, finished, errors=(result.error_message or "Product Hunt client failed",))
        items = tuple(
            SourceItem(
                source="product_hunt", external_id=product.id, collected_at=finished,
                payload={
                    "title": product.name,
                    "url": product.url,
                    "summary": product.tagline or product.description or "",
                    "published_at": None,
                    "tags": product.topics,
                    "votes_count": product.votes_count,
                },
                metadata={"published_at": None, "tags": product.topics},
            )
            for product in result.items
        )
        return CollectorResult(self.name(), CollectorStatus.SUCCESS, started, finished, items=items)
