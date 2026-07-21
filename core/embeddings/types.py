from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    text: str
    model: str
    dimensions: int | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

@dataclass(frozen=True, slots=True)
class EmbeddingError:
    code: str
    message: str
    retryable: bool = False

@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    values: tuple[float, ...]
    model: str
    dimensions: int
    normalized: bool

@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: EmbeddingVector | None
    error: EmbeddingError | None
    cached: bool
    input_units: int

@dataclass(frozen=True, slots=True)
class EmbeddingBatchResult:
    results: tuple[EmbeddingResult, ...]
    successful: int
    failed: int
    cached: int
