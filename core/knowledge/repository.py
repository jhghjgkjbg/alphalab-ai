from typing import Protocol

from core.collector.types import SourceItem


class KnowledgeRepository(Protocol):
    def save(self, item: SourceItem) -> bool:
        """Save a new item and return whether it was inserted."""

    def all(self) -> tuple[SourceItem, ...]:
        """Return all stored items in insertion order."""

    def count(self) -> int:
        """Return the number of unique stored items."""


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], SourceItem] = {}

    def save(self, item: SourceItem) -> bool:
        key = (item.source, item.external_id)
        if key in self._items:
            return False

        self._items[key] = item
        return True

    def all(self) -> tuple[SourceItem, ...]:
        return tuple(self._items.values())

    def count(self) -> int:
        return len(self._items)
