from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class EnrichmentSource(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def title(self) -> str: ...

    @property
    def summary(self) -> str: ...

    @property
    def content(self) -> str: ...

    @property
    def version(self) -> int: ...

    @property
    def created_at(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider_name: str
    provider_type: str
    values: tuple[str, ...]
    success: bool


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    summary: str
    keywords: tuple[str, ...]
    tags: tuple[str, ...]
    provider_results: tuple[ProviderResult, ...]
    warnings: tuple[str, ...]
