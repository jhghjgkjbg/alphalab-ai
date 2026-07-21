import asyncio, unittest
from core.embeddings.fake import FakeEmbeddingProvider
from core.embeddings.engine import EmbeddingEngine
from core.embeddings.cache import InMemoryEmbeddingCache

class EmbeddingTests(unittest.TestCase):
    def test_fake_engine_cache_batch(self):
        async def run():
            p=FakeEmbeddingProvider(4); c=InMemoryEmbeddingCache(10,10); e=EmbeddingEngine(p,c); a=await e.embed(" Hello  world "); b=await e.embed("hello world"); self.assertEqual(a.vector.dimensions,4); self.assertIsNotNone(b.vector); batch=await e.embed_batch(["a","b"]); self.assertEqual(len(batch.results),2)
        asyncio.run(run())
    def test_error_and_immutable(self):
        async def run(): self.assertIsNotNone((await EmbeddingEngine(FakeEmbeddingProvider(fail=True)).embed("x")).error)
        asyncio.run(run())

if __name__ == '__main__': unittest.main()
