import ast
import asyncio
import io
import pathlib
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from core.collector.types import SourceItem
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.normalizer import KnowledgeNormalizer
from core.knowledge.repository import InMemoryKnowledgeRepository
from core.publication.engine import InMemoryPublicationLedger, PublicationEngine
from core.publication.events import (
    PublicationCandidateCreated,
    PublicationCompleted,
    PublicationRejected,
)
from core.publication.handler import PublicationHandler
from core.publication.policy import ScoreThresholdPolicy
from core.publication.publishers import ConsolePublisher, PublisherRegistry
from core.publication.types import PublicationCandidate, PublishResult
from core.scoring.events import ScoringCompleted


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def repository_with_document():
    repository = InMemoryKnowledgeRepository()
    document = KnowledgeNormalizer(clock=lambda: NOW).normalize(
        SourceItem(
            source="hacker_news", external_id="42", collected_at=NOW,
            payload={"title": "OpenAI story", "url": "https://example.com/story"},
        )
    )
    repository.add(document)
    return repository, document


def scoring(document, score: int = 60, correlation_id=None):
    return ScoringCompleted(
        event_id=uuid4(), event_version=1, occurred_at=NOW,
        source=document.source, external_id=document.source_external_id,
        total_score=score, details=(), reasons=("scored",),
        correlation_id=correlation_id or uuid4(),
    )


class RecordingPublisher:
    def __init__(self, channel: str, calls: list[str], *, fail: bool = False) -> None:
        self._channel = channel
        self._calls = calls
        self._fail = fail

    @property
    def channel_name(self) -> str:
        return self._channel

    async def publish(self, candidate: PublicationCandidate) -> PublishResult:
        self._calls.append(self._channel)
        if self._fail:
            raise RuntimeError("publisher failed")
        return PublishResult(self._channel, True, "external", NOW, None)


class PublisherRegistryTests(unittest.TestCase):
    def test_rejects_duplicate_channel(self) -> None:
        registry = PublisherRegistry()
        registry.register(ConsolePublisher(io.StringIO()))
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(ConsolePublisher(io.StringIO()))
        self.assertEqual(registry.channels(), ("console",))


class PublicationHandlerTests(unittest.TestCase):
    def build_handler(self, score_channels=("console",), publishers=()):
        repository, document = repository_with_document()
        event_bus = InMemoryEventBus()
        registry = PublisherRegistry()
        for publisher in publishers:
            registry.register(publisher)
        engine = PublicationEngine(
            ScoreThresholdPolicy(50, score_channels, clock=lambda: NOW),
            registry,
            clock=lambda: NOW,
        )
        ledger = InMemoryPublicationLedger()
        return PublicationHandler(engine, repository, ledger, event_bus), event_bus, document, ledger

    def test_rejection_does_not_call_publisher_and_emits_event(self) -> None:
        calls: list[str] = []
        publisher = RecordingPublisher("console", calls)
        handler, event_bus, document, _ = self.build_handler(publishers=(publisher,))
        rejected: list[PublicationRejected] = []

        async def capture(event: PublicationRejected) -> None:
            rejected.append(event)

        event_bus.subscribe(PublicationRejected, capture)
        correlation_id = uuid4()
        result = asyncio.run(handler.handle(scoring(document, 49, correlation_id)))

        self.assertTrue(result.rejected)
        self.assertEqual(calls, [])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].correlation_id, correlation_id)

    def test_candidate_event_precedes_publisher_and_completed_contains_results(self) -> None:
        order: list[str] = []
        publisher = RecordingPublisher("console", order)
        handler, event_bus, document, ledger = self.build_handler(publishers=(publisher,))
        completed: list[PublicationCompleted] = []

        async def candidate_capture(_: PublicationCandidateCreated) -> None:
            order.append("candidate")

        async def completed_capture(event: PublicationCompleted) -> None:
            order.append("completed")
            completed.append(event)

        event_bus.subscribe(PublicationCandidateCreated, candidate_capture)
        event_bus.subscribe(PublicationCompleted, completed_capture)
        correlation_id = uuid4()
        result = asyncio.run(handler.handle(scoring(document, 60, correlation_id)))

        self.assertEqual(order, ["candidate", "console", "completed"])
        self.assertTrue(result.accepted)
        self.assertTrue(completed[0].results[0].success)
        self.assertEqual(completed[0].correlation_id, correlation_id)
        self.assertTrue(ledger.is_processed(result.candidate_id))

    def test_publisher_failure_does_not_stop_other_channels(self) -> None:
        calls: list[str] = []
        handler, _, document, _ = self.build_handler(
            score_channels=("broken", "working"),
            publishers=(
                RecordingPublisher("broken", calls, fail=True),
                RecordingPublisher("working", calls),
            ),
        )

        result = asyncio.run(handler.handle(scoring(document)))

        self.assertEqual(calls, ["broken", "working"])
        self.assertEqual([item.success for item in result.results], [False, True])

    def test_ledger_prevents_repeated_publication_and_completed_event(self) -> None:
        calls: list[str] = []
        handler, event_bus, document, _ = self.build_handler(
            publishers=(RecordingPublisher("console", calls),)
        )
        completed: list[PublicationCompleted] = []

        async def capture(event: PublicationCompleted) -> None:
            completed.append(event)

        event_bus.subscribe(PublicationCompleted, capture)
        event = scoring(document)

        first = asyncio.run(handler.handle(event))
        second = asyncio.run(handler.handle(event))

        self.assertFalse(first.idempotent)
        self.assertTrue(second.idempotent)
        self.assertEqual(calls, ["console"])
        self.assertEqual(len(completed), 1)


class PublicationArchitectureTests(unittest.TestCase):
    def test_publication_has_no_forbidden_imports(self) -> None:
        forbidden = (
            "agents", "backend", "core.collector", "core.enrichment",
            "core.scheduler", "core.source_manager", "redis", "sqlalchemy",
            "telegram",
        )
        violations: list[str] = []
        for path in pathlib.Path("core/publication").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module and any(module == item or module.startswith(f"{item}.") for item in forbidden):
                    violations.append(f"{path}: {module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
