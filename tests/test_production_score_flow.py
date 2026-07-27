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
