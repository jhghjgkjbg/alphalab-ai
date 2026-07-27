from datetime import UTC, datetime
from types import SimpleNamespace
from core.analytics import DistributionEvent, DistributionEventStore
from core.growth import GrowthEventRecorder, GrowthEventStore
from core.reporting import ReportingService
from core.storage.database import SQLiteDatabase

def test_reporting_distribution_growth_and_funnel_are_read_only(tmp_path):
    db = SQLiteDatabase(tmp_path / "report.db"); ds = DistributionEventStore(db); gs = GrowthEventStore(db)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    def de(eid, typ, dest="telegram_en", status="sent", metadata=None):
        return DistributionEvent(eid, now, typ, "a", dest, status, 1, metadata=metadata or {})
    ds.append(de("a1", "delivery_attempted", status="pending")); ds.append(de("a2", "delivery_succeeded")); ds.append(de("a2", "delivery_succeeded"))
    ds.append(de("b1", "delivery_attempted", "website", "pending")); ds.append(de("b2", "delivery_failed", "website", "failed"))
    ds.append(de("c1", "delivery_succeeded", "draft", metadata={"remote_publication_performed": False}))
    rec = GrowthEventRecorder(gs, clock=lambda: now); campaign = "campaign-a"
    rec.record_link_visit("anon", "a", "telegram_en", campaign, "en", "v1")
    rec.record_subscription_started(anonymous_id="anon", campaign_id=campaign)
    rec.record_subscription_confirmed(email="user@example.com", campaign_id=campaign)
    rec.record_subscription_cancelled(email="user@example.com", campaign_id=campaign)
    service = ReportingService(ds, gs); distribution = service.distribution_summary(); growth = service.growth_summary(campaign); funnel = service.conversion_funnel(campaign)
    assert [(x.destination, x.attempted, x.succeeded, x.success_rate) for x in distribution.destinations] == [("draft", 0, 1, None), ("telegram_en", 1, 1, 1.0), ("website", 1, 0, 0.0)]
    assert growth.visits == growth.subscription_started == growth.subscription_confirmed == growth.subscription_cancelled == 1
    assert funnel.visit_to_started == funnel.started_to_confirmed == funnel.visit_to_confirmed == 1.0
    assert service.growth_summary("other").visits == 0
    assert service.conversion_funnel("other").visit_to_started is None
    assert ds.list_for_article("a") and gs.list_for_campaign(campaign)

def test_reporting_empty_and_malformed_metadata(tmp_path):
    db = SQLiteDatabase(tmp_path / "empty.db"); service = ReportingService(DistributionEventStore(db), GrowthEventStore(db))
    assert service.distribution_summary().destinations == ()
    assert service.growth_summary().visits == 0
    with db.connect() as c: c.execute("INSERT INTO distribution_events VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("x", "bad", "delivery_succeeded", "a", "x", "sent", 1, None, None, None, "not-json"))
    assert service.distribution_summary().destinations[0].remote_publications == 1
