from core.scoring.base import BaseRule
from core.scoring.types import ScoreResult, ScorableItem
from core.scoring.types import ScoringRequest, ScoredItem, ScoringResult, ScoringStats
from datetime import UTC, datetime
from core.scoring.quality import QualityScoreCalculator


class ScoringEngine:
    def __init__(self, weights: dict[str, float] | None = None, min_score: float = 0.0, freshness_half_life_hours: float = 24.0, source_priority_map: dict[str, float] | None = None) -> None:
        self._rules: list[BaseRule] = []
        self._weights = weights or {}
        self._min_score = min_score
        self._half_life = freshness_half_life_hours
        self._source_priority = source_priority_map or {}
        self._quality = QualityScoreCalculator()

    def register(self, rule: BaseRule) -> None:
        rule_name = rule.name()
        if not rule_name:
            raise ValueError("rule name must not be empty")
        if any(registered.name() == rule_name for registered in self._rules):
            raise ValueError(f"rule is already registered: {rule_name}")

        self._rules.append(rule)

    def registered(self) -> tuple[BaseRule, ...]:
        return tuple(self._rules)

    async def score(self, item: ScorableItem) -> ScoreResult:
        details = []
        for rule in self._rules:
            details.append(await rule.score(item))

        immutable_details = tuple(details)
        return ScoreResult(
            total_score=sum(detail.score_delta for detail in immutable_details),
            details=immutable_details,
            reasons=tuple(detail.reason for detail in immutable_details),
        )

    def score_items(self, requests: list[ScoringRequest]) -> ScoringResult:
        scored = []
        now = datetime.now(UTC)
        for index, request in enumerate(requests):
            freshness = request.freshness_bonus
            if request.published_at and self._half_life > 0:
                age = max(0.0, (now - request.published_at).total_seconds() / 3600)
                freshness = freshness * (0.5 ** (age / self._half_life))
            payload = getattr(request.item, "payload", {})
            if isinstance(payload, dict) and ("editorial" in payload or "enrichment" in payload):
                score, _, _ = self._quality.calculate(request.item, ranking=request.ranking_score, similarity=max(0.0, 1.0 - request.similarity_penalty), now=now)
            else:
                score = request.ranking_score + freshness + request.popularity_bonus + request.manual_boost + self._source_priority.get(str(getattr(request.item, "source", "")), request.source_priority) - request.similarity_penalty
            if score >= self._min_score: scored.append((ScoredItem(request.item, score), index))
        scored.sort(key=lambda pair: (-pair[0].final_score, pair[1]))
        items = tuple(pair[0] for pair in scored)
        return ScoringResult(items, ScoringStats(len(requests), len(items)))
