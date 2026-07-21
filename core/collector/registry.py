import inspect
from collections.abc import Callable, Mapping
from types import MappingProxyType

from core.collector.base import BaseCollector


class CollectorRegistry:
    """Registry of available collector types without lifecycle ownership."""

    def __init__(self) -> None:
        self._collectors: dict[str, type[BaseCollector]] = {}
        self._factories: dict[str, Callable[[], BaseCollector]] = {}

    def register(self, collector_type: type[BaseCollector]) -> None:
        if not issubclass(collector_type, BaseCollector):
            raise TypeError("collector_type must inherit from BaseCollector")

        name = collector_type.name()
        if not name:
            raise ValueError("collector name must not be empty")
        if name in self._collectors:
            raise ValueError(f"collector is already registered: {name}")

        self._collectors[name] = collector_type

    def register_factory(
        self,
        collector_name: str,
        factory: Callable[[], BaseCollector],
    ) -> None:
        if not collector_name:
            raise ValueError("collector_name must not be empty")
        if collector_name in self._collectors or collector_name in self._factories:
            raise ValueError(f"collector is already registered: {collector_name}")
        self._factories[collector_name] = factory

    def get(self, name: str) -> type[BaseCollector]:
        return self._collectors[name]

    def registered(self) -> Mapping[str, type[BaseCollector]]:
        return MappingProxyType(self._collectors.copy())

    def create(self, name: str, **configuration: object) -> BaseCollector:
        if name in self._factories:
            factory = self._factories[name]
            if inspect.signature(factory).parameters:
                return factory(**configuration)
            return factory()
        return self._collectors[name]()
