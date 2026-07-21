from datetime import datetime
from collections.abc import Iterable

from .normalize import normalize_title, normalize_url
from .types import DedupStats, DuplicateGroup, NormalizedItem

_PRIORITY = {"github": 0, "product_hunt": 1, "hacker_news": 2, "devto": 3, "lobsters": 4, "arxiv": 5, "reddit": 6, "rss": 7}

class DedupEngine:
    def __init__(self, source_priority: dict[str, int] | None = None) -> None:
        self._priority = dict(source_priority or _PRIORITY)

    def deduplicate(self, items: Iterable[object]) -> tuple[tuple[object, ...], tuple[DuplicateGroup, ...], DedupStats]:
        materialized = list(items)
        normalized = [NormalizedItem(i, normalize_url(self._field(i, "url", "")), normalize_title(self._field(i, "title", ""))) for i in materialized]
        groups: dict[str, list[NormalizedItem]] = {}
        seen: dict[str, int] = {}
        for entry in normalized:
            keys = [f"url:{entry.normalized_url}"] if entry.normalized_url else []
            if entry.normalized_title: keys.append(f"title:{entry.normalized_title}")
            match = next((seen[k] for k in keys if k in seen), None)
            if match is None:
                index = len(groups); match = index
                for key in keys: seen[key] = match
                groups[str(match)] = [entry]
            else:
                groups[str(match)].append(entry)
        unique: list[object] = []; duplicate_groups: list[DuplicateGroup] = []
        for entries in groups.values():
            kept = min(entries, key=lambda e: (self._priority.get(str(self._field(e.item, "source", "")).lower(), 999), -self._timestamp(e.item), normalized.index(e)))
            unique.append(kept.item)
            if len(entries) > 1:
                duplicate_groups.append(DuplicateGroup(entries[0].normalized_url or entries[0].normalized_title, tuple(e.item for e in entries), kept.item))
        stats = DedupStats(len(materialized), len(unique), len(materialized)-len(unique), len(duplicate_groups))
        return tuple(unique), tuple(duplicate_groups), stats

    @staticmethod
    def _field(item: object, name: str, default: object) -> object:
        if hasattr(item, name): return getattr(item, name)
        payload = getattr(item, "payload", {})
        return payload.get(name, default) if isinstance(payload, dict) else default

    @classmethod
    def _timestamp(cls, item: object) -> float:
        value = cls._field(item, "published_at", None)
        if isinstance(value, datetime): return value.timestamp()
        try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError): return 0.0
