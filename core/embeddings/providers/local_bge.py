from __future__ import annotations

import asyncio
from typing import Any, Callable

from ..types import EmbeddingBatchResult, EmbeddingError, EmbeddingRequest, EmbeddingResult, EmbeddingVector


class LocalBGEEmbeddingProvider:
    _models: dict[tuple[str, str], Any] = {}
    _locks: dict[tuple[str, str], asyncio.Lock] = {}

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", device: str | None = None, batch_size: int = 32, normalize_embeddings: bool = True, model_factory: Callable[[str, str], Any] | None = None) -> None:
        if batch_size <= 0: raise ValueError("batch_size must be positive")
        self.model_name, self.device, self.batch_size, self.normalize_embeddings = model, device or "cpu", batch_size, normalize_embeddings
        self._factory = model_factory

    @property
    def metadata(self):
        return {"name": "local_bge", "model": self.model_name, "enabled": True, "dimensions": None, "max_batch_size": self.batch_size, "estimated_cost_per_1000_units": 0.0, "local": True}

    async def _model(self):
        key = (self.model_name, self.device)
        if key not in self._locks: self._locks[key] = asyncio.Lock()
        async with self._locks[key]:
            if key not in self._models:
                def load():
                    if self._factory: return self._factory(self.model_name, self.device)
                    from sentence_transformers import SentenceTransformer
                    return SentenceTransformer(self.model_name, device=self.device)
                self._models[key] = await asyncio.to_thread(load)
        return self._models[key]

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        result = await self.embed_batch((request,))
        return result.results[0]

    async def embed_batch(self, requests: tuple[EmbeddingRequest, ...]) -> EmbeddingBatchResult:
        if any(not r.text.strip() or not r.model for r in requests):
            results = tuple(EmbeddingResult(None, EmbeddingError("invalid_request", "text and model are required"), False, len(r.text)) for r in requests)
            return EmbeddingBatchResult(results, 0, len(results), 0)
        try:
            model = await self._model(); vectors = []
            for start in range(0, len(requests), self.batch_size):
                batch = requests[start:start + self.batch_size]
                encoded = await asyncio.to_thread(model.encode, [r.text for r in batch], batch_size=self.batch_size, normalize_embeddings=self.normalize_embeddings, convert_to_numpy=True)
                vectors.extend(encoded)
            results = tuple(EmbeddingResult(EmbeddingVector(tuple(float(x) for x in vector), requests[i].model, len(vector), self.normalize_embeddings), None, False, len(requests[i].text)) for i, vector in enumerate(vectors))
            return EmbeddingBatchResult(results, len(results), 0, 0)
        except Exception as exc:
            results = tuple(EmbeddingResult(None, EmbeddingError("provider_error", str(exc) or type(exc).__name__), False, len(r.text)) for r in requests)
            return EmbeddingBatchResult(results, 0, len(results), 0)
