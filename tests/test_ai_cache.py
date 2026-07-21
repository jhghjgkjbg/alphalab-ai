import asyncio
import unittest

from core.ai_gateway.cache import AICacheKey, InMemoryAICache
from core.ai_gateway.types import AIResponse, AIUsage


RESPONSE = AIResponse(True, "ok", AIUsage("p", "m", 1, 1, 0.0))


class AICacheTests(unittest.TestCase):
    def key(self, model="m", params=None): return AICacheKey.build("classify", "p", model, " Hello  World ", params)

    def test_hit_miss_ttl_and_stats(self):
        async def run():
            cache = InMemoryAICache(2, .01); self.assertIsNone(await cache.get(self.key())); await cache.set(self.key(), RESPONSE); self.assertEqual(await cache.get(self.key()), RESPONSE); await asyncio.sleep(.02); self.assertIsNone(await cache.get(self.key())); stats = await cache.stats(); self.assertEqual((stats.hits, stats.misses, stats.expired), (1, 2, 1))
        asyncio.run(run())

    def test_keys_delete_clear_and_lru(self):
        async def run():
            cache = InMemoryAICache(2); k1, k2, k3 = self.key(), self.key("x"), self.key("y"); await cache.set(k1, RESPONSE); await cache.set(k2, RESPONSE); await cache.get(k1); await cache.set(k3, RESPONSE); self.assertIsNone(await cache.get(k2)); self.assertTrue(await cache.delete(k1)); await cache.clear(); self.assertEqual((await cache.stats()).entries, 0)
        asyncio.run(run()); self.assertNotEqual(self.key(), self.key("x")); self.assertNotEqual(self.key(params={"a": 1}), self.key(params={"a": 2}))

    def test_does_not_store_failure_and_concurrent_access(self):
        async def run():
            cache = InMemoryAICache(); key = self.key(); await asyncio.gather(*(cache.set(key, RESPONSE) for _ in range(20))); await asyncio.gather(*(cache.get(key) for _ in range(20))); self.assertFalse(await cache.set(self.key("bad"), AIResponse(False, None)))
        asyncio.run(run())


if __name__ == "__main__": unittest.main()
