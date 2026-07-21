from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class BudgetConfig:
    monthly_budget_usd: float
    daily_budget_usd: float
    hourly_budget_usd: float
    emergency_stop: bool = False


@dataclass(frozen=True, slots=True)
class BudgetState:
    month_spent: float = 0.0
    day_spent: float = 0.0
    hour_spent: float = 0.0


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    allowed: bool
    reason: str
    remaining_month: float
    remaining_day: float
    remaining_hour: float


class BudgetManager:
    def __init__(self, config: BudgetConfig, state: BudgetState | None = None) -> None:
        if min(config.monthly_budget_usd, config.daily_budget_usd, config.hourly_budget_usd) < 0:
            raise ValueError("budgets must not be negative")
        self._config = config
        self._state = state or BudgetState()

    @property
    def config(self) -> BudgetConfig:
        return self._config

    def remaining_budget(self) -> tuple[float, float, float]:
        return (
            self._config.monthly_budget_usd - self._state.month_spent,
            self._config.daily_budget_usd - self._state.day_spent,
            self._config.hourly_budget_usd - self._state.hour_spent,
        )

    def can_execute(self, cost_usd: float) -> BudgetDecision:
        if cost_usd < 0:
            raise ValueError("cost must not be negative")
        remaining = self.remaining_budget()
        if self._config.emergency_stop:
            return BudgetDecision(False, "emergency_stop", *remaining)
        if cost_usd > remaining[2]:
            return BudgetDecision(False, "hourly_limit_exceeded", *remaining)
        if cost_usd > remaining[1]:
            return BudgetDecision(False, "daily_limit_exceeded", *remaining)
        if cost_usd > remaining[0]:
            return BudgetDecision(False, "monthly_limit_exceeded", *remaining)
        return BudgetDecision(True, "allowed", *remaining)

    def register_usage(self, cost_usd: float) -> BudgetState:
        if cost_usd < 0:
            raise ValueError("cost must not be negative")
        self._state = replace(
            self._state,
            month_spent=self._state.month_spent + cost_usd,
            day_spent=self._state.day_spent + cost_usd,
            hour_spent=self._state.hour_spent + cost_usd,
        )
        return self._state
