from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AIRequest:
    operation: str
    input: str
    model: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class AIUsage:
    provider: str
    model: str
    input_units: int
    output_units: int
    estimated_cost: float
    cached: bool = False


@dataclass(frozen=True, slots=True)
class AIError:
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class AIResponse:
    success: bool
    output: Any
    usage: AIUsage | None = None
    error: AIError | None = None

