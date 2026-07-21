import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core.scheduler.base import AsyncCallback, Scheduler
from core.scheduler.types import ScheduledTask


Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(slots=True)
class _TaskState:
    task_id: str
    interval_seconds: float
    callback: AsyncCallback
    enabled: bool
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    next_run_at: datetime | None = None
    run_count: int = 0
    failure_count: int = 0
    last_error: str | None = None


class InMemoryScheduler(Scheduler):
    def __init__(
        self,
        *,
        clock: Clock | None = None,
        sleep: Sleep | None = None,
        idle_sleep_seconds: float = 1.0,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep or asyncio.sleep
        self._idle_sleep_seconds = idle_sleep_seconds
        self._tasks: dict[str, _TaskState] = {}

    def register_periodic(
        self,
        task_id: str,
        interval_seconds: float,
        callback: AsyncCallback,
        *,
        enabled: bool = True,
    ) -> None:
        if not task_id:
            raise ValueError("task_id must not be empty")
        if task_id in self._tasks:
            raise ValueError(f"task is already registered: {task_id}")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        state = _TaskState(task_id, interval_seconds, callback, enabled)
        if enabled:
            state.next_run_at = self._clock() + timedelta(seconds=interval_seconds)
        self._tasks[task_id] = state

    async def run_task(self, task_id: str) -> bool:
        state = self._tasks[task_id]
        if not state.enabled:
            return False

        state.last_started_at = self._clock()
        state.run_count += 1
        succeeded = True
        try:
            await state.callback()
            state.last_error = None
        except Exception as exc:
            succeeded = False
            state.failure_count += 1
            state.last_error = f"{type(exc).__name__}: {exc}"
        finally:
            state.last_finished_at = self._clock()
            state.next_run_at = state.last_finished_at + timedelta(
                seconds=state.interval_seconds
            )
        return succeeded

    async def run_due(self) -> tuple[str, ...]:
        now = self._clock()
        due_ids = tuple(
            state.task_id
            for state in self._tasks.values()
            if state.enabled
            and state.next_run_at is not None
            and state.next_run_at <= now
        )
        for task_id in due_ids:
            await self.run_task(task_id)
        return due_ids

    def enable(self, task_id: str) -> None:
        state = self._tasks[task_id]
        if not state.enabled:
            state.enabled = True
            state.next_run_at = self._clock() + timedelta(seconds=state.interval_seconds)

    def disable(self, task_id: str) -> None:
        state = self._tasks[task_id]
        state.enabled = False
        state.next_run_at = None

    def tasks(self) -> tuple[ScheduledTask, ...]:
        return tuple(self._snapshot(state) for state in self._tasks.values())

    def next_run_at(self, task_id: str) -> datetime | None:
        return self._tasks[task_id].next_run_at

    async def serve(self) -> None:
        while True:
            await self.run_due()
            await self._sleep(self._sleep_delay())

    def _sleep_delay(self) -> float:
        now = self._clock()
        next_runs = tuple(
            state.next_run_at
            for state in self._tasks.values()
            if state.enabled and state.next_run_at is not None
        )
        if not next_runs:
            return self._idle_sleep_seconds
        return max(0.0, min((next_run - now).total_seconds() for next_run in next_runs))

    @staticmethod
    def _snapshot(state: _TaskState) -> ScheduledTask:
        return ScheduledTask(
            task_id=state.task_id,
            interval_seconds=state.interval_seconds,
            enabled=state.enabled,
            last_started_at=state.last_started_at,
            last_finished_at=state.last_finished_at,
            next_run_at=state.next_run_at,
            run_count=state.run_count,
            failure_count=state.failure_count,
            last_error=state.last_error,
        )
