import asyncio
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from core.collector.events import CollectionCompleted
from core.collector.types import CollectorStatus, SourceItem
from core.enrichment.engine import EnrichmentEngine
from core.enrichment.events import KnowledgeEnriched
from core.enrichment.handler import EnrichmentHandler
from core.enrichment.providers import DeterministicSummaryProvider
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.events import KnowledgeStored
from core.knowledge.handler import KnowledgeHandler
from core.knowledge.normalizer import KnowledgeNormalizer
from core.knowledge.repository import InMemoryKnowledgeRepository
from core.scoring.base import BaseRule
from core.scoring.engine import ScoringEngine
from core.scoring.events import ScoringCompleted
from core.scoring.handler import ScoringHandler
from core.scoring.rules import KeywordRule, SourceTrustRule
from core.scoring.types import RuleResult, ScorableItem


def make_item(external_id: str = "1") -> SourceItem:
    return SourceItem(
        source="hacker_news",
        external_id=external_id,
        collected_at=datetime.now(UTC),
        payload={"title": "OpenAI announces GPT", "url": "https://example.com/story"},
    )


def make_collection_event(
    item: SourceItem,
    correlation_id: UUID | None = None,
) -> CollectionCompleted:
    return CollectionCompleted(
        event_id=uuid4(),
        event_version=1,
        occurred_at=datetime.now(UTC),
        collector_name="hacker_news",
        status=CollectorStatus.SUCCESS,
        items=(item,),
        errors=(),
        correlation_id=correlation_id or uuid4(),
    )


class FailingRule(BaseRule):
    @classmethod
    def name(cls) -> str:
        return "failing"

    async def score(self, item: ScorableItem) -> RuleResult:
        raise RuntimeError("scoring failed")


class KnowledgeEventTests(unittest.TestCase):
    def test_publishes_knowledge_stored_only_for_new_document(self) -> None:
        event_bus = InMemoryEventBus()
        repository = InMemoryKnowledgeRepository()
        handler = KnowledgeHandler(repository, event_bus)
        received: list[KnowledgeStored] = []

        async def capture(event: KnowledgeStored) -> None:
            received.append(event)

        event_bus.subscribe(KnowledgeStored, capture)
        item = make_item()

        asyncio.run(handler.handle(make_collection_event(item)))
        asyncio.run(handler.handle(make_collection_event(item)))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].document_id, repository.all()[0].id)
        self.assertFalse(hasattr(received[0], "item"))
        self.assertFalse(hasattr(received[0], "document"))


class ScoringHandlerTests(unittest.TestCase):
    def test_scores_enriched_document_and_preserves_correlation(self) -> None:
        event_bus = InMemoryEventBus()
        repository = InMemoryKnowledgeRepository()
        original = KnowledgeNormalizer().normalize(make_item())
        enriched = replace(original, summary="OpenAI GPT summary", version=2)
        repository.add(original)
        repository.update(enriched, expected_version=1)
        engine = ScoringEngine()
        engine.register(SourceTrustRule())
        engine.register(KeywordRule())
        handler = ScoringHandler(engine, event_bus, repository)
        completed: list[ScoringCompleted] = []

        async def capture(event: ScoringCompleted) -> None:
            completed.append(event)

        event_bus.subscribe(ScoringCompleted, capture)
        correlation_id = uuid4()
        event = KnowledgeEnriched(
            event_id=uuid4(), event_version=1, occurred_at=datetime.now(UTC),
            document_id=enriched.id, previous_version=1, current_version=2,
            correlation_id=correlation_id, warnings=(),
        )

        asyncio.run(handler.handle(event))

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].total_score, 30)
        self.assertEqual(completed[0].correlation_id, correlation_id)

    def test_scoring_is_not_triggered_by_knowledge_stored(self) -> None:
        event_bus = InMemoryEventBus()
        repository = InMemoryKnowledgeRepository()
        document = KnowledgeNormalizer().normalize(make_item())
        repository.add(document)
        engine = ScoringEngine()
        engine.register(SourceTrustRule())
        handler = ScoringHandler(engine, event_bus, repository)
        completed: list[ScoringCompleted] = []

        async def capture(event: ScoringCompleted) -> None:
            completed.append(event)

        event_bus.subscribe(KnowledgeEnriched, handler.handle)
        event_bus.subscribe(ScoringCompleted, capture)
        stored = KnowledgeStored(
            event_id=uuid4(), event_version=1, occurred_at=datetime.now(UTC),
            document_id=document.id, source=document.source,
            source_external_id=document.source_external_id, correlation_id=uuid4(),
        )

        asyncio.run(event_bus.publish(stored))

        self.assertEqual(completed, [])

    def test_scoring_failure_does_not_stop_other_enrichment_handlers(self) -> None:
        event_bus = InMemoryEventBus()
        repository = InMemoryKnowledgeRepository()
        original = KnowledgeNormalizer().normalize(make_item())
        enriched = replace(original, version=2)
        repository.add(original)
        repository.update(enriched, 1)
        engine = ScoringEngine()
        engine.register(FailingRule())
        scoring_handler = ScoringHandler(engine, event_bus, repository)
        observed: list[KnowledgeEnriched] = []

        async def observer(event: KnowledgeEnriched) -> None:
            observed.append(event)

        event_bus.subscribe(KnowledgeEnriched, scoring_handler.handle)
        event_bus.subscribe(KnowledgeEnriched, observer)
        event = KnowledgeEnriched(
            event_id=uuid4(), event_version=1, occurred_at=datetime.now(UTC),
            document_id=enriched.id, previous_version=1, current_version=2,
            correlation_id=uuid4(), warnings=(),
        )

        with self.assertLogs("core.event_bus.in_memory", level="ERROR"):
            asyncio.run(event_bus.publish(event))

        self.assertEqual(observed, [event])


class CorrelationPipelineTests(unittest.TestCase):
    def test_preserves_correlation_id_through_full_pipeline(self) -> None:
        event_bus = InMemoryEventBus()
        repository = InMemoryKnowledgeRepository()
        knowledge_handler = KnowledgeHandler(repository, event_bus)
        enrichment_handler = EnrichmentHandler(
            EnrichmentEngine(summary_providers=(DeterministicSummaryProvider(),)),
            repository,
            event_bus,
        )
        engine = ScoringEngine()
        engine.register(SourceTrustRule())
        scoring_handler = ScoringHandler(engine, event_bus, repository)
        completed: list[ScoringCompleted] = []

        async def capture(event: ScoringCompleted) -> None:
            completed.append(event)

        event_bus.subscribe(CollectionCompleted, knowledge_handler.handle)
        event_bus.subscribe(KnowledgeStored, enrichment_handler.handle)
        event_bus.subscribe(KnowledgeEnriched, scoring_handler.handle)
        event_bus.subscribe(ScoringCompleted, capture)
        correlation_id = uuid4()

        asyncio.run(event_bus.publish(make_collection_event(make_item(), correlation_id)))

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].correlation_id, correlation_id)
        self.assertEqual(repository.all()[0].version, 2)


if __name__ == "__main__":
    unittest.main()
