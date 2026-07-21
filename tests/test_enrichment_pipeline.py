import ast
import asyncio
import pathlib
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from core.collector.types import SourceItem
from core.enrichment.engine import EnrichmentEngine
from core.enrichment.events import KnowledgeEnriched
from core.enrichment.handler import EnrichmentHandler
from core.enrichment.providers import DeterministicSummaryProvider
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.events import KnowledgeStored
from core.knowledge.normalizer import KnowledgeNormalizer
from core.knowledge.repository import InMemoryKnowledgeRepository


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def make_document():
    return KnowledgeNormalizer(clock=lambda: NOW).normalize(
        SourceItem(
            source="hacker_news",
            external_id="42",
            collected_at=NOW,
            payload={"title": "AlphaLab", "content": "Canonical knowledge platform"},
        )
    )


def stored_event(document, correlation_id=None):
    return KnowledgeStored(
        event_id=uuid4(), event_version=1, occurred_at=NOW,
        document_id=document.id, source=document.source,
        source_external_id=document.source_external_id,
        correlation_id=correlation_id or uuid4(),
    )


class RejectingRepository:
    def __init__(self, document) -> None:
        self.document = document

    def get(self, document_id):
        return self.document if document_id == self.document.id else None

    def update(self, document, expected_version):
        return False


class RepositoryVersionTests(unittest.TestCase):
    def test_optimistic_update_succeeds_and_preserves_original(self) -> None:
        repository = InMemoryKnowledgeRepository()
        original = make_document()
        repository.add(original)
        enriched = replace(original, summary="Summary", version=2, updated_at=NOW)

        updated = repository.update(enriched, expected_version=1)

        self.assertTrue(updated)
        self.assertEqual(original.version, 1)
        self.assertEqual(original.summary, "")
        self.assertEqual(repository.get(original.id), enriched)
        self.assertEqual(enriched.id, original.id)
        self.assertEqual(enriched.created_at, original.created_at)

    def test_optimistic_update_rejects_version_conflict(self) -> None:
        repository = InMemoryKnowledgeRepository()
        original = make_document()
        repository.add(original)
        enriched = replace(original, version=2)

        self.assertFalse(repository.update(enriched, expected_version=2))
        self.assertIs(repository.get(original.id), original)


class EnrichmentHandlerTests(unittest.TestCase):
    def test_publishes_event_only_after_successful_update(self) -> None:
        repository = InMemoryKnowledgeRepository()
        original = make_document()
        repository.add(original)
        event_bus = InMemoryEventBus()
        handler = EnrichmentHandler(
            EnrichmentEngine(summary_providers=(DeterministicSummaryProvider(),)),
            repository,
            event_bus,
        )
        events: list[KnowledgeEnriched] = []

        async def capture(event: KnowledgeEnriched) -> None:
            events.append(event)

        event_bus.subscribe(KnowledgeEnriched, capture)
        correlation_id = uuid4()
        asyncio.run(handler.handle(stored_event(original, correlation_id)))

        current = repository.get(original.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].previous_version, 1)
        self.assertEqual(events[0].current_version, 2)
        self.assertEqual(events[0].correlation_id, correlation_id)
        self.assertEqual(current.version, 2)
        self.assertEqual(original.version, 1)
        self.assertEqual(current.id, original.id)

    def test_does_not_publish_on_version_conflict(self) -> None:
        original = make_document()
        repository = RejectingRepository(original)
        event_bus = InMemoryEventBus()
        handler = EnrichmentHandler(
            EnrichmentEngine(summary_providers=(DeterministicSummaryProvider(),)),
            repository,
            event_bus,
        )
        events: list[KnowledgeEnriched] = []

        async def capture(event: KnowledgeEnriched) -> None:
            events.append(event)

        event_bus.subscribe(KnowledgeEnriched, capture)
        asyncio.run(handler.handle(stored_event(original)))

        self.assertEqual(events, [])


class EnrichmentArchitectureTests(unittest.TestCase):
    def test_enrichment_has_no_forbidden_imports(self) -> None:
        violations: list[str] = []
        forbidden = ("agents", "backend", "core.collector", "core.event_bus", "core.scoring")
        for path in pathlib.Path("core/enrichment").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module and any(module == item or module.startswith(f"{item}.") for item in forbidden):
                    violations.append(f"{path}: {module}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
