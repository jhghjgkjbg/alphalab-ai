from datetime import datetime, UTC
from typing import Protocol
class QualityRule(Protocol):
    name: str
    def score(self, publication) -> float: ...
class LengthRule:
    name="length_score"
    def score(self,p): return 1.0 if len(p.summary)>=120 else .5 if len(p.summary)>=40 else 0.2
class CanonicalRule:
    name="canonical_score"
    def score(self,p): return 1.0 if p.canonical_url else 0.0
class TitleRule:
    name="title_score"
    def score(self,p): return 1.0 if p.title.strip() else 0.1
class FreshnessRule:
    name="freshness_score"
    def score(self,p):
        try:return max(0.0,1-(datetime.now(UTC)-datetime.fromisoformat(p.published_at).replace(tzinfo=UTC)).days/30)
        except Exception:return 0.5
class SourceRule:
    name="source_score"
    def score(self,p): return 1.0 if p.source.casefold() in {"github","arxiv","hacker_news","lobsters"} else .5
class StructureRule:
    name="structure_score"
    def score(self,p): return 1.0 if p.title and p.summary and p.canonical_url else .4
class LanguageRule:
    name="language_score"
    def score(self,p): return 1.0 if p.language else .0
