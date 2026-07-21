from dataclasses import replace
from datetime import datetime, UTC
class FreshArticleRule:
    name="freshness"
    def score(self,p):
        try:return max(0,1-(datetime.now(UTC)-datetime.fromisoformat(p.published_at).replace(tzinfo=UTC)).days/30)
        except Exception:return .5
class TrendRule:
    name="trend"
    def score(self,p): return max(0,min(1,float(p.trend_bonus)))
class QualityRule:
    name="quality"
    def score(self,p): return max(0,min(1,float(p.final_quality_score)))
class SourcePriorityRule:
    name="source"
    def score(self,p): return {"github":1,"arxiv":.95,"hacker_news":.9,"lobsters":.8}.get(p.source.casefold(),.5)
class EditorialPriorityRule:
    name="editorial"
    def score(self,p): return max(0,min(1,float(p.editorial_score)/100 if p.editorial_score>1 else float(p.editorial_score)))
class RankingEngineV1:
    def __init__(self,rules=None): self.rules=tuple(rules or (FreshArticleRule(),TrendRule(),QualityRule(),SourcePriorityRule(),EditorialPriorityRule()))
    def rank(self,p):
        details={r.name:float(r.score(p)) for r in self.rules}; total=sum(details.values())/len(details) if details else 0
        return replace(p,ranking_score=total,ranking_details=details)
