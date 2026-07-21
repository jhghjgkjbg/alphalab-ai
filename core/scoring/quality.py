from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping
from core.reputation import SourceReputationCalculator


class QualityScoreCalculator:
    def __init__(self, weights: Mapping[str, float] | None = None, source_reputation: Mapping[str, float] | None = None, category_bonus: Mapping[str, float] | None = None) -> None:
        self.weights = dict(weights or {"importance": .30, "verdict": .20, "ranking": .15, "freshness": .10, "source": .10, "popularity": .05, "similarity": .05, "category": .05})
        self.source_reputation = SourceReputationCalculator(overrides=source_reputation).overrides
        self.category_bonus = {k.lower(): v for k, v in (category_bonus or {"ai": 1.0, "open source": 1.0, "llm": 1.0, "programming": .8, "research": .9}).items()}

    def calculate(self, item: Any, *, ranking: float = 0.0, similarity: float = 0.0, trend_bonus: float = 0.0, now: datetime | None = None) -> tuple[float, dict[str, float], str]:
        payload = getattr(item, "payload", {})
        if not isinstance(payload, Mapping): payload = {}
        editorial = payload.get("editorial", payload.get("enrichment", {}))
        if not isinstance(editorial, Mapping): editorial = {}
        importance = self._num(editorial.get("importance", payload.get("importance", 0)))
        verdict = self._num(editorial.get("verdict_score", editorial.get("verdict", 0)))
        source = self.source_reputation.get(str(getattr(item, "source", payload.get("source", ""))).lower(), .60)
        published = payload.get("published_at") or getattr(item, "collected_at", None)
        age = max(0.0, ((now or datetime.now(UTC)) - published).total_seconds() / 3600) if isinstance(published, datetime) else 9999
        freshness = 1.0 if age < 6 else .8 if age < 24 else .6 if age < 72 else .35 if age < 168 else .1
        popularity = min(1.0, max(0.0, self._num(payload.get("score", payload.get("popularity", 0))) / 100))
        category = str(editorial.get("category", payload.get("category", ""))).lower()
        category_value = self.category_bonus.get(category, 0.0)
        values = {"importance": importance, "verdict": verdict, "ranking": ranking, "freshness": freshness, "source": source, "popularity": popularity, "similarity": similarity, "category": category_value}
        score = sum(values[k] * self.weights.get(k, 0.0) for k in values) + min(.10, max(0.0, trend_bonus))
        values["trend"] = min(.10, max(0.0, trend_bonus))
        reason = ", ".join(f"{k}={values[k]:.2f}" for k in values)
        return score, values, reason

    @staticmethod
    def _num(value: Any) -> float:
        try: return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError): return 0.0
