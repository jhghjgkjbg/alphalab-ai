import asyncio
import unittest

from core.ai_gateway.fake import FakeAIProvider
from core.ai_gateway.gateway import AIGateway
from core.ai_gateway.types import AIError, AIRequest, AIResponse, AIUsage


class AIProvider:
    name = "test"
    async def execute(self, request):
        return AIResponse(True, "ok", AIUsage("test", "model", 2, 1, 0.1, cached=True))


class AIGatewayTests(unittest.TestCase):
    def test_success_usage_and_cached(self):
        response = asyncio.run(AIGateway(AIProvider()).classify("x"))
        self.assertTrue(response.success); self.assertTrue(response.usage.cached)

    def test_provider_error_and_disabled(self):
        class Broken:
            name = "broken"
            async def execute(self, _): raise RuntimeError("boom")
        self.assertEqual(asyncio.run(AIGateway(Broken()).summarize("x")).error.code, "provider_error")
        self.assertEqual(asyncio.run(AIGateway(disabled=True).rank("x")).error.code, "ai_disabled")

    def test_fake_and_immutable_types(self):
        self.assertTrue(asyncio.run(AIGateway(FakeAIProvider()).rank("x")).success)
        with self.assertRaises((AttributeError, TypeError)):
            AIUsage("p", "m", 1, 1, 0.0).provider = "x"


if __name__ == "__main__": unittest.main()
