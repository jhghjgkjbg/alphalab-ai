import asyncio
import unittest
from core.embeddings.providers.local_bge import LocalBGEEmbeddingProvider
from core.embeddings.types import EmbeddingRequest

class Model:
    def encode(self, texts, **kwargs): return [[float(len(t)), 1.0] for t in texts]

class LocalProviderTests(unittest.TestCase):
    def test_lazy_singleton_batch_and_metadata(self):
        calls=[]
        def factory(*args): calls.append(args); return Model()
        async def run():
            p=LocalBGEEmbeddingProvider(batch_size=1, model_factory=factory); requests=(EmbeddingRequest("a","m"),EmbeddingRequest("bb","m")); r=await p.embed_batch(requests); self.assertEqual(len(r.results),2); await p.embed(requests[0]); self.assertEqual(len(calls),1); self.assertTrue(p.metadata["local"]); self.assertTrue(r.results[0].vector.dimensions>0)
        asyncio.run(run())
    def test_errors_and_configuration(self):
        async def run():
            p=LocalBGEEmbeddingProvider(model_factory=lambda *_: Model()); r=await p.embed(EmbeddingRequest("","m")); self.assertIsNotNone(r.error); self.assertEqual(p.device,"cpu")
        asyncio.run(run())

if __name__ == "__main__": unittest.main()
