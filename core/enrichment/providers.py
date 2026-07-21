import re

from core.enrichment.types import EnrichmentSource


class DeterministicSummaryProvider:
    def __init__(self, max_length: int = 240) -> None:
        if max_length <= 0:
            raise ValueError("max_length must be positive")
        self._max_length = max_length

    @classmethod
    def name(cls) -> str:
        return "deterministic_summary"

    async def provide(self, document: EnrichmentSource) -> str:
        text = " ".join(part.strip() for part in (document.title, document.content) if part.strip())
        text = re.sub(r"\s+", " ", text)
        if len(text) <= self._max_length:
            return text

        candidate = text[: self._max_length + 1]
        boundary = candidate.rfind(" ", 0, self._max_length + 1)
        if boundary > 0:
            candidate = candidate[:boundary]
        else:
            candidate = text[: self._max_length]
        return candidate.rstrip()


class DeterministicKeywordProvider:
    _STOP_WORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with",
        "без", "был", "быть", "в", "во", "для", "до", "и", "из", "или", "к",
        "как", "на", "не", "но", "о", "от", "по", "с", "со", "что", "это",
    }
    _SHORT_ALLOWLIST = {"ai"}

    def __init__(self, max_keywords: int = 12, min_length: int = 3) -> None:
        if max_keywords < 0 or min_length < 1:
            raise ValueError("keyword limits must be valid")
        self._max_keywords = max_keywords
        self._min_length = min_length

    @classmethod
    def name(cls) -> str:
        return "deterministic_keywords"

    async def provide(
        self,
        document: EnrichmentSource,
        summary: str,
    ) -> tuple[str, ...]:
        text = " ".join((document.title, summary, document.content)).lower()
        tokens = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
        keywords: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen or token in self._STOP_WORDS:
                continue
            if len(token) < self._min_length and token not in self._SHORT_ALLOWLIST:
                continue
            seen.add(token)
            keywords.append(token)
            if len(keywords) == self._max_keywords:
                break
        return tuple(keywords)


class DictionaryTagProvider:
    _CATEGORY_TERMS = {
        "ai": ("ai", "artificial intelligence", "machine learning", "openai", "anthropic", "gpt", "claude"),
        "llm": ("llm", "large language model", "gpt", "claude"),
        "coding": ("code", "coding", "developer", "github", "programming", "python"),
        "security": ("security", "cybersecurity", "vulnerability", "malware", "privacy"),
        "startup": ("startup", "founder", "funding", "venture", "yc"),
        "crypto": ("bitcoin", "blockchain", "crypto", "ethereum", "web3"),
        "data": ("analytics", "data", "database", "dataset", "sql"),
    }

    def __init__(self, max_tags: int = 5) -> None:
        if max_tags < 0:
            raise ValueError("max_tags must not be negative")
        self._max_tags = max_tags

    @classmethod
    def name(cls) -> str:
        return "dictionary_tags"

    async def provide(
        self,
        document: EnrichmentSource,
        summary: str,
        keywords: tuple[str, ...],
    ) -> tuple[str, ...]:
        text = " ".join((document.title, summary, document.content, *keywords)).lower()
        tags = [
            category
            for category, terms in self._CATEGORY_TERMS.items()
            if any(self._contains_term(text, term) for term in terms)
        ]
        return tuple(tags[: self._max_tags])

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text))
