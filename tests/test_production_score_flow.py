from dataclasses import replace

from core.collector.types import SourceItem
from core.publication.builder import PublicationBuilder
from core.ranking import RankingEngineV1
from core.scoring.engine import ScoringEngine
from core.scoring.types import ScoringRequest
from core.renderers.website import WebsiteRenderer
from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore
from pathlib import Path
import tempfile
from agents.ai_scout.agent import production_scoring_request, _normalized_popularity


def test_existing_ranking_and_scoring_score_reaches_website_view():
    item = SourceItem("github", "score-1", __import__("datetime").datetime.now(__import__("datetime").UTC), {"title": "AI release", "summary": "Useful summary", "url": "https://example.test/score"})
    ranked = RankingEngineV1().rank(PublicationBuilder().build(item))
    scored = ScoringEngine().score_items([ScoringRequest(item, ranking_score=ranked.ranking_score)]).items[0]
    enriched_item = replace(item, payload={**item.payload, "score": scored.final_score})
    publication = PublicationBuilder().build(enriched_item)
    view = WebsiteRenderer("en").render(publication)

    assert scored.final_score > 0
    assert publication.score == scored.final_score
    assert view.score == scored.final_score

    with tempfile.TemporaryDirectory() as directory:
        store = SQLitePublishedArticlesStore(SQLiteDatabase(Path(directory) / "score.db"))
        store.append(publication)
        assert store.latest(1)[0]["score"] == scored.final_score


def test_production_preserves_distinct_source_signals_in_scores():
    now = __import__("datetime").datetime.now(__import__("datetime").UTC)
    first = SourceItem("github", "one", now, {"title": "One", "summary": "Summary", "url": "https://example.test/one", "popularity_bonus": 0.1})
    second = SourceItem("github", "two", now, {"title": "Two", "summary": "Summary", "url": "https://example.test/two", "popularity_bonus": 0.7})
    ranked = RankingEngineV1()
    requests = [production_scoring_request(item, ranked.rank(PublicationBuilder().build(item)).ranking_score) for item in (first, second)]
    scores = ScoringEngine().score_items(requests).items
    assert scores[0].final_score != scores[1].final_score


def test_popularity_normalization_is_deterministic_and_bounded():
    assert _normalized_popularity({"score": 5}) < _normalized_popularity({"score": 100}) <= 1
    assert 0 < _normalized_popularity({"stars": 100}) <= 1
    assert 0 < _normalized_popularity({"votes_count": 200}) <= 1
    assert _normalized_popularity({"popularity_bonus": .25, "score": 100}) == .25
    assert _normalized_popularity({"score": -1}) == 0
    assert _normalized_popularity({"score": "bad"}) == 0


def test_normalized_popularity_changes_production_selection_and_score_stays_bounded():
    now = __import__("datetime").datetime.now(__import__("datetime").UTC)
    low = SourceItem("hacker_news", "low", now, {"title": "Low", "summary": "Summary", "url": "https://example.test/low", "score": 5})
    high = SourceItem("hacker_news", "high", now, {"title": "High", "summary": "Summary", "url": "https://example.test/high", "score": 100})
    ranking = RankingEngineV1(); builder = PublicationBuilder(); engine = ScoringEngine()
    requests = [production_scoring_request(x, ranking.rank(builder.build(x)).ranking_score) for x in (low, high)]
    scored = engine.score_items(requests).items
    assert scored[0].item.external_id == "high"
    assert all(0 <= x.final_score <= 1 for x in scored)
