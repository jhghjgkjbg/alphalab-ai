from typing import Protocol

from core.enrichment.types import EnrichmentSource


class SummaryProvider(Protocol):
    @classmethod
    def name(cls) -> str: ...

    async def provide(self, document: EnrichmentSource) -> str: ...


class KeywordProvider(Protocol):
    @classmethod
    def name(cls) -> str: ...

    async def provide(self, document: EnrichmentSource, summary: str) -> tuple[str, ...]: ...


class TagProvider(Protocol):
    @classmethod
    def name(cls) -> str: ...

    async def provide(
        self,
        document: EnrichmentSource,
        summary: str,
        keywords: tuple[str, ...],
    ) -> tuple[str, ...]: ...
