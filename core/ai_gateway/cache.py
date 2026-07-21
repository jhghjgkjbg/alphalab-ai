from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .types import AIResponse


@dataclass(frozen=True, slots=True)
class AICacheKey:
    operation: str
    provider: str
    model: str
    normalized_input: str
    parameters: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def build(cls, operation: str, provider: str, model: str, input_text: str, parameters: dict[str, Any] | None = None) -> "AICacheKey":
        normalized = " ".join(input_text.strip().split()).lower()
        params = tuple(sorted((parameters or {}).items()))
        return cls(operation, provider, model, normalized, params)


@dataclass(frozen=True, slots=True)
class AICacheEntry:
    response: AIResponse
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


@dataclass(frozen=True, slots=True)
class AICacheStats:
    entries: int
    hits: int
    misses: int
    evictions: int
    expired: int


class InMemoryAICache:
    def __init__(self, max_entries: int = 100, default_ttl_seconds: float = 3600) -> None:
        if max_entries <= 0 or default_ttl_seconds <= 0:
            raise ValueError("cache limits must be positive")
        self._max = max_entries
        self._ttl = default_ttl_seconds
        self._entries: OrderedDict[AICacheKey, AICacheEntry] = OrderedDict()
        self._hits = self._misses = self._evictions = self._expired = 0
        self._lock = asyncio.Lock()

    async def get(self, key: AICacheKey) -> AIResponse | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if datetime.now(UTC) >= entry.expires_at:
                del self._entries[key]; self._expired += 1; self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._entries[key] = AICacheEntry(entry.response, entry.created_at, entry.expires_at, entry.hit_count + 1)
            self._hits += 1
            return entry.response

    async def set(self, key: AICacheKey, response: AIResponse, ttl_seconds: float | None = None) -> bool:
        if not response.success or response.error is not None:
            return False
        async with self._lock:
            now = datetime.now(UTC)
            self._entries[key] = AICacheEntry(response, now, now + timedelta(seconds=ttl_seconds or self._ttl))
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False); self._evictions += 1
        return True

    async def delete(self, key: AICacheKey) -> bool:
        async with self._lock:
            return self._entries.pop(key, None) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()

    async def stats(self) -> AICacheStats:
        async with self._lock:
            return AICacheStats(len(self._entries), self._hits, self._misses, self._evictions, self._expired)
