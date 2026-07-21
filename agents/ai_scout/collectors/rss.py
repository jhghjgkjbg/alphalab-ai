import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree

from core.collector.base import BaseCollector
from core.collector.types import CollectorResult, CollectorStatus, SourceItem


FeedLoader = Callable[[str, float, int], bytes]


class RSSCollector(BaseCollector):
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024

    def __init__(
        self,
        feed_url: str,
        max_items: int = 10,
        *,
        timeout: float = 10.0,
        fetch: FeedLoader | None = None,
    ) -> None:
        parsed = urlparse(feed_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("feed_url must use http or https")
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        self._feed_url = feed_url
        self._max_items = max_items
        self._timeout = timeout
        self._fetch = fetch or self._default_fetch

    @classmethod
    def name(cls) -> str:
        return "rss"

    async def collect(self) -> CollectorResult:
        started_at = datetime.now(UTC)
        try:
            raw = await asyncio.to_thread(
                self._fetch,
                self._feed_url,
                self._timeout,
                self.MAX_RESPONSE_BYTES,
            )
            if len(raw) > self.MAX_RESPONSE_BYTES:
                raise ValueError("feed response exceeds maximum size")
            root = ElementTree.fromstring(raw)
        except (HTTPError, URLError, TimeoutError, ValueError, ElementTree.ParseError, OSError) as exc:
            return self._result(
                CollectorStatus.FAILED,
                started_at,
                (),
                (f"feed request failed: {type(exc).__name__}: {exc}",),
            )

        entries = self._entries(root)[: self._max_items]
        items: list[SourceItem] = []
        errors: list[str] = []
        for index, entry in enumerate(entries):
            try:
                items.append(self._to_source_item(entry, index))
            except (TypeError, ValueError) as exc:
                errors.append(f"entry {index} skipped: {exc}")

        status = (
            CollectorStatus.PARTIAL
            if errors and items
            else CollectorStatus.FAILED
            if errors and not items
            else CollectorStatus.SUCCESS
        )
        return self._result(status, started_at, tuple(items), tuple(errors))

    def _to_source_item(self, entry: ElementTree.Element, index: int) -> SourceItem:
        title = self._text(entry, "title")
        if not title:
            raise ValueError("title is missing")
        link = self._link(entry)
        external_id = self._text(entry, "guid") or self._text(entry, "id")
        if not external_id:
            identity = link or f"{self._feed_url}#entry-{index}-{title}"
            external_id = str(uuid5(NAMESPACE_URL, identity))
        content = (
            self._text(entry, "encoded")
            or self._text(entry, "content")
            or self._text(entry, "description")
            or self._text(entry, "summary")
        )
        published_at = self._parse_datetime(
            self._text(entry, "pubDate")
            or self._text(entry, "published")
            or self._text(entry, "updated")
        )
        author = self._text(entry, "creator") or self._author(entry)
        return SourceItem(
            source="rss",
            external_id=external_id,
            collected_at=datetime.now(UTC),
            payload={"title": title, "url": link, "content": content},
            metadata={"author": author, "published_at": published_at},
        )

    @staticmethod
    def _entries(root: ElementTree.Element) -> list[ElementTree.Element]:
        root_name = RSSCollector._local_name(root.tag)
        if root_name == "rss":
            return [child for child in root.iter() if RSSCollector._local_name(child.tag) == "item"]
        if root_name == "feed":
            return [child for child in root if RSSCollector._local_name(child.tag) == "entry"]
        raise ValueError("unsupported feed root")

    @classmethod
    def _text(cls, element: ElementTree.Element, name: str) -> str:
        for child in element.iter():
            if cls._local_name(child.tag).lower() == name.lower() and child is not element:
                return (child.text or "").strip()
        return ""

    @classmethod
    def _link(cls, element: ElementTree.Element) -> str:
        for child in element.iter():
            if cls._local_name(child.tag).lower() != "link":
                continue
            href = child.attrib.get("href")
            if href and child.attrib.get("rel", "alternate") == "alternate":
                return href.strip()
            if child.text and child.text.strip():
                return child.text.strip()
        return ""

    @classmethod
    def _author(cls, element: ElementTree.Element) -> str:
        for author in element.iter():
            if cls._local_name(author.tag).lower() == "author":
                return cls._text(author, "name") or (author.text or "").strip()
        return ""

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @staticmethod
    def _default_fetch(url: str, timeout: float, max_bytes: int) -> bytes:
        request = Request(url, headers={"User-Agent": "AlphaLab-AI-RSS/0.1"})
        with urlopen(request, timeout=timeout) as response:
            content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("feed response exceeds maximum size")
        return content

    @staticmethod
    def _result(
        status: CollectorStatus,
        started_at: datetime,
        items: tuple[SourceItem, ...],
        errors: tuple[str, ...],
    ) -> CollectorResult:
        return CollectorResult(
            collector_name=RSSCollector.name(),
            status=status,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            items=items,
            errors=errors,
        )
