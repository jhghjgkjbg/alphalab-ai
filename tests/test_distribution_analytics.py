import asyncio
from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
from core.analytics import DistributionEvent, DistributionEventStore
from core.delivery import DeliveryOrchestrator, DestinationDelivery, DeliveryPlan
from core.storage.database import SQLiteDatabase

def event(**kw):
    base=dict(event_id="e1", occurred_at=datetime(2026,1,1,tzinfo=UTC), event_type="delivery_succeeded", article_id="a", destination_id="x", delivery_status="sent", attempt_number=1)
    base.update(kw); return DistributionEvent(**base)

def test_append_idempotent_ordered_and_metadata_allowlisted(tmp_path):
    store=DistributionEventStore(SQLiteDatabase(tmp_path/"a.db")); first=event(metadata={"publisher_kind":"fake","token":"SECRET"})
    store.append(first); store.append(first)
    rows=store.list_for_article("a"); assert len(rows)==1 and "SECRET" not in rows[0]["metadata_json"]
    assert store.count_by_event_type()["delivery_succeeded"] == 1

def test_delivery_emits_attempt_and_success(tmp_path):
    class P:
        async def publish(self, view): return SimpleNamespace(success=True, external_id="id")
    analytics=DistributionEventStore(SQLiteDatabase(tmp_path/"a.db")); pub=SimpleNamespace(article_id="a")
    binding=DestinationDelivery("x",P(),object())
    asyncio.run(DeliveryOrchestrator(bindings=(binding,),confirm_send=True,analytics_store=analytics).deliver(pub,DeliveryPlan(SimpleNamespace(x=True))))
    assert [r["event_type"] for r in analytics.list_for_article("a")] == ["delivery_attempted"]

def test_future_emits_only_deferred(tmp_path):
    class P:
        async def publish(self, view): raise AssertionError
    analytics=DistributionEventStore(SQLiteDatabase(tmp_path/"a.db")); now=datetime(2026,1,1,tzinfo=UTC)
    binding=DestinationDelivery("x",P(),object(),now+timedelta(hours=1)); pub=SimpleNamespace(article_id="a")
    asyncio.run(DeliveryOrchestrator(bindings=(binding,),confirm_send=True,clock=lambda:now,analytics_store=analytics).deliver(pub,DeliveryPlan(SimpleNamespace(x=True))))
    rows=analytics.list_for_article("a"); assert len(rows)==1 and rows[0]["event_type"] == "delivery_deferred"

def test_event_contract_validation_and_immutable_metadata():
    from dataclasses import FrozenInstanceError
    import pytest
    e = event(metadata={"publisher_kind": "fake"})
    with pytest.raises(FrozenInstanceError): e.event_type = "delivery_failed"
    with pytest.raises(TypeError): e.metadata["publisher_kind"] = "changed"
    assert e.metadata["publisher_kind"] == "fake"
    with pytest.raises(ValueError): event(occurred_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError): event(event_type="bad")
    with pytest.raises(ValueError): event(delivery_status="bad")
    with pytest.raises(ValueError): event(attempt_number=-1)
    with pytest.raises(ValueError): event(article_id="")
    with pytest.raises(ValueError): event(reason="not safe!")

def test_attempt_number_is_persisted_attempt_and_skips_are_logged(tmp_path):
    class P:
        async def publish(self, view): return SimpleNamespace(success=True, external_id="id")
    db = SQLiteDatabase(tmp_path / "a.db")
    analytics = DistributionEventStore(db)
    from core.storage.stores import SQLitePublishedArticlesStore
    persisted = SQLitePublishedArticlesStore(db)
    pub = SimpleNamespace(article_id="a")
    binding = DestinationDelivery("x", P(), object())
    asyncio.run(DeliveryOrchestrator(bindings=(binding,), confirm_send=True, analytics_store=analytics).deliver(pub, DeliveryPlan(SimpleNamespace(x=True))))
    rows = analytics.list_for_article("a")
    assert [r["attempt_number"] for r in rows] == [1]
    persisted.begin_delivery_attempt("a", "u", "x")
    persisted.record_delivery("a", "u", "x", "failed", error="bad")
    binding = DestinationDelivery("x", P(), object(), attempt_number=2)
    asyncio.run(DeliveryOrchestrator(bindings=(binding,), confirm_send=True, analytics_store=analytics).deliver(pub, DeliveryPlan(SimpleNamespace(x=True))))
    assert analytics.list_for_article("a")[-1]["attempt_number"] == 2
    asyncio.run(DeliveryOrchestrator(bindings=(binding,), confirm_send=True, analytics_store=analytics).deliver(pub, DeliveryPlan(SimpleNamespace(x=True)), skip_destinations={"x"}))
    assert analytics.list_for_article("a")[-1]["event_type"] == "delivery_skipped"

def test_event_identity_and_schema_are_stable(tmp_path):
    db = SQLiteDatabase(tmp_path / "schema.db")
    store = DistributionEventStore(db)
    a = event(event_id="", article_id="a", destination_id="x", attempt_number=1)
    b = event(event_id="", article_id="a", destination_id="x", attempt_number=1)
    assert store.event_id(a) == store.event_id(b)
    assert store.event_id(a) != store.event_id(event(event_id="", attempt_number=2))
    with db.connect() as c:
        cols = {r[1]: r for r in c.execute("PRAGMA table_info(distribution_events)")}
        indexes = {r[1] for r in c.execute("PRAGMA index_list(distribution_events)")}
    assert cols["event_id"][5] == 1 and cols["metadata_json"][3] == 1
    assert {"idx_distribution_article", "idx_distribution_destination", "idx_distribution_type"} <= indexes
