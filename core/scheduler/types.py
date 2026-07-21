from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ScheduledTask:
    task_id: str
    interval_seconds: float
    enabled: bool
    last_started_at: datetime | None
    last_finished_at: datetime | None
    next_run_at: datetime | None
    run_count: int
    failure_count: int
    last_error: str | None
