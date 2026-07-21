import asyncio, json, unittest
from datetime import datetime, UTC
from core.pipeline.ai_pipeline import AIPipeline
from core.collector.types import SourceItem
from core.embeddings.engine import EmbeddingEngine
from core.embeddings.fake import FakeEmbeddingProvider
from core.ai_gateway.gateway import AIGateway
from core.ai_gateway.fake import FakeAIProvider
from core.ranking.engine import RankingEngine
from core.publication.engine import ScoredPublicationEngine

class P(FakeAIProvider):
 async def execute(self,r): return __import__('core.ai_gateway.types',fromlist=['AIResponse']).AIResponse(True,json.dumps({'relevance_score':1,'novelty_score':1,'technical_depth':1,'business_value':1}))
class Tests(unittest.TestCase):
 def test_full_and_empty(self):
  async def run():
   items=[SourceItem('rss','1',datetime.now(UTC),{'title':'AI','url':'https://x'})]
   pipeline=AIPipeline(collector=lambda:items,embedding_engine=EmbeddingEngine(FakeEmbeddingProvider()),gateway=AIGateway(P()),ranking_engine=RankingEngine(AIGateway(P())),publication_engine=ScoredPublicationEngine(dry_run=True))
   self.assertEqual(len((await pipeline.run()).items),1); self.assertEqual(len((await AIPipeline(collector=lambda:[]).run()).items),0)
  asyncio.run(run())
if __name__=='__main__': unittest.main()
