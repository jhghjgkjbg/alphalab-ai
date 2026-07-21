from dataclasses import dataclass
from .rules import Rule, NormalizeWhitespaceRule, NormalizeUrlRule, CleanFieldsRule

@dataclass(frozen=True)
class EditorialDecision:
    accepted: bool
    editorial_score: float
    source_trust_score: float
    freshness_score: float
    topic_score: float
    reasons: tuple[str, ...] = ()

class EditorialEngine:
    def __init__(self,rules=None, minimum_score=0.0, preferred_sources=(), blocked_sources=(), preferred_topics=(), blocked_topics=()):
        self.rules=tuple(rules or (NormalizeWhitespaceRule(),NormalizeUrlRule(),CleanFieldsRule())); self.minimum_score=minimum_score; self.preferred_sources={str(x).casefold() for x in preferred_sources}; self.blocked_sources={str(x).casefold() for x in blocked_sources}; self.preferred_topics={str(x).casefold() for x in preferred_topics}; self.blocked_topics={str(x).casefold() for x in blocked_topics}
    def apply(self,publication):
        for rule in self.rules: publication=rule.apply(publication)
        return publication
    def evaluate(self, publication):
        source=str(publication.source or '').casefold(); topic=str(publication.category or '').casefold(); reasons=[]
        trust=1.0 if source in self.preferred_sources else (0.0 if source in self.blocked_sources else .6)
        topic_score=1.0 if topic in self.preferred_topics else (0.0 if topic in self.blocked_topics else .5)
        freshness=1.0 if publication.published_at else .5
        score=(trust+topic_score+freshness)/3
        if source in self.blocked_sources: reasons.append('blocked_source')
        if topic in self.blocked_topics: reasons.append('blocked_topic')
        accepted=score >= self.minimum_score and not reasons
        if score < self.minimum_score: reasons.append('below_minimum_score')
        return EditorialDecision(accepted, score, trust, freshness, topic_score, tuple(reasons))
