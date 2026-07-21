import asyncio
import unittest
from datetime import UTC, datetime

from core.collector.types import SourceItem
from core.enrichment.engine import EnrichmentEngine
from core.enrichment.providers import (
    DeterministicKeywordProvider,
    DeterministicSummaryProvider,
    DictionaryTagProvider,
)
from core.knowledge.normalizer import KnowledgeNormalizer


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def document(title: str, content: str = ""):
    item = SourceItem(
        source="hacker_news",
        external_id="1",
        collected_at=NOW,
        payload={"title": title, "content": content},
    )
    return KnowledgeNormalizer(clock=lambda: NOW).normalize(item)


class FailingSummaryProvider:
    @classmethod
    def name(cls) -> str:
        return "failing_summary"

    async def provide(self, item) -> str:
        raise RuntimeError("provider failed")


class EnrichmentProviderTests(unittest.TestCase):
    def test_summary_is_deterministic(self) -> None:
        provider = DeterministicSummaryProvider(max_length=100)
        item = document("AlphaLab", "Builds canonical knowledge")

        first = asyncio.run(provider.provide(item))
        second = asyncio.run(provider.provide(item))

        self.assertEqual(first, second)
        self.assertEqual(first, "AlphaLab Builds canonical knowledge")

    def test_summary_respects_limit_without_cutting_word(self) -> None:
        result = asyncio.run(
            DeterministicSummaryProvider(max_length=18).provide(
                document("AlphaLab platform", "builds knowledge")
            )
        )

        self.assertLessEqual(len(result), 18)
        self.assertEqual(result, "AlphaLab platform")

    def test_keywords_are_unique_without_stop_words(self) -> None:
        item = document("The AI platform and platform", "Данные и AI для команды")

        result = asyncio.run(DeterministicKeywordProvider().provide(item, ""))

        self.assertEqual(result.count("platform"), 1)
        self.assertEqual(result.count("ai"), 1)
        self.assertNotIn("the", result)
        self.assertNotIn("and", result)
        self.assertNotIn("для", result)

    def test_tags_use_deterministic_dictionary(self) -> None:
        item = document("OpenAI security startup", "Python data platform")

        result = asyncio.run(DictionaryTagProvider().provide(item, "", ()))

        self.assertEqual(result, ("ai", "coding", "security", "startup", "data"))


class EnrichmentEngineTests(unittest.TestCase):
    def test_provider_failure_does_not_stop_other_providers(self) -> None:
        engine = EnrichmentEngine(
            summary_providers=(FailingSummaryProvider(), DeterministicSummaryProvider()),
            keyword_providers=(DeterministicKeywordProvider(),),
            tag_providers=(DictionaryTagProvider(),),
        )
        item = document("OpenAI coding", "GPT platform")

        result = asyncio.run(engine.enrich(item))

        self.assertTrue(result.summary)
        self.assertTrue(result.keywords)
        self.assertIn("ai", result.tags)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("failing_summary", result.warnings[0])
        self.assertFalse(result.provider_results[0].success)


if __name__ == "__main__":
    unittest.main()
