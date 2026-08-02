import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from core.delivery import DeliveryOrchestrator
from core.production_runner import ProductionRunner
from core.publication.builder import PublicationBuilder
from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore
from core.ai_enrichment.types import AIContext


class _Publisher:
    def __init__(self, channel, chat_id, trace): self.channel, self.chat_id, self.events, self.trace = channel, chat_id, trace, []
    async def publish(self, view):
        event = (self.channel, id(self), self.chat_id, view.language, view.title, view.text, len(view.text))
        self.events.append(event); self.trace.append(event)
        return SimpleNamespace(success=True, message_id=len(self.events))


class _AI:
    def __init__(self): self.calls = 0
    def enrich(self, publication):
        self.calls += 1
        ctx = AIContext(short_summary="Enriched English summary", long_summary="Enriched English summary", confidence=.9, headline_suggestions=("Enriched English headline",), ru_title="Обогащённый русский заголовок", ru_body="Обогащённое русское резюме")
        return replace(publication, ai_context=ctx, score=.84)


class _Website:
    def __init__(self, trace): self.trace = trace
    def publish(self, view): self.trace.append(("website", id(self), "website", view.language, view.title, view.summary, len(view.summary)))


class ExactProductionPathTests(unittest.TestCase):
    def test_language_text_validation_rejects_cross_language_and_empty_values(self):
        self.assertTrue(ProductionRunner._valid_text("Valid English summary", "en"))
        self.assertFalse(ProductionRunner._valid_text("Valid English summary", "ru"))
        self.assertTrue(ProductionRunner._valid_text("Русское резюме", "ru"))
        self.assertFalse(ProductionRunner._valid_text("Русское резюме", "en"))
        self.assertTrue(ProductionRunner._valid_text("English текст", "en"))
        self.assertTrue(ProductionRunner._valid_text("Русский text", "ru"))
        self.assertFalse(ProductionRunner._valid_text("Abвг", "en"))
        self.assertFalse(ProductionRunner._valid_text("Abвг", "ru"))
        self.assertFalse(ProductionRunner._valid_text("   ", "en"))
        self.assertFalse(ProductionRunner._valid_text("   ", "ru"))

    def _run(self, legacy=False):
        td = tempfile.mkdtemp()
        try:
            store = SQLitePublishedArticlesStore(SQLiteDatabase(Path(td) / "test.db"))
            item = SimpleNamespace(external_id="unique-article", source="test", payload={"title":"Original", "summary":"Original summary", "url":"https://example.test/unique", "category":"AI", "published_at":"2026-07-21T00:00:00+00:00"})
            if legacy: store.append({"id":"unique-article", "title":"Original", "summary":"", "url":"https://example.test/unique", "score":0})
            trace=[]; ai=_AI(); en=_Publisher("telegram_en", "en-chat", trace); ru=_Publisher("telegram_ru", "ru-chat", trace); website=_Website(trace)
            delivery=DeliveryOrchestrator(website, en, telegram_publisher_ru=ru, confirm_send=True)
            root=SimpleNamespace(builder=PublicationBuilder(), articles_store=store, ai_enrichment_engine=ai, delivery_orchestrator=delivery)
            result=asyncio.run(ProductionRunner(composition_root=root, confirm_send=True).run([item]))
            print("exact production trace:", trace)
            return result, ai, en, ru, store, td
        except Exception:
            import shutil
            shutil.rmtree(td, ignore_errors=True)
            raise

    def test_exact_path_sends_each_channel_once_and_persists_enriched_row(self):
        result, ai, en, ru, store, td = self._run()
        try:
            self.assertEqual(ai.calls, 1); self.assertEqual(result.delivery.overall, "sent")
            self.assertEqual(len(en.trace), 1); self.assertEqual(len(ru.trace), 1)
            rows=store.latest(); self.assertEqual(len(rows), 1); self.assertTrue(rows[0]["summary"]); self.assertGreater(rows[0]["score"], 0)
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_legacy_incomplete_row_is_not_treated_as_final_content(self):
        result, ai, en, ru, store, td = self._run(legacy=True)
        try:
            rows=store.latest(); self.assertEqual(len(rows), 1); self.assertTrue(rows[0]["summary"]); self.assertGreater(rows[0]["score"], 0)
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)
