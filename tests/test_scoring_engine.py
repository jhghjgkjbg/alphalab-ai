import unittest
from datetime import UTC, datetime, timedelta
from core.scoring.engine import ScoringEngine
from core.scoring.types import ScoringRequest

class ScoringEngineTests(unittest.TestCase):
    def test_formula_priority_and_stable_order(self):
        engine=ScoringEngine(source_priority_map={"github": 2}, min_score=0)
        items=[ScoringRequest("a", ranking_score=5, popularity_bonus=1, manual_boost=1, similarity_penalty=.5), ScoringRequest("b", ranking_score=5, popularity_bonus=1, manual_boost=1, similarity_penalty=.5)]
        result=engine.score_items(items); self.assertEqual([x.item for x in result.items], ["a","b"]); self.assertEqual(result.stats.total_items,2)
    def test_freshness_and_empty(self):
        engine=ScoringEngine(freshness_half_life_hours=24)
        old=ScoringRequest("x", freshness_bonus=10, published_at=datetime.now(UTC)-timedelta(hours=24)); self.assertAlmostEqual(engine.score_items([old]).items[0].final_score,5,delta=.2); self.assertEqual(engine.score_items([]).items,())

if __name__ == "__main__": unittest.main()
