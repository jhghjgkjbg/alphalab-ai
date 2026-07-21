from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from core.collector.events import CollectionCompleted
from core.collector.registry import CollectorRegistry
from core.collector.types import CollectorResult, CollectorStatus
from core.source_manager.registry import SourceRegistry
from core.source_manager.types import SourceRunResult, SourceRunStatus


class EventPublisher(Protocol):
    async def publish(self, event: Any) -> None: ...


class SourceManager:
    def __init__(
        self,
        collector_registry: CollectorRegistry,
        source_registry: SourceRegistry,
        event_publisher: EventPublisher,
    ) -> None:
        self._collector_registry = collector_registry
        self._source_registry = source_registry
        self._event_publisher = event_publisher

    async def run_source(
        self,
        source_id: str,
        correlation_id: UUID | None = None,
    ) -> SourceRunResult:
        started_at = datetime.now(UTC)
        correlation_id = correlation_id or uuid4()
        source = self._source_registry.get(source_id)
        if source is None:
            return self._result(
                source_id, "", SourceRunStatus.NOT_FOUND, started_at,
                correlation_id, error_message="unknown source",
            )
        if not source.enabled:
            return self._result(
                source_id, source.collector_name, SourceRunStatus.SKIPPED,
                started_at, correlation_id, error_message="source is disabled",
            )

        try:
            collector = self._collector_registry.create(
                source.collector_name,
                metadata=source.metadata,
                max_items=source.max_items,
            )
            collector_result = await collector.collect()
            print(
                f"collector: name={source.collector_name} enabled=yes called=yes "
                f"parsed={len(collector_result.items)} produced={len(collector_result.items)} "
                f"failed={len(collector_result.errors)} "
                f"error={(collector_result.errors[0][:200] if collector_result.errors else '')}"
            )
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            print(
                f"collector: name={source.collector_name} enabled=yes called=yes "
                f"parsed=0 produced=0 failed=1 exception={error_message[:200]}"
            )
            collector_result = CollectorResult(
                collector_name=source.collector_name,
                status=CollectorStatus.FAILED,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                errors=(error_message,),
            )

        await self._event_publisher.publish(
            CollectionCompleted(
                event_id=uuid4(),
                event_version=1,
                occurred_at=collector_result.finished_at,
                collector_name=collector_result.collector_name,
                status=collector_result.status,
                items=collector_result.items,
                errors=collector_result.errors,
                correlation_id=correlation_id,
            )
        )

        status = SourceRunStatus(collector_result.status.value)
        return SourceRunResult(
            source_id=source_id,
            collector_name=collector_result.collector_name,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            collected_count=len(collector_result.items),
            error_count=len(collector_result.errors),
            correlation_id=correlation_id,
            error_message="; ".join(collector_result.errors) or None,
            items=collector_result.items,
        )

    async def run_enabled(self) -> tuple[SourceRunResult, ...]:
        results = []
        for source in self._source_registry.enabled():
            results.append(await self.run_source(source.source_id))
        return tuple(results)

    @staticmethod
    def _result(
        source_id: str,
        collector_name: str,
        status: SourceRunStatus,
        started_at: datetime,
        correlation_id: UUID,
        *,
        error_message: str,
    ) -> SourceRunResult:
        return SourceRunResult(
            source_id=source_id,
            collector_name=collector_name,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            collected_count=0,
            error_count=1,
            correlation_id=correlation_id,
            error_message=error_message,
        )
