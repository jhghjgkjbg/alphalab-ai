from datetime import datetime, UTC
from .types import PublicationMetrics, NoOpCollector
class MetricsEngine:
    def __init__(self,collector=None): self.collector=collector or NoOpCollector()
    def collect(self,publication):
        try: freshness=max(0,1-(datetime.now(UTC)-datetime.fromisoformat(publication.published_at).replace(tzinfo=UTC)).days/30)
        except Exception: freshness=.5
        m=PublicationMetrics(float(publication.editorial_score),float(publication.final_quality_score),float(publication.ranking_score),publication.language,publication.source,publication.category,float(publication.trend_bonus),freshness,len(publication.summary),len(publication.title)); self.collector.collect(m); return m
