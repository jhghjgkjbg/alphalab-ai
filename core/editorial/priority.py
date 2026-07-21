from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PublicationPriority:
    level: str
    score: float
    factors: dict[str, float]


class PublicationPrioritizer:
    def prioritize(self, publication, ai_confidence=0.0, freshness=0.5, source_trust=0.5, importance=0.5, audience_relevance=0.5) -> PublicationPriority:
        editorial = min(1.0, max(0.0, float(getattr(publication, "editorial_score", 0) or 0) / 100))
        values = {"editorial_score": editorial, "ai_confidence": float(ai_confidence), "freshness": float(freshness), "source_trust": float(source_trust), "story_importance": float(importance), "audience_relevance": float(audience_relevance)}
        score = sum(values.values()) / len(values)
        level = "breaking" if score >= .9 else "high" if score >= .72 else "normal" if score >= .45 else "low"
        return PublicationPriority(level, round(score, 4), values)

    def apply(self, publication, **kwargs):
        return replace(publication, priority=self.prioritize(publication, **kwargs))
