import asyncio
from dataclasses import replace
from .budget import BudgetManager
from .cache import AICacheKey, InMemoryAICache
from .protocol import AIProvider
from .rate_limit import InMemoryRateLimiter
from .router import AIRouter
from .types import AIError, AIRequest, AIResponse


class AIGateway:
    def __init__(self, provider: AIProvider | None = None, *, disabled: bool = False, cache: InMemoryAICache | None = None, budget: BudgetManager | None = None, rate_limiter: InMemoryRateLimiter | None = None, router: AIRouter | None = None) -> None:
        self._provider = provider
        self._disabled = disabled
        self._cache, self._budget, self._rate_limiter = cache, budget, rate_limiter
        self._router = router
        self._key_locks: dict[AICacheKey, asyncio.Lock] = {}
        self._key_locks_guard = asyncio.Lock()

    async def execute(self, request: AIRequest) -> AIResponse:
        if self._disabled:
            return AIResponse(False, None, error=AIError("ai_disabled", "AI Gateway is disabled"))
        if self._provider is None:
            if self._router is not None:
                return await self._router.execute(request)
            return AIResponse(False, None, error=AIError("provider_missing", "AI provider is not configured"))
        key = AICacheKey.build(request.operation, getattr(self._provider, "name", "provider"), request.model or "default", request.input, dict(request.metadata))
        async with self._key_locks_guard:
            lock = self._key_locks.setdefault(key, asyncio.Lock())
        async with lock:
            if self._cache is not None:
                cached = await self._cache.get(key)
                if cached is not None:
                    return replace(cached, usage=replace(cached.usage, cached=True) if cached.usage else None)
            estimated = dict(request.metadata).get("estimated_cost", 0.0)
            if self._budget is not None:
                decision = self._budget.can_execute(float(estimated))
                if not decision.allowed:
                    return AIResponse(False, None, error=AIError("budget_rejected", decision.reason))
            acquired = False
            if self._rate_limiter is not None:
                decision = await self._rate_limiter.acquire()
                if not decision.allowed:
                    return AIResponse(False, None, error=AIError("rate_limit_rejected", decision.reason))
                acquired = True
            try:
                response = await self._provider.execute(request)
            except Exception as exc:
                return AIResponse(False, None, error=AIError("provider_error", str(exc) or type(exc).__name__))
            finally:
                if acquired:
                    await self._rate_limiter.release()
            if not isinstance(response, AIResponse):
                return AIResponse(False, None, error=AIError("invalid_response", "Provider returned invalid response"))
            if response.success:
                if self._budget is not None and response.usage is not None:
                    self._budget.register_usage(response.usage.estimated_cost)
                if self._cache is not None:
                    await self._cache.set(key, response)
            return response

    async def classify(self, text: str, model: str | None = None) -> AIResponse:
        return await self.execute(AIRequest("classify", text, model))

    async def summarize(self, text: str, model: str | None = None) -> AIResponse:
        return await self.execute(AIRequest("summarize", text, model))

    async def rank(self, text: str, model: str | None = None) -> AIResponse:
        return await self.execute(AIRequest("rank", text, model))
