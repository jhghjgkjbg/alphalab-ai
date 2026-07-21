import asyncio, unittest
from dataclasses import dataclass
from core.publication.engine import ScoredPublicationEngine

@dataclass
class S:
    item: object; final_score: float
class P:
    async def publish(self, item): return type("R", (), {"success": True, "external_id": "1"})()
class PublicationTests(unittest.TestCase):
    def test_sort_filter_top_duplicates_and_dry_run(self):
        async def run():
            items=[S(type("I",(),{"external_id":"a"})(),9), S(type("I",(),{"external_id":"b"})(),5), S(type("I",(),{"external_id":"a"})(),4)]
            r=await ScoredPublicationEngine(P(),6,2).publish_scored(items); self.assertEqual([x.item.external_id for x in r.items],["a"]); self.assertEqual(r.stats.total_items,3)
            self.assertEqual(len((await ScoredPublicationEngine(dry_run=True).publish_scored([])).items),0)
        asyncio.run(run())
if __name__ == "__main__": unittest.main()
