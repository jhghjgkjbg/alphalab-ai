import hashlib
from .types import *

class FakeEmbeddingProvider:
    def __init__(self, dimensions: int = 8, model: str = "fake", fail: bool = False, max_batch_size: int = 16) -> None:
        self._metadata = {"name": "fake", "model": model, "enabled": True, "dimensions": dimensions, "max_batch_size": max_batch_size, "estimated_cost_per_1000_units": 0.0, "local": True}
        self.fail = fail
    @property
    def metadata(self): return self._metadata
    async def embed(self, request):
        if self.fail: return EmbeddingResult(None, EmbeddingError("provider_error", "fake failure"), False, len(request.text))
        digest = hashlib.sha256(request.text.encode()).digest(); values = tuple((digest[i % len(digest)] / 255.0) * 2 - 1 for i in range(request.dimensions or self._metadata["dimensions"]))
        return EmbeddingResult(EmbeddingVector(values, request.model, len(values), False), None, False, len(request.text))
    async def embed_batch(self, requests):
        results = tuple([await self.embed(r) for r in requests]); return EmbeddingBatchResult(results, sum(r.vector is not None for r in results), sum(r.error is not None for r in results), 0)
