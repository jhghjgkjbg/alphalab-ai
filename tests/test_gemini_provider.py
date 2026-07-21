import asyncio
import unittest
from core.ai_gateway.providers.gemini import GeminiProvider
from core.ai_gateway.types import AIRequest

class GeminiProviderTests(unittest.TestCase):
    def test_success_and_metadata(self):
        async def request(*_): return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}], "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 1}}
        p = GeminiProvider("key", "model", 2, request); r = asyncio.run(p.execute(AIRequest("summarize", "text")))
        self.assertTrue(r.success); self.assertEqual(r.output, "ok"); self.assertEqual(p.name, "gemini"); self.assertIn("summarize", p.supported_operations)
    def test_errors(self):
        async def timeout(*_): raise TimeoutError()
        self.assertEqual(asyncio.run(GeminiProvider("k", "m", 1, timeout).execute(AIRequest("classify", "x"))).error.code, "timeout")
        async def invalid(*_): return (403, {})
        self.assertEqual(asyncio.run(GeminiProvider("k", "m", 1, invalid).execute(AIRequest("classify", "x"))).error.code, "invalid_api_key")
        async def quota(*_): return (402, {})
        self.assertEqual(asyncio.run(GeminiProvider("k", "m", 1, quota).execute(AIRequest("classify", "x"))).error.code, "quota_exceeded")
        async def malformed(*_): return {"candidates": []}
        self.assertEqual(asyncio.run(GeminiProvider("k", "m", 1, malformed).execute(AIRequest("classify", "x"))).error.code, "empty_response")
if __name__ == "__main__": unittest.main()
