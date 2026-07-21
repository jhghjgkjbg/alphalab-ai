from abc import ABC, abstractmethod

from core.scoring.types import RuleResult, ScorableItem


class BaseRule(ABC):
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the stable, unique rule name."""

    @abstractmethod
    async def score(self, item: ScorableItem) -> RuleResult:
        """Evaluate one item without mutating it."""
