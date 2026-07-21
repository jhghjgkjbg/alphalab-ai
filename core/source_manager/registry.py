from dataclasses import replace

from core.source_manager.types import SourceDefinition


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, SourceDefinition] = {}

    def register(self, source: SourceDefinition) -> None:
        if not source.source_id:
            raise ValueError("source_id must not be empty")
        if source.source_id in self._sources:
            raise ValueError(f"source is already registered: {source.source_id}")
        if source.interval_seconds <= 0 or source.max_items <= 0:
            raise ValueError("source interval and max_items must be positive")
        self._sources[source.source_id] = source

    def get(self, source_id: str) -> SourceDefinition | None:
        return self._sources.get(source_id)

    def all(self) -> tuple[SourceDefinition, ...]:
        return tuple(self._sources.values())

    def enabled(self) -> tuple[SourceDefinition, ...]:
        return tuple(source for source in self._sources.values() if source.enabled)

    def enable(self, source_id: str) -> SourceDefinition:
        return self._set_enabled(source_id, True)

    def disable(self, source_id: str) -> SourceDefinition:
        return self._set_enabled(source_id, False)

    def _set_enabled(self, source_id: str, enabled: bool) -> SourceDefinition:
        current = self._sources[source_id]
        updated = replace(current, enabled=enabled)
        self._sources[source_id] = updated
        return updated
