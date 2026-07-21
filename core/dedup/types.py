from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class NormalizedItem:
    item: Any
    normalized_url: str
    normalized_title: str

@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    key: str
    items: tuple[Any, ...]
    kept_item: Any

@dataclass(frozen=True, slots=True)
class DedupStats:
    total_items: int
    unique_items: int
    duplicate_items: int
    duplicate_groups: int
