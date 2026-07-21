from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class PipelineMetrics:
    collection_duration_ms: float = 0.0
    editorial_duration_ms: float = 0.0
    ai_duration_ms: float = 0.0
    rendering_duration_ms: float = 0.0
    delivery_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    candidates_collected: int = 0
    candidates_accepted: int = 0
    duplicates_removed: int = 0
    articles_generated: int = 0
    delivery_success_count: int = 0
    delivery_failure_count: int = 0


class PipelineMetricsCollector:
    def __init__(self):
        self._started = perf_counter(); self._marks = {}; self._counts = {}

    def mark(self, stage): self._marks[stage] = perf_counter()
    def count(self, name, value=1): self._counts[name] = self._counts.get(name, 0) + int(value)
    def finish(self):
        def duration(name, end_name=None):
            start = self._marks.get(name, self._started); end = self._marks.get(end_name or name + "_end", perf_counter()); return round(max(0, end-start)*1000, 3)
        return PipelineMetrics(duration("collection"), duration("editorial"), duration("ai"), duration("rendering"), duration("delivery"), round((perf_counter()-self._started)*1000, 3), self._counts.get("candidates_collected", 0), self._counts.get("candidates_accepted", 0), self._counts.get("duplicates_removed", 0), self._counts.get("articles_generated", 0), self._counts.get("delivery_success_count", 0), self._counts.get("delivery_failure_count", 0))
