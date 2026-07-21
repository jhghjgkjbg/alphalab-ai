from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5


KNOWLEDGE_ID_NAMESPACE = uuid5(NAMESPACE_URL, "https://alphalab.ai/knowledge")


def build_document_id(source: str, source_external_id: str) -> UUID:
    return uuid5(KNOWLEDGE_ID_NAMESPACE, f"{source}\x00{source_external_id}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    id: UUID
    title: str
    url: str | None
    source: str
    source_external_id: str
    published_at: datetime | None
    collected_at: datetime
    summary: str
    language: str
    content: str
    keywords: tuple[str, ...]
    tags: tuple[str, ...]
    metadata: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "keywords", tuple(self.keywords))
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))
