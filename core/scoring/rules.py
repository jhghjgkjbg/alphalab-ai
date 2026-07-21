import inspect
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from core.scoring.base import BaseRule
from core.scoring.types import RuleResult, ScorableItem


Clock = Callable[[], datetime]
DuplicateChecker = Callable[[ScorableItem], bool | Awaitable[bool]]


class FreshnessRule(BaseRule):
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def name(cls) -> str:
        return "freshness"

    async def score(self, item: ScorableItem) -> RuleResult:
        now = self._clock()
        age = max(now - item.collected_at, timedelta(0))

        if age <= timedelta(hours=24):
            delta, tier = 30, "up to 24 hours"
        elif age <= timedelta(hours=72):
            delta, tier = 20, "up to 72 hours"
        elif age <= timedelta(days=7):
            delta, tier = 10, "up to 7 days"
        else:
            delta, tier = 0, "older than 7 days"

        return RuleResult(
            rule_name=self.name(),
            score_delta=delta,
            reason=f"Item freshness: {tier}",
        )


class SourceTrustRule(BaseRule):
    _BONUSES = {
        "hacker_news": 20,
        "github": 15,
        "product_hunt": 15,
    }

    @classmethod
    def name(cls) -> str:
        return "source_trust"

    async def score(self, item: ScorableItem) -> RuleResult:
        delta = self._BONUSES.get(item.source, 0)
        return RuleResult(
            rule_name=self.name(),
            score_delta=delta,
            reason=f"Source trust for '{item.source}': +{delta}",
        )


class DuplicateRule(BaseRule):
    def __init__(self, is_duplicate: DuplicateChecker) -> None:
        self._is_duplicate = is_duplicate

    @classmethod
    def name(cls) -> str:
        return "duplicate"

    async def score(self, item: ScorableItem) -> RuleResult:
        duplicate_result = self._is_duplicate(item)
        if inspect.isawaitable(duplicate_result):
            duplicate_result = await duplicate_result

        is_duplicate = bool(duplicate_result)
        return RuleResult(
            rule_name=self.name(),
            score_delta=-100 if is_duplicate else 0,
            reason="Duplicate item" if is_duplicate else "Unique item",
        )


class KeywordRule(BaseRule):
    DEFAULT_KEYWORDS = ("AI", "LLM", "OpenAI", "Anthropic", "GPT", "Claude")

    def __init__(
        self,
        *,
        keywords: tuple[str, ...] = DEFAULT_KEYWORDS,
        bonus_per_keyword: int = 5,
        max_bonus: int = 20,
    ) -> None:
        if bonus_per_keyword < 0 or max_bonus < 0:
            raise ValueError("keyword bonuses must not be negative")

        self._keywords = tuple(dict.fromkeys(keywords))
        self._bonus_per_keyword = bonus_per_keyword
        self._max_bonus = max_bonus

    @classmethod
    def name(cls) -> str:
        return "keyword"

    async def score(self, item: ScorableItem) -> RuleResult:
        searchable_text = " ".join((item.title, item.summary, item.content))
        matched = tuple(
            keyword
            for keyword in self._keywords
            if re.search(
                rf"(?<!\w){re.escape(keyword)}(?!\w)",
                searchable_text,
                flags=re.IGNORECASE,
            )
        )
        delta = min(len(matched) * self._bonus_per_keyword, self._max_bonus)
        reason = (
            f"Matched keywords: {', '.join(matched)}"
            if matched
            else "No scoring keywords matched"
        )
        return RuleResult(
            rule_name=self.name(),
            score_delta=delta,
            reason=reason,
        )
