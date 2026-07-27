from datetime import UTC, datetime, timedelta, timezone
import pytest
from core.growth import GrowthEvent, GrowthEventRecorder, GrowthEventStore
from core.growth.attribution import build_campaign_id, build_link_id
from core.storage.database import SQLiteDatabase

def test_privacy_safe_identity_and_append_only(tmp_path):
    store = GrowthEventStore(SQLiteDatabase(tmp_path / "growth.db")); rec = GrowthEventRecorder(store, clock=lambda: datetime(2026,1,1,tzinfo=UTC))
    sid = rec.subscriber_id(" User@Example.com "); assert sid.startswith("email_sha256:v1:") and "User@" not in sid
    rec.record_subscription_confirmed(email="USER@example.com", source_event_id="confirm-1")
    rec.record_subscription_confirmed(email=" user@example.com ", source_event_id="confirm-1")
    rows = store.list_for_subscriber(sid); assert len(rows) == 1

def test_attribution_and_visits_are_deterministic(tmp_path):
    store = GrowthEventStore(SQLiteDatabase(tmp_path / "growth.db")); rec = GrowthEventRecorder(store)
    campaign = build_campaign_id("a"); one = build_link_id("a", "telegram_en", campaign, "en")
    assert one == build_link_id("a", "telegram_en", campaign, "en") and one != build_link_id("a", "telegram_ru", campaign, "en")
    rec.record_link_visit("anon", "a", "telegram_en", campaign, "en", "visit-1")
    rec.record_link_visit("anon", "a", "telegram_en", campaign, "en", "visit-2")
    assert len(store.list_for_anonymous("anon")) == 2

def test_event_validation_and_safe_metadata(tmp_path):
    with pytest.raises(ValueError): GrowthEvent("e", datetime(2026,1,1), "link_visited", anonymous_id="a")
    store = GrowthEventStore(SQLiteDatabase(tmp_path / "growth.db")); rec = GrowthEventRecorder(store)
    rec.record_subscription_started(anonymous_id="a", metadata={"locale":"en", "email":"secret@example.com", "nested":{"x":1}})
    row = store.list_for_anonymous("a")[0]; assert "secret@example.com" not in row["metadata_json"] and "nested" not in row["metadata_json"]

def test_offset_normalization_and_allowed_metadata_values(tmp_path):
    store = GrowthEventStore(SQLiteDatabase(tmp_path / "growth.db")); rec = GrowthEventRecorder(store, clock=lambda: datetime(2026, 1, 1, 3, 0, tzinfo=timezone(timedelta(hours=3))))
    rec.record_subscription_started(anonymous_id="anon", metadata={"locale": "en", "signup_surface": "https://bad.example/?token=x", "subscription_provider": "web", "phone": "+123"})
    row = store.list_for_anonymous("anon")[0]
    assert row["occurred_at"].startswith("2026-01-01T00:00:00")
    assert "https://" not in row["metadata_json"] and "+123" not in row["metadata_json"]
    with pytest.raises(ValueError): rec.record_subscription_confirmed()

def test_storage_queries_indexes_and_append_only(tmp_path):
    db = SQLiteDatabase(tmp_path / "growth.db"); store = GrowthEventStore(db)
    rec = GrowthEventRecorder(store)
    campaign = build_campaign_id("a")
    rec.record_link_visit("anon", "a", "telegram_en", campaign, "en", "v1")
    rec.record_link_visit("anon", "b", "telegram_en", campaign, "en", "v2")
    rec.record_subscription_cancelled(email="user@example.com", source_event_id="cancel")
    with db.connect() as c:
        indexes = {r[1] for r in c.execute("PRAGMA index_list(growth_events)")}
        before = c.execute("SELECT COUNT(*) FROM growth_events").fetchone()[0]
    assert {"idx_growth_subscriber", "idx_growth_anonymous", "idx_growth_article_destination", "idx_growth_campaign", "idx_growth_link", "idx_growth_type"} <= indexes
    assert len(store.list_for_anonymous("anon")) == 2
    assert len(store.list_for_campaign(campaign, limit=1)) == 1
    assert len(store.list_for_link(build_link_id("a", "telegram_en", campaign, "en"))) == 1
    with pytest.raises(ValueError): store.list_for_campaign(campaign, limit=-1)
    assert not hasattr(store, "update") and not hasattr(store, "delete")
    with db.connect() as c: assert c.execute("SELECT COUNT(*) FROM growth_events").fetchone()[0] == before
