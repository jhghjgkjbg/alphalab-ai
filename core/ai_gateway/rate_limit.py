from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    requests_per_minute: int
    requests_per_hour: int
    max_concurrent_requests: int
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RateLimitState:
    minute_count: int
    hour_count: int
    active_requests: int
    minute_reset_at: datetime
    hour_reset_at: datetime


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    reason: str
    retry_after_seconds: float
    remaining_minute: int
    remaining_hour: int
    available_concurrency: int


class InMemoryRateLimiter:
    def __init__(self, config: RateLimitConfig, clock: Callable[[], datetime] | None = None) -> None:
        if min(config.requests_per_minute, config.requests_per_hour, config.max_concurrent_requests) < 0:
            raise ValueError("rate limits must not be negative")
        self._config = config
        now = (clock or (lambda: datetime.now(UTC)))()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._state = RateLimitState(0, 0, 0, now + timedelta(minutes=1), now + timedelta(hours=1))
        self._lock = asyncio.Lock()

    def _refresh(self, now: datetime) -> None:
        if now >= self._state.hour_reset_at:
            self._state = replace(self._state, minute_count=0, hour_count=0, minute_reset_at=now + timedelta(minutes=1), hour_reset_at=now + timedelta(hours=1))
        elif now >= self._state.minute_reset_at:
            self._state = replace(self._state, minute_count=0, minute_reset_at=now + timedelta(minutes=1))

    def _decision(self, allowed: bool, reason: str, now: datetime) -> RateLimitDecision:
        remaining_m = max(0, self._config.requests_per_minute - self._state.minute_count)
        remaining_h = max(0, self._config.requests_per_hour - self._state.hour_count)
        available = max(0, self._config.max_concurrent_requests - self._state.active_requests)
        retry = 0.0 if allowed else max(0.0, (self._state.minute_reset_at - now).total_seconds())
        if reason == "hour_limit_exceeded": retry = max(0.0, (self._state.hour_reset_at - now).total_seconds())
        return RateLimitDecision(allowed, reason, retry, remaining_m, remaining_h, available)

    async def acquire(self) -> RateLimitDecision:
        async with self._lock:
            now = self._clock(); self._refresh(now)
            if not self._config.enabled: return self._decision(True, "disabled", now)
            if self._state.active_requests >= self._config.max_concurrent_requests: return self._decision(False, "concurrency_limit_exceeded", now)
            if self._state.minute_count >= self._config.requests_per_minute: return self._decision(False, "minute_limit_exceeded", now)
            if self._state.hour_count >= self._config.requests_per_hour: return self._decision(False, "hour_limit_exceeded", now)
            self._state = replace(self._state, minute_count=self._state.minute_count + 1, hour_count=self._state.hour_count + 1, active_requests=self._state.active_requests + 1)
            return self._decision(True, "allowed", now)

    async def release(self) -> None:
        async with self._lock:
            self._state = replace(self._state, active_requests=max(0, self._state.active_requests - 1))

    async def inspect(self) -> RateLimitState:
        async with self._lock:
            self._refresh(self._clock()); return self._state

    async def reset(self) -> None:
        async with self._lock:
            now = self._clock(); self._state = RateLimitState(0, 0, 0, now + timedelta(minutes=1), now + timedelta(hours=1))
