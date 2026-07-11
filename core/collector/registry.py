from collections.abc import Mapping
from types import MappingProxyType

from core.collector.base import BaseCollector


class CollectorRegistry:
    """Registry of available collector types without lifecycle ownership."""

    def __init__(self) -> None:
        self._collectors: dict[str, type[BaseCollector]] = {}

    def register(self, collector_type: type[BaseCollector]) -> None:
        if not issubclass(collector_type, BaseCollector):
            raise TypeError("collector_type must inherit from BaseCollector")

        name = collector_type.name()
        if not name:
            raise ValueError("collector name must not be empty")
        if name in self._collectors:
            raise ValueError(f"collector is already registered: {name}")

        self._collectors[name] = collector_type

    def get(self, name: str) -> type[BaseCollector]:
        return self._collectors[name]

    def registered(self) -> Mapping[str, type[BaseCollector]]:
        return MappingProxyType(self._collectors.copy())
