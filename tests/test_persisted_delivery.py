import asyncio
from pathlib import Path
from types import SimpleNamespace

from core.delivery import DeliveryOrchestrator, DeliveryPlan
from core.editorial.channels import PublicationChannels
from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore


def store(tmp_path):
    return SQLitePublishedArticlesStore(SQLiteDatabase(Path(tmp_path) / "delivery.db"))


def test_delivery_attempts_and_external_ids_are_separate(tmp_path):
    s = store(tmp_path)
    for destination in ("telegram_en", "telegram_ru"):
        s.begin_delivery_attempt("a", "https://example/a", destination)
    s.record_delivery("a", "https://example/a", "telegram_en", "sent", 42)
    s.record_delivery("a", "https://example/a", "telegram_ru", "sent", 43)
    rows = {r["destination"]: r for r in s.delivery_states("a")}
    assert rows["telegram_en"]["external_id"] == "42"
    assert rows["telegram_ru"]["external_id"] == "43"


def test_attempt_count_increments_and_timeout_is_unknown(tmp_path):
    s = store(tmp_path)
    s.begin_delivery_attempt("a", "https://example/a", "telegram_en")
    s.begin_delivery_attempt("a", "https://example/a", "telegram_en")
    s.record_delivery("a", "https://example/a", "telegram_en", "unknown", error="TimeoutError")
    row = s.delivery_states("a")[0]
    assert row["attempt_count"] == 2
    assert row["status"] == "unknown"


def test_delivery_normalizes_api_failure_without_affecting_other_channel():
    class Publisher:
        def __init__(self, result): self.result = result; self.calls = 0
        async def publish(self, view): self.calls += 1; return self.result
    en = Publisher(SimpleNamespace(success=False, error_message="bad request"))
    ru = Publisher(SimpleNamespace(success=True, message_id=9))
    report = asyncio.run(DeliveryOrchestrator(telegram_publisher=en, telegram_publisher_ru=ru, confirm_send=True).deliver(
        None, DeliveryPlan(PublicationChannels(False, True, True)), telegram_en_view=object(), telegram_ru_view=object()))
    assert report.telegram_en == "failed"
    assert report.telegram_ru == "sent"
    assert report.details["telegram_ru"]["external_id"] == 9


def test_resume_policy_skips_sent_unknown_and_live_pending(tmp_path):
    s = store(tmp_path)
    for destination, status in (("telegram_en", "sent"), ("telegram_ru", "unknown"), ("website", "pending")):
        s.begin_delivery_attempt("a", "https://example/a", destination)
        if status != "pending":
            s.record_delivery("a", "https://example/a", destination, status, "7")
    assert s.prepare_delivery_attempt("a", "https://example/a", "telegram_en") == "skip"
    assert s.prepare_delivery_attempt("a", "https://example/a", "telegram_ru") == "skip"
    assert s.prepare_delivery_attempt("a", "https://example/a", "website") == "skip"


def test_stale_pending_allows_a_new_attempt(tmp_path):
    s = store(tmp_path)
    s.begin_delivery_attempt("a", "https://example/a", "website")
    with s.database.connect() as c:
        c.execute("UPDATE publication_deliveries SET updated_at='2000-01-01T00:00:00+00:00' WHERE article_id='a'")
    assert s.prepare_delivery_attempt("a", "https://example/a", "website", ttl_seconds=1) == "send"
    assert s.delivery_states("a")[0]["attempt_count"] == 2
