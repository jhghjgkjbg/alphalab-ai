import unittest
from datetime import UTC, datetime

from core.collector.base import BaseCollector
from core.collector.registry import CollectorRegistry
from core.collector.types import CollectorResult, CollectorStatus


class ExampleCollector(BaseCollector):
    @classmethod
    def name(cls) -> str:
        return "example"

    async def collect(self) -> CollectorResult:
        now = datetime.now(UTC)
        return CollectorResult(
            collector_name=self.name(),
            status=CollectorStatus.SUCCESS,
            started_at=now,
            finished_at=now,
        )


class CollectorRegistryTests(unittest.TestCase):
    def test_registers_and_returns_collector_type(self) -> None:
        registry = CollectorRegistry()

        registry.register(ExampleCollector)

        self.assertIs(registry.get("example"), ExampleCollector)
        self.assertEqual(dict(registry.registered()), {"example": ExampleCollector})

    def test_rejects_duplicate_collector_name(self) -> None:
        registry = CollectorRegistry()
        registry.register(ExampleCollector)

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(ExampleCollector)


if __name__ == "__main__":
    unittest.main()
