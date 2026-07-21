import ast
import asyncio
import pathlib
import unittest
from datetime import UTC, datetime
from uuid import UUID

from core.collector.events import CollectionCompleted
from core.collector.types import CollectorStatus, SourceItem
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.events import KnowledgeStored
from core.knowledge.handler import KnowledgeHandler
from core.knowledge.models import KnowledgeDocument, build_document_id
from core.knowledge.normalizer import KnowledgeNormalizer
from core.knowledge.repository import InMemoryKnowledgeRepository


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def source_item(
    external_id: str = "42",
    *,
    title: object = "AlphaLab AI",
    url: object = "https://example.com/alphalab",
    content: object = "Canonical knowledge",
    published_at: object = 1_700_000_000,
    metadata: dict[str, object] | None = None,
) -> SourceItem:
    item_metadata = {"author": "alice", "published_at": published_at}
    if metadata:
        item_metadata.update(metadata)
    return SourceItem(
        source="hacker_news",
        external_id=external_id,
        collected_at=NOW,
        payload={"title": title, "url": url, "content": content},
        metadata=item_metadata,
    )


class KnowledgeDocumentTests(unittest.TestCase):
    def test_document_id_is_stable_for_source_key(self) -> None:
        first = build_document_id("hacker_news", "42")
        second = build_document_id("hacker_news", "42")

        self.assertIsInstance(first, UUID)
        self.assertEqual(first, second)
        self.assertNotEqual(first, build_document_id("github", "42"))

    def test_normalizes_complete_source_item(self) -> None:
        document = KnowledgeNormalizer(clock=lambda: NOW).normalize(source_item())

        self.assertEqual(document.id, build_document_id("hacker_news", "42"))
        self.assertEqual(document.title, "AlphaLab AI")
        self.assertEqual(document.url, "https://example.com/alphalab")
        self.assertEqual(document.content, "Canonical knowledge")
        self.assertEqual(document.published_at, datetime.fromtimestamp(1_700_000_000, tz=UTC))
        self.assertEqual(document.summary, "")
        self.assertEqual(document.keywords, ())
        self.assertEqual(document.tags, ())
        self.assertEqual(document.created_at, NOW)
        self.assertEqual(document.updated_at, NOW)
        self.assertEqual(document.version, 1)

    def test_normalizes_missing_optional_values(self) -> None:
        item = source_item(title=None, url=None, content=None, published_at=None)

        document = KnowledgeNormalizer(clock=lambda: NOW).normalize(item)

        self.assertEqual(document.title, "")
        self.assertIsNone(document.url)
        self.assertEqual(document.content, "")
        self.assertIsNone(document.published_at)
        self.assertEqual(document.language, "unknown")

    def test_detects_ru_en_and_unknown_languages(self) -> None:
        normalizer = KnowledgeNormalizer(clock=lambda: NOW)

        ru = normalizer.normalize(source_item("1", title="Новая модель", content=""))
        en = normalizer.normalize(source_item("2", title="New model", content=""))
        unknown = normalizer.normalize(source_item("3", title="123", content=""))

        self.assertEqual((ru.language, en.language, unknown.language), ("ru", "en", "unknown"))

    def test_metadata_is_read_only_and_sensitive_values_are_removed(self) -> None:
        document = KnowledgeNormalizer(clock=lambda: NOW).normalize(
            source_item(metadata={"score": 10, "api_token": "hidden"})
        )

        self.assertEqual(document.metadata["score"], 10)
        self.assertNotIn("api_token", document.metadata)
        with self.assertRaises(TypeError):
            document.metadata["score"] = 20


class KnowledgeRepositoryTests(unittest.TestCase):
    def test_stores_documents_deduplicates_and_supports_both_lookups(self) -> None:
        repository = InMemoryKnowledgeRepository()
        normalizer = KnowledgeNormalizer(clock=lambda: NOW)
        first = normalizer.normalize(source_item("42"))
        duplicate = normalizer.normalize(source_item("42", title="Changed"))

        self.assertTrue(repository.add(first))
        self.assertFalse(repository.add(duplicate))
        self.assertIs(repository.get(first.id), first)
        self.assertIs(repository.get_by_source_key("hacker_news", "42"), first)
        self.assertEqual(repository.all(), (first,))
        self.assertEqual(repository.count(), 1)


class FailingNormalizer:
    def __init__(self) -> None:
        self._normalizer = KnowledgeNormalizer(clock=lambda: NOW)

    def normalize(self, item: SourceItem) -> KnowledgeDocument:
        if item.external_id == "bad":
            raise ValueError("invalid item")
        return self._normalizer.normalize(item)


class KnowledgeHandlerTests(unittest.TestCase):
    def test_normalization_failure_does_not_stop_other_items(self) -> None:
        event_bus = InMemoryEventBus()
        repository = InMemoryKnowledgeRepository()
        handler = KnowledgeHandler(repository, event_bus, FailingNormalizer())
        stored_events: list[KnowledgeStored] = []

        async def capture(event: KnowledgeStored) -> None:
            stored_events.append(event)

        event_bus.subscribe(KnowledgeStored, capture)
        collection_event = CollectionCompleted(
            event_id=build_document_id("event", "1"),
            event_version=1,
            occurred_at=NOW,
            collector_name="hacker_news",
            status=CollectorStatus.PARTIAL,
            items=(source_item("bad"), source_item("good")),
            errors=(),
            correlation_id=build_document_id("correlation", "1"),
        )

        with self.assertLogs("core.knowledge.handler", level="ERROR"):
            asyncio.run(handler.handle(collection_event))

        self.assertEqual(repository.count(), 1)
        self.assertEqual(len(stored_events), 1)
        self.assertEqual(handler.stats(collection_event.event_id).received, 2)
        self.assertEqual(handler.stats(collection_event.event_id).stored, 1)
        self.assertEqual(handler.stats(collection_event.event_id).failed, 1)


class KnowledgeArchitectureTests(unittest.TestCase):
    def test_model_has_no_forbidden_imports(self) -> None:
        path = pathlib.Path("core/knowledge/models.py")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = {"agents", "backend", "core.collector", "core.event_bus", "core.scoring"}
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        violations = [
            module
            for module in imports
            if any(module == item or module.startswith(f"{item}.") for item in forbidden)
        ]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
