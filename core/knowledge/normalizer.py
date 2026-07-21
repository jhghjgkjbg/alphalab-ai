import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from core.collector.types import SourceItem
from core.knowledge.models import KnowledgeDocument, build_document_id


Clock = Callable[[], datetime]
_SENSITIVE_KEY_PARTS = ("api_key", "authorization", "password", "secret", "token")


class KnowledgeNormalizer:
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def normalize(self, item: SourceItem) -> KnowledgeDocument:
        title = self._string_value(item.payload.get("title"))
        url = self._optional_string(item.payload.get("url"))
        content = self._string_value(
            item.payload.get("content", item.payload.get("text", ""))
        )
        published_at = self._parse_datetime(
            item.metadata.get("published_at", item.payload.get("published_at"))
        )
        now = self._clock()

        return KnowledgeDocument(
            id=build_document_id(item.source, item.external_id),
            title=title,
            url=url,
            source=item.source,
            source_external_id=item.external_id,
            published_at=published_at,
            collected_at=item.collected_at,
            summary="",
            language=self._detect_language(f"{title} {content}"),
            content=content,
            keywords=(),
            tags=(),
            metadata=self._safe_metadata(item.metadata),
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _string_value(value: Any) -> str:
        return value if isinstance(value, str) else ""

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _detect_language(text: str) -> str:
        if re.search(r"[А-Яа-яЁё]", text):
            return "ru"
        if re.search(r"[A-Za-z]", text):
            return "en"
        return "unknown"

    @classmethod
    def _safe_metadata(cls, metadata: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in metadata.items()
            if isinstance(key, str)
            and not any(part in key.lower() for part in _SENSITIVE_KEY_PARTS)
            and cls._is_safe_value(value)
        }

    @classmethod
    def _is_safe_value(cls, value: Any) -> bool:
        if value is None or isinstance(value, (str, int, float, bool, datetime)):
            return True
        if isinstance(value, Mapping):
            return all(
                isinstance(key, str) and cls._is_safe_value(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            return all(cls._is_safe_value(item) for item in value)
        return False

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return datetime.fromtimestamp(value, tz=UTC)
            except (OSError, OverflowError, ValueError):
                return None
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        return None
