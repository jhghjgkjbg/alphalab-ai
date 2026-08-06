from core.scoring.base import BaseRule
from core.scoring.types import ScoreResult, ScorableItem
from core.scoring.types import ScoringRequest, ScoredItem, ScoringResult, ScoringStats
from datetime import UTC, datetime
from core.scoring.quality import QualityScoreCalculator
import re


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
        seen_titles: set[str] = set()
        package_count = 0
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
            title = str((payload or {}).get("title", "")).lower() if isinstance(payload, dict) else ""
            normalized = re.sub(r"[^a-z0-9]+", "", re.sub(r"^(re|update|release|new)[:\s-]+", "", title))
            if normalized and normalized in seen_titles:
                score -= 0.25
            if normalized:
                seen_titles.add(normalized)
            if str(getattr(request.item, "source", "")) in {"pypi", "npm", "dockerhub"}:
                if package_count >= 2 and len(requests) > 2:
                    continue
                package_count += 1
            if score >= self._min_score: scored.append((ScoredItem(request.item, score), index))
        def tie_key(pair):
            scored_item, index = pair
            request = requests[index]
            payload = getattr(request.item, "payload", {}) or {}
            body = str(payload.get("content") or payload.get("body") or "").strip()
            summary = str(payload.get("summary") or payload.get("description") or "").strip()
            completeness = 2 if body else 1 if summary else 0
            return (-scored_item.final_score, -float(request.source_priority or 0), -completeness, -(len(body) + len(summary)), index)
        scored.sort(key=tie_key)
        items = tuple(pair[0] for pair in scored)
        return ScoringResult(items, ScoringStats(len(requests), len(items)))
