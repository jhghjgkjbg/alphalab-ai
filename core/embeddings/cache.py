import asyncio
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from dataclasses import dataclass
from .types import EmbeddingResult

@dataclass(frozen=True, slots=True)
class EmbeddingCacheStats:
    entries: int; hits: int; misses: int; evictions: int; expired: int

class InMemoryEmbeddingCache:
    def __init__(self, max_entries=100, ttl_seconds=3600):
        self._max=max_entries; self._ttl=ttl_seconds; self._items=OrderedDict(); self._hits=self._misses=self._evictions=self._expired=0; self._lock=asyncio.Lock()
    @staticmethod
    def key(text, provider, model, dimensions): return (" ".join(text.strip().split()), provider, model, dimensions)
    async def get(self, key):
        async with self._lock:
            item=self._items.get(key)
            if not item: self._misses+=1; return None
            result, expires=item
            if datetime.now(UTC)>=expires: del self._items[key]; self._expired+=1; self._misses+=1; return None
            self._items.move_to_end(key); self._hits+=1; return result
    async def set(self, key, result, ttl_seconds=None):
        if result.vector is None or result.error is not None: return False
        async with self._lock:
            self._items[key]=(result, datetime.now(UTC)+timedelta(seconds=ttl_seconds or self._ttl)); self._items.move_to_end(key)
            while len(self._items)>self._max: self._items.popitem(last=False); self._evictions+=1
        return True
    async def delete(self,key):
        async with self._lock: return self._items.pop(key,None) is not None
    async def clear(self):
        async with self._lock: self._items.clear()
    async def stats(self):
        async with self._lock: return EmbeddingCacheStats(len(self._items),self._hits,self._misses,self._evictions,self._expired)
