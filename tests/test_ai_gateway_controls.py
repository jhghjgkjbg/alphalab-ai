import asyncio
import unittest
from core.ai_gateway.gateway import AIGateway
from core.ai_gateway.types import AIRequest, AIResponse, AIUsage
from core.ai_gateway.cache import InMemoryAICache
from core.ai_gateway.budget import BudgetConfig, BudgetManager
from core.ai_gateway.rate_limit import InMemoryRateLimiter, RateLimitConfig

class Provider:
    name = "p"
    def __init__(self, fail=False): self.calls = 0; self.fail = fail
    async def execute(self, request):
        self.calls += 1
        if self.fail: raise RuntimeError("fail")
        return AIResponse(True, "ok", AIUsage("p", "m", 1, 1, .5))

class GatewayControlTests(unittest.TestCase):
    def test_cache_budget_and_rate(self):
        async def run():
            p = Provider(); g = AIGateway(p, cache=InMemoryAICache(), budget=BudgetManager(BudgetConfig(2,2,2)), rate_limiter=InMemoryRateLimiter(RateLimitConfig(5,5,1)))
            a = await g.classify("x"); b = await g.classify("x"); self.assertEqual(p.calls, 1); self.assertTrue(b.usage.cached)
            denied = AIGateway(Provider(), budget=BudgetManager(BudgetConfig(0,0,0))); self.assertEqual((await denied.execute(AIRequest("x", "x", metadata=(("estimated_cost",1),)))).error.code, "budget_rejected")
        asyncio.run(run())
    def test_provider_failure_releases(self):
        async def run():
            limiter = InMemoryRateLimiter(RateLimitConfig(2,2,1)); r = await AIGateway(Provider(True), rate_limiter=limiter).classify("x"); self.assertEqual(r.error.code, "provider_error"); self.assertEqual((await limiter.inspect()).active_requests, 0)
        asyncio.run(run())

if __name__ == "__main__": unittest.main()
