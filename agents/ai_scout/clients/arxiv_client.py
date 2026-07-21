from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, str], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ArxivItem:
    id: str
    title: str
    summary: str
    url: str
    published_at: str | None
    authors: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArxivResult:
    success: bool
    items: tuple[ArxivItem, ...]
    error_message: str | None
    status_code: int | None = None


class ArxivClient:
    API_URL = "https://export.arxiv.org/api/query"
    NS = {"a": "http://www.w3.org/2005/Atom", "ar": "http://arxiv.org/schemas/atom"}

    def __init__(self, timeout_seconds: float, request: HttpRequest) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout, self._request = timeout_seconds, request

    async def search(self, search_query: str, max_items: int = 10) -> ArxivResult:
        if not search_query:
            return ArxivResult(False, (), "search_query must not be empty")
        if max_items <= 0:
            return ArxivResult(False, (), "max_items must be positive")
        try:
            response = await self._request(self.API_URL, {"Accept": "application/atom+xml"}, {"search_query": search_query, "max_results": str(max_items)}, self._timeout)
            status, payload = self._unpack(response)
            if status is not None and not 200 <= status < 300:
                return ArxivResult(False, (), "arXiv HTTP request failed", status)
            if isinstance(payload, str): payload = payload.encode()
            root = ElementTree.fromstring(payload)
            entries = root.findall("a:entry", self.NS)
            return ArxivResult(True, tuple(self._parse(e) for e in entries[:max_items]), None, status)
        except TimeoutError:
            return ArxivResult(False, (), "arXiv request timed out")
        except (ElementTree.ParseError, TypeError, ValueError):
            return ArxivResult(False, (), "invalid arXiv XML")
        except Exception as exc:
            return ArxivResult(False, (), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int): return response[0], response[1]
        return None, response

    @classmethod
    def _parse(cls, entry: ElementTree.Element) -> ArxivItem:
        text = lambda tag: (entry.findtext(f"a:{tag}", default="", namespaces=cls.NS) or "").strip()
        authors = tuple((a.findtext("a:name", default="", namespaces=cls.NS) or "").strip() for a in entry.findall("a:author", cls.NS))
        categories = tuple(c.attrib["term"] for c in entry.findall("a:category", cls.NS) if "term" in c.attrib)
        link = next((l.attrib.get("href", "") for l in entry.findall("a:link", cls.NS) if l.attrib.get("rel") == "alternate"), "")
        return ArxivItem(text("id"), text("title"), text("summary"), link, text("published") or None, authors, categories)
