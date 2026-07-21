import asyncio, json, unittest
from core.ranking.engine import RankingEngine
from core.ai_gateway.types import AIResponse
class Gateway:
    def __init__(self): self.calls=0
    async def rank(self,text): self.calls+=1; return AIResponse(True,json.dumps({"relevance_score":.8,"novelty_score":.6,"technical_depth":.7,"business_value":.5}))
class RankingTests(unittest.TestCase):
    def test_json_extraction_variants(self):
        valid = '{"relevance_score":0.9,"novelty_score":0.7,"technical_depth":0.8,"business_value":0.6}'
        cases = [valid, 'before ```json\n'+valid+'\n``` after', 'before '+valid+' after', '```{} ``` ```'+valid+'```', '{"note":"brace { and \\"quote\\""} '+valid]
        for text in cases:
            self.assertEqual(RankingEngine._parse(text), {"relevance":.9,"novelty":.7,"technical":.8,"business":.6})
        self.assertIsNone(RankingEngine._parse('[1,2,3]'))
    def test_rank_batch_and_empty(self):
        async def run():
            g=Gateway(); r=await RankingEngine(g,batch_size=1).rank_batch(["a","b","a"]); self.assertEqual(len(r.items),2); self.assertEqual(g.calls,2); self.assertEqual((await RankingEngine(g).rank([])).items,())
        asyncio.run(run())
    def test_malformed_provider(self):
        class Bad:
            async def rank(self,_): return AIResponse(True,"bad")
        async def run(): self.assertEqual((await RankingEngine(Bad()).rerank(["x"])).stats.failed_items,1)
        asyncio.run(run())
if __name__ == "__main__": unittest.main()
