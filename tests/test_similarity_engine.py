import asyncio
import unittest
from core.similarity.engine import SimilarityEngine
from core.similarity.metrics import cosine_similarity
from core.embeddings.fake import FakeEmbeddingProvider
from core.embeddings.engine import EmbeddingEngine

class SimilarityTests(unittest.TestCase):
    def test_metrics_and_find(self):
        self.assertAlmostEqual(cosine_similarity((1,0),(1,0)), 1.0); self.assertIsNone(cosine_similarity((0,0),(1,0)))
        async def run():
            engine=SimilarityEngine(EmbeddingEngine(FakeEmbeddingProvider(4))); result=await engine.find_similar("same", ["same", "other"], .9, 1); self.assertEqual(len(result.matches),1); self.assertEqual(result.matches[0].rank,1); self.assertEqual((await engine.compare_many((1,0),( (1,0),(0,1) ))), (1.0,0.0))
        asyncio.run(run())
    def test_empty_and_malformed(self):
        async def run():
            engine=SimilarityEngine(EmbeddingEngine(FakeEmbeddingProvider())); self.assertEqual((await engine.find_similar("", ["x"],0,2)).matches,()); self.assertIsNone(await engine.compare((1,), (1,2)))
        asyncio.run(run())

if __name__ == "__main__": unittest.main()
