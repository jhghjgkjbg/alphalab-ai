from dataclasses import replace
from .rules import LengthRule, CanonicalRule, TitleRule, FreshnessRule, SourceRule, StructureRule, LanguageRule
class QualityScoringEngine:
    def __init__(self,rules=None): self.rules=tuple(rules or (LengthRule(),CanonicalRule(),TitleRule(),FreshnessRule(),SourceRule(),StructureRule(),LanguageRule()))
    def score(self,publication):
        values={r.name:max(0.0,min(1.0,float(r.score(publication)))) for r in self.rules}; total=sum(values.values())/len(values) if values else 0.0
        return replace(publication,quality_scores=values,final_quality_score=total)
