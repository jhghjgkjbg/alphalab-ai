from typing import Protocol
from uuid import UUID

from core.knowledge.models import KnowledgeDocument


class KnowledgeRepository(Protocol):
    def add(self, document: KnowledgeDocument) -> bool:
        """Add a new document and return whether it was inserted."""

    def get(self, document_id: UUID) -> KnowledgeDocument | None:
        """Return a document by its canonical identifier."""

    def get_by_source_key(
        self,
        source: str,
        source_external_id: str,
    ) -> KnowledgeDocument | None:
        """Return a document by source identity."""

    def all(self) -> tuple[KnowledgeDocument, ...]:
        """Return immutable documents in insertion order."""

    def count(self) -> int:
        """Return the number of unique documents."""

    def update(self, document: KnowledgeDocument, expected_version: int) -> bool:
        """Replace a document when its current version matches the expectation."""


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._documents_by_id: dict[UUID, KnowledgeDocument] = {}
        self._ids_by_source_key: dict[tuple[str, str], UUID] = {}

    def add(self, document: KnowledgeDocument) -> bool:
        source_key = (document.source, document.source_external_id)
        if source_key in self._ids_by_source_key or document.id in self._documents_by_id:
            return False

        self._documents_by_id[document.id] = document
        self._ids_by_source_key[source_key] = document.id
        return True

    def get(self, document_id: UUID) -> KnowledgeDocument | None:
        return self._documents_by_id.get(document_id)

    def get_by_source_key(
        self,
        source: str,
        source_external_id: str,
    ) -> KnowledgeDocument | None:
        document_id = self._ids_by_source_key.get((source, source_external_id))
        return self._documents_by_id.get(document_id) if document_id else None

    def all(self) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._documents_by_id.values())

    def count(self) -> int:
        return len(self._documents_by_id)

    def update(self, document: KnowledgeDocument, expected_version: int) -> bool:
        current = self._documents_by_id.get(document.id)
        if current is None or current.version != expected_version:
            return False
        if (
            document.source != current.source
            or document.source_external_id != current.source_external_id
            or document.version != expected_version + 1
        ):
            return False

        source_key = (current.source, current.source_external_id)
        if self._ids_by_source_key.get(source_key) != document.id:
            return False

        self._documents_by_id[document.id] = document
        return True
