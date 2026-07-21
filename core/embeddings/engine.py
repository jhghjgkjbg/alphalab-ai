import asyncio
from .cache import InMemoryEmbeddingCache
from .types import *

class EmbeddingEngine:
    def __init__(self, provider, cache=None): self._provider=provider; self._cache=cache; self._locks={}; self._guard=asyncio.Lock()
    def _request(self,text,model,dimensions): return EmbeddingRequest(" ".join(text.strip().split()),model,dimensions)
    async def embed(self,text,model=None,dimensions=None):
        model=model or self._provider.metadata["model"]; dimensions=dimensions or self._provider.metadata["dimensions"]; key= self._cache.key(text,self._provider.metadata["name"],model,dimensions) if self._cache else None
        async with self._guard: lock=self._locks.setdefault(key or text,asyncio.Lock())
        async with lock:
            if self._cache:
                cached=await self._cache.get(key)
                if cached: return EmbeddingResult(cached.vector,cached.error,True,cached.input_units)
            try: result=await self._provider.embed(self._request(text,model,dimensions))
            except Exception as exc: result=EmbeddingResult(None,EmbeddingError("provider_error",str(exc)),False,len(text))
            if self._cache: await self._cache.set(key,result)
            return result
    async def embed_batch(self,texts,model=None,dimensions=None):
        results=tuple([await self.embed(t,model,dimensions) for t in texts]); return EmbeddingBatchResult(results,sum(r.vector is not None for r in results),sum(r.error is not None for r in results),sum(r.cached for r in results))
