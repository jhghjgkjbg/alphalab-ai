from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .budget import BudgetManager
from .fake import FakeAIProvider
from .protocol import AIProvider
from .types import AIError, AIRequest, AIResponse


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    name: str
    enabled: bool
    priority: int
    estimated_cost: float
    estimated_speed: float
    quality: float
    supported_operations: frozenset[str]


@dataclass(frozen=True, slots=True)
class RegisteredProvider:
    provider: AIProvider
    metadata: ProviderMetadata


class AIRouter:
    def __init__(self, providers: Iterable[RegisteredProvider] = (), *, budget: BudgetManager | None = None, fake_provider: AIProvider | None = None) -> None:
        self._providers = list(providers)
        self._budget = budget
        self._fake = fake_provider or FakeAIProvider()

    def register(self, provider: AIProvider, metadata: ProviderMetadata) -> None:
        self._providers.append(RegisteredProvider(provider, metadata))

    def candidates(self, operation: str) -> tuple[RegisteredProvider, ...]:
        candidates = [p for p in self._providers if p.metadata.enabled and operation in p.metadata.supported_operations]
        if operation in {"classify", "rank"}:
            candidates.sort(key=lambda p: (p.metadata.estimated_cost, -p.metadata.priority))
        else:
            candidates.sort(key=lambda p: (-p.metadata.quality, -p.metadata.priority))
        if self._budget is not None and self._budget.remaining_budget()[0] < 0.2 * self._budget.config.monthly_budget_usd:
            candidates.sort(key=lambda p: (p.metadata.estimated_cost, -p.metadata.priority))
        return tuple(candidates)

    async def execute(self, request: AIRequest) -> AIResponse:
        candidates = self.candidates(request.operation)
        if not candidates:
            return await self._fake.execute(request)
        for registered in candidates:
            try:
                response = await registered.provider.execute(request)
                if response.success:
                    return response
            except Exception:
                continue
        return await self._fake.execute(request)
