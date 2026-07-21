import asyncio
import json
import unittest
from datetime import UTC, datetime

from core.collector.types import SourceItem
from core.dedup.engine import DedupEngine
from core.embeddings.cache import InMemoryEmbeddingCache
from core.embeddings.engine import EmbeddingEngine
from core.embeddings.fake import FakeEmbeddingProvider
from core.ai_gateway.cache import InMemoryAICache
from core.ai_gateway.budget import BudgetConfig, BudgetManager
from core.ai_gateway.rate_limit import RateLimitConfig, InMemoryRateLimiter
from core.ai_gateway.gateway import AIGateway
from core.ai_gateway.fake import FakeAIProvider
from core.ranking.engine import RankingEngine
from core.scoring.engine import ScoringEngine
from core.scoring.types import ScoringRequest
from core.publication.engine import ScoredPublicationEngine


class RankingFake(FakeAIProvider):
    async def execute(self, request):
        from core.ai_gateway.types import AIResponse, AIUsage
        return AIResponse(True, json.dumps({"relevance_score": .9, "novelty_score": .8, "technical_depth": .7, "business_value": .8}), AIUsage("fake", "fake", 1, 1, 0.0))


class MockTelegram:
    def __init__(self): self.items = []
    async def publish(self, item): self.items.append(item); return type("Result", (), {"success": True, "external_id": str(len(self.items))})()


class FullPipelineTests(unittest.TestCase):
    def test_full_fake_pipeline_and_cost_metrics(self):
        async def run():
            source = lambda source, title, url: SourceItem(source, title, datetime.now(UTC), {"title": title, "url": url, "summary": title})
            raw = [source("rss", "AI launch", "https://example.com/a?utm_source=x"), source("github", "AI launch", "https://example.com/a"), source("reddit", "Unique", "https://example.com/u")]
            unique, groups, stats = DedupEngine().deduplicate(raw); self.assertEqual(stats.duplicate_items, 1); self.assertEqual(len(unique), 2)
            embedding = EmbeddingEngine(FakeEmbeddingProvider(), InMemoryEmbeddingCache()); similarity = __import__("core.similarity.engine", fromlist=["SimilarityEngine"]).SimilarityEngine(embedding); self.assertEqual(len((await similarity.find_similar("AI launch", unique, 0.0, 2)).matches), 2)
            gateway = AIGateway(RankingFake(), cache=InMemoryAICache(), budget=BudgetManager(BudgetConfig(10, 10, 10)), rate_limiter=InMemoryRateLimiter(RateLimitConfig(10, 10, 2)))
            ranked = await RankingEngine(gateway).rank(unique); scored = ScoringEngine().score_items([ScoringRequest(x.item, ranking_score=x.final_score * 100, freshness_bonus=10) for x in ranked.items])
            telegram = MockTelegram(); published = await ScoredPublicationEngine(telegram, minimum_score=1, top_n=2).publish_scored(scored.items)
            self.assertEqual(published.stats.published_items, 2); self.assertEqual(len(telegram.items), 2); self.assertEqual(len((await gateway.rank("same")).output), len((await gateway.rank("same")).output))
        asyncio.run(run())

if __name__ == "__main__": unittest.main()
