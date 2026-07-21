import asyncio
import ast
import pathlib
import unittest
from datetime import UTC, datetime, timedelta

from core.scheduler.in_memory import InMemoryScheduler


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


class SchedulerTests(unittest.TestCase):
    def test_registers_periodic_task_and_calculates_next_run(self) -> None:
        clock = MutableClock(NOW)
        scheduler = InMemoryScheduler(clock=clock)

        async def callback() -> None:
            pass

        scheduler.register_periodic("task", 30, callback)

        self.assertEqual(scheduler.tasks()[0].task_id, "task")
        self.assertEqual(scheduler.next_run_at("task"), NOW + timedelta(seconds=30))

    def test_rejects_duplicate_task_id(self) -> None:
        scheduler = InMemoryScheduler(clock=MutableClock(NOW))

        async def callback() -> None:
            pass

        scheduler.register_periodic("task", 30, callback)
        with self.assertRaisesRegex(ValueError, "already registered"):
            scheduler.register_periodic("task", 60, callback)

    def test_runs_task_manually_and_updates_statistics(self) -> None:
        clock = MutableClock(NOW)
        scheduler = InMemoryScheduler(clock=clock)
        calls: list[str] = []

        async def callback() -> None:
            calls.append("called")

        scheduler.register_periodic("task", 10, callback)
        succeeded = asyncio.run(scheduler.run_task("task"))

        task = scheduler.tasks()[0]
        self.assertTrue(succeeded)
        self.assertEqual(calls, ["called"])
        self.assertEqual(task.run_count, 1)
        self.assertEqual(task.failure_count, 0)
        self.assertEqual(task.last_started_at, NOW)
        self.assertEqual(task.last_finished_at, NOW)
        self.assertEqual(task.next_run_at, NOW + timedelta(seconds=10))

    def test_runs_due_tasks(self) -> None:
        clock = MutableClock(NOW)
        scheduler = InMemoryScheduler(clock=clock)
        calls: list[str] = []

        async def callback() -> None:
            calls.append("due")

        scheduler.register_periodic("task", 10, callback)
        clock.now += timedelta(seconds=10)

        due = asyncio.run(scheduler.run_due())

        self.assertEqual(due, ("task",))
        self.assertEqual(calls, ["due"])

    def test_task_failure_does_not_stop_other_due_tasks(self) -> None:
        clock = MutableClock(NOW)
        scheduler = InMemoryScheduler(clock=clock)
        calls: list[str] = []

        async def failing() -> None:
            raise RuntimeError("boom")

        async def successful() -> None:
            calls.append("success")

        scheduler.register_periodic("failing", 10, failing)
        scheduler.register_periodic("successful", 10, successful)
        clock.now += timedelta(seconds=10)

        due = asyncio.run(scheduler.run_due())

        failing_stats, successful_stats = scheduler.tasks()
        self.assertEqual(due, ("failing", "successful"))
        self.assertEqual(calls, ["success"])
        self.assertEqual(failing_stats.failure_count, 1)
        self.assertIn("RuntimeError", failing_stats.last_error)
        self.assertEqual(successful_stats.run_count, 1)

    def test_disable_and_enable_create_new_schedule(self) -> None:
        clock = MutableClock(NOW)
        scheduler = InMemoryScheduler(clock=clock)

        async def callback() -> None:
            pass

        scheduler.register_periodic("task", 10, callback)
        scheduler.disable("task")
        self.assertIsNone(scheduler.next_run_at("task"))
        self.assertFalse(asyncio.run(scheduler.run_task("task")))

        clock.now += timedelta(seconds=5)
        scheduler.enable("task")
        self.assertEqual(scheduler.next_run_at("task"), clock.now + timedelta(seconds=10))

    def test_service_loop_uses_injected_sleep_and_propagates_cancellation(self) -> None:
        delays: list[float] = []

        async def cancelling_sleep(delay: float) -> None:
            delays.append(delay)
            raise asyncio.CancelledError

        scheduler = InMemoryScheduler(
            clock=MutableClock(NOW),
            sleep=cancelling_sleep,
            idle_sleep_seconds=2.0,
        )

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(scheduler.serve())

        self.assertEqual(delays, [2.0])


class SchedulerArchitectureTests(unittest.TestCase):
    def test_scheduler_has_no_forbidden_imports(self) -> None:
        forbidden = (
            "agents", "apscheduler", "backend", "celery", "core.collector",
            "core.source_manager", "redis", "sqlalchemy",
        )
        violations: list[str] = []
        for path in pathlib.Path("core/scheduler").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module and any(module == item or module.startswith(f"{item}.") for item in forbidden):
                    violations.append(f"{path}: {module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
