import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from scripts import check_distribution_config as preflight
from scripts import run_scheduled_distribution as scheduled
from core.analytics import DistributionEventStore
from core.delivery import DeliveryOrchestrator, DestinationDelivery, DeliveryPlan
from core.growth import GrowthEventStore
from core.reporting import ReportingService
from core.storage.database import SQLiteDatabase

def _settings(**extra):
    values = dict(telegram_en_enabled=False, telegram_ru_enabled=False, x_enabled=False, linkedin_enabled=False, medium_enabled=False, devto_enabled=False, hashnode_enabled=False, substack_enabled=False, reddit_enabled=False, publish_at=None, telegram_bot_token=None, telegram_en_chat_id=None, telegram_ru_chat_id=None, x_bearer_token="", linkedin_access_token="", linkedin_author_urn="", medium_integration_token="", medium_author_id="", devto_api_key="", hashnode_personal_access_token="", hashnode_publication_id="")
    values.update(extra); return SimpleNamespace(**values)

def test_preflight_and_single_runner_lock(tmp_path, monkeypatch):
    assert all(x["ready"] for x in preflight.check(_settings(), tmp_path, tmp_path / "lock").values())
    calls = []
    monkeypatch.setattr(scheduled.subprocess, "run", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0))
    lock = tmp_path / "run.lock"
    assert scheduled.run_once(lock_path=lock) == 0 and len(calls) == 1
    lock.write_text("active", encoding="utf-8")
    assert scheduled.run_once(lock_path=lock) == 2 and len(calls) == 1

def test_future_deferred_website_immediate_and_no_growth(tmp_path):
    db = SQLiteDatabase(tmp_path / "accept.db"); now = datetime(2026, 1, 1, tzinfo=UTC); calls = []
    class P:
        async def publish(self, view): calls.append(view); return SimpleNamespace(success=True, external_id="local")
    pub = SimpleNamespace(article_id="a")
    bindings = (DestinationDelivery("website", P(), object()), DestinationDelivery("x", P(), object(), now + timedelta(hours=1)))
    report = asyncio.run(DeliveryOrchestrator(bindings=bindings, confirm_send=True, clock=lambda: now).deliver(pub, DeliveryPlan(SimpleNamespace(website=True, x=True))))
    assert report.website == "sent" and report.statuses["x"] == "pending" and len(calls) == 1
    assert GrowthEventStore(db).list_for_campaign("none") == []

def test_reporting_is_read_only_and_draft_not_remote(tmp_path):
    db = SQLiteDatabase(tmp_path / "report.db"); before = db.path.read_bytes()
    report = ReportingService(DistributionEventStore(db), GrowthEventStore(db)).distribution_summary()
    assert report.destinations == () and db.path.read_bytes() == before
