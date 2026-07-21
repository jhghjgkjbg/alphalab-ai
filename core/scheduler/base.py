from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from core.scheduler.types import ScheduledTask


AsyncCallback = Callable[[], Awaitable[Any]]


class Scheduler(ABC):
    @abstractmethod
    def register_periodic(
        self,
        task_id: str,
        interval_seconds: float,
        callback: AsyncCallback,
        *,
        enabled: bool = True,
    ) -> None: ...

    @abstractmethod
    async def run_task(self, task_id: str) -> bool: ...

    @abstractmethod
    async def run_due(self) -> tuple[str, ...]: ...

    @abstractmethod
    def enable(self, task_id: str) -> None: ...

    @abstractmethod
    def disable(self, task_id: str) -> None: ...

    @abstractmethod
    def tasks(self) -> tuple[ScheduledTask, ...]: ...

    @abstractmethod
    def next_run_at(self, task_id: str) -> datetime | None: ...

    @abstractmethod
    async def serve(self) -> None: ...
