from datetime import datetime
from .metrics import cosine_similarity
from .types import SimilarityMatch, SimilarityResult

class SimilarityEngine:
    def __init__(self, embedding_engine) -> None: self._embedding_engine = embedding_engine

    async def compare(self, vector1, vector2) -> float | None:
        return cosine_similarity(vector1, vector2)

    async def compare_many(self, query_vector, candidate_vectors) -> tuple[float | None, ...]:
        return tuple(cosine_similarity(query_vector, vector) for vector in candidate_vectors)

    async def find_similar(self, query, candidates, threshold=0.0, top_k=10) -> SimilarityResult:
        if not isinstance(query, str) or not query.strip() or top_k <= 0: return SimilarityResult((), query if isinstance(query, str) else "")
        query_result = await self._embedding_engine.embed(query)
        if query_result.vector is None: return SimilarityResult((), query)
        values = []
        for index, candidate in enumerate(candidates or ()):
            text = candidate if isinstance(candidate, str) else getattr(candidate, "text", None) or (getattr(candidate, "payload", {}) or {}).get("title", "")
            if not isinstance(text, str) or not text.strip(): continue
            result = await self._embedding_engine.embed(text)
            score = cosine_similarity(query_result.vector.values, result.vector.values) if result.vector else None
            if score is not None and score >= threshold: values.append((candidate, score, index, self._timestamp(candidate)))
        values.sort(key=lambda value: (-value[1], -value[3], value[2]))
        return SimilarityResult(tuple(SimilarityMatch(item, score, rank + 1) for rank, (item, score, _, _) in enumerate(values[:top_k])), query)

    @staticmethod
    def _timestamp(item) -> float:
        value = getattr(item, "published_at", None) or (getattr(item, "payload", {}) or {}).get("published_at")
        if isinstance(value, datetime): return value.timestamp()
        try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError): return 0.0
