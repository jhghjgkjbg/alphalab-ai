import ast
import asyncio
import pathlib
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from core.collector.base import BaseCollector
from core.collector.events import CollectionCompleted
from core.collector.registry import CollectorRegistry
from core.collector.types import CollectorResult, CollectorStatus, SourceItem
from core.event_bus.in_memory import InMemoryEventBus
from core.source_manager.manager import SourceManager
from core.source_manager.registry import SourceRegistry
from core.source_manager.types import SourceDefinition, SourcePriority, SourceRunStatus


def definition(source_id: str = "source", enabled: bool = True) -> SourceDefinition:
    return SourceDefinition(
        source_id=source_id,
        collector_name=f"collector_{source_id}",
        enabled=enabled,
        interval_seconds=60,
        priority=SourcePriority.NORMAL,
        max_items=10,
        metadata={"owner": "test"},
    )


class SuccessfulCollector(BaseCollector):
    calls = 0

    @classmethod
    def name(cls) -> str:
        return "collector_source"

    async def collect(self) -> CollectorResult:
        type(self).calls += 1
        now = datetime.now(UTC)
        return CollectorResult(
            collector_name=self.name(), status=CollectorStatus.SUCCESS,
            started_at=now, finished_at=now,
            items=(SourceItem("source", "1", now, {"title": "Story"}),),
        )


class FailingCollector(BaseCollector):
    @classmethod
    def name(cls) -> str:
        return "collector_failing"

    async def collect(self) -> CollectorResult:
        raise RuntimeError("collector crashed")


class SourceRegistryTests(unittest.TestCase):
    def test_registers_gets_and_filters_sources(self) -> None:
        registry = SourceRegistry()
        source = definition()
        registry.register(source)

        self.assertIs(registry.get("source"), source)
        self.assertEqual(registry.all(), (source,))
        self.assertEqual(registry.enabled(), (source,))
        with self.assertRaises(TypeError):
            source.metadata["owner"] = "changed"

    def test_rejects_duplicate_source_id(self) -> None:
        registry = SourceRegistry()
        registry.register(definition())
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(definition())

    def test_enable_disable_replaces_immutable_definition(self) -> None:
        registry = SourceRegistry()
        original = definition()
        registry.register(original)

        disabled = registry.disable("source")
        enabled = registry.enable("source")

        self.assertTrue(original.enabled)
        self.assertFalse(disabled.enabled)
        self.assertTrue(enabled.enabled)
        self.assertIsNot(original, disabled)


class SourceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        SuccessfulCollector.calls = 0

    def test_runs_registered_collector_and_publishes_event(self) -> None:
        collectors = CollectorRegistry()
        collectors.register(SuccessfulCollector)
        sources = SourceRegistry()
        sources.register(definition())
        event_bus = InMemoryEventBus()
        events: list[CollectionCompleted] = []

        async def capture(event: CollectionCompleted) -> None:
            events.append(event)

        event_bus.subscribe(CollectionCompleted, capture)
        manager = SourceManager(collectors, sources, event_bus)
        correlation_id = uuid4()

        result = asyncio.run(manager.run_source("source", correlation_id))

        self.assertEqual(result.status, SourceRunStatus.SUCCESS)
        self.assertEqual(result.collected_count, 1)
        self.assertEqual(SuccessfulCollector.calls, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].correlation_id, correlation_id)

    def test_disabled_and_unknown_sources_do_not_run(self) -> None:
        collectors = CollectorRegistry()
        collectors.register(SuccessfulCollector)
        sources = SourceRegistry()
        sources.register(definition(enabled=False))
        manager = SourceManager(collectors, sources, InMemoryEventBus())

        disabled = asyncio.run(manager.run_source("source"))
        unknown = asyncio.run(manager.run_source("missing"))

        self.assertEqual(disabled.status, SourceRunStatus.SKIPPED)
        self.assertEqual(unknown.status, SourceRunStatus.NOT_FOUND)
        self.assertEqual(SuccessfulCollector.calls, 0)

    def test_factory_is_used_to_create_collector(self) -> None:
        collectors = CollectorRegistry()
        instance = SuccessfulCollector()
        collectors.register_factory(instance.name(), lambda: instance)
        sources = SourceRegistry()
        sources.register(definition())
        manager = SourceManager(collectors, sources, InMemoryEventBus())

        asyncio.run(manager.run_source("source"))

        self.assertEqual(SuccessfulCollector.calls, 1)

    def test_collector_failure_does_not_stop_next_source(self) -> None:
        collectors = CollectorRegistry()
        collectors.register(FailingCollector)
        collectors.register(SuccessfulCollector)
        sources = SourceRegistry()
        sources.register(definition("failing"))
        sources.register(definition("source"))
        manager = SourceManager(collectors, sources, InMemoryEventBus())

        results = asyncio.run(manager.run_enabled())

        self.assertEqual(
            [result.status for result in results],
            [SourceRunStatus.FAILED, SourceRunStatus.SUCCESS],
        )
        self.assertEqual(SuccessfulCollector.calls, 1)


class SourceManagerArchitectureTests(unittest.TestCase):
    def test_source_manager_has_no_forbidden_imports(self) -> None:
        forbidden = ("agents", "backend", "core.enrichment", "core.knowledge", "core.scoring", "core.scheduler")
        violations: list[str] = []
        for path in pathlib.Path("core/source_manager").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module and any(module == item or module.startswith(f"{item}.") for item in forbidden):
                    violations.append(f"{path}: {module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
