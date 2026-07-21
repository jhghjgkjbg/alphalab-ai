from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class SimilarityRequest:
    query: str
    threshold: float
    top_k: int

@dataclass(frozen=True, slots=True)
class SimilarityMatch:
    item: Any
    similarity: float
    rank: int

@dataclass(frozen=True, slots=True)
class SimilarityResult:
    matches: tuple[SimilarityMatch, ...]
    query: str
