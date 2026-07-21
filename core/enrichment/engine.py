from core.enrichment.base import KeywordProvider, SummaryProvider, TagProvider
from core.enrichment.types import EnrichmentResult, EnrichmentSource, ProviderResult


class EnrichmentEngine:
    def __init__(
        self,
        summary_providers: tuple[SummaryProvider, ...] = (),
        keyword_providers: tuple[KeywordProvider, ...] = (),
        tag_providers: tuple[TagProvider, ...] = (),
    ) -> None:
        self._summary_providers = tuple(summary_providers)
        self._keyword_providers = tuple(keyword_providers)
        self._tag_providers = tuple(tag_providers)

    async def enrich(self, document: EnrichmentSource) -> EnrichmentResult:
        summary = document.summary
        keywords: list[str] = []
        tags: list[str] = []
        provider_results: list[ProviderResult] = []
        warnings: list[str] = []

        for provider in self._summary_providers:
            try:
                value = await provider.provide(document)
                if not summary and value:
                    summary = value
                provider_results.append(ProviderResult(provider.name(), "summary", (value,), True))
            except Exception as exc:
                warnings.append(self._warning(provider.name(), exc))
                provider_results.append(ProviderResult(provider.name(), "summary", (), False))

        for provider in self._keyword_providers:
            try:
                values = await provider.provide(document, summary)
                self._extend_unique(keywords, values)
                provider_results.append(ProviderResult(provider.name(), "keywords", tuple(values), True))
            except Exception as exc:
                warnings.append(self._warning(provider.name(), exc))
                provider_results.append(ProviderResult(provider.name(), "keywords", (), False))

        for provider in self._tag_providers:
            try:
                values = await provider.provide(document, summary, tuple(keywords))
                self._extend_unique(tags, values)
                provider_results.append(ProviderResult(provider.name(), "tags", tuple(values), True))
            except Exception as exc:
                warnings.append(self._warning(provider.name(), exc))
                provider_results.append(ProviderResult(provider.name(), "tags", (), False))

        return EnrichmentResult(
            summary=summary,
            keywords=tuple(keywords),
            tags=tuple(tags),
            provider_results=tuple(provider_results),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
        for value in values:
            if value not in target:
                target.append(value)

    @staticmethod
    def _warning(provider_name: str, error: Exception) -> str:
        return f"{provider_name}: {type(error).__name__}: {error}"
