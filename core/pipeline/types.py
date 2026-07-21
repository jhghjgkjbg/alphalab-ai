from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class StageFailure:
    record: str
    exception_type: str
    message: str
    traceback: str

@dataclass(frozen=True, slots=True)
class StageStats:
    name: str
    received: int
    produced: int
    failed: int = 0
    failures: tuple[StageFailure, ...] = ()

@dataclass(frozen=True, slots=True)
class PipelineStats:
    stages: tuple[StageStats, ...]

@dataclass(frozen=True, slots=True)
class PipelineResult:
    items: tuple[Any, ...]
    stats: PipelineStats
