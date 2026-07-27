from datetime import datetime, UTC, timedelta
import asyncio
from types import SimpleNamespace
import pytest
from core.delivery import DestinationDelivery, DeliveryOrchestrator, DeliveryPlan, is_delivery_due
from core.storage.database import SQLiteDatabase
from core.storage.stores import SQLitePublishedArticlesStore

class P:
    def __init__(self): self.calls=0
    async def publish(self, view): self.calls += 1; return SimpleNamespace(success=True, external_id="x")

def test_due_decision_and_naive_rejection():
    now=datetime(2026,1,1,tzinfo=UTC)
    assert is_delivery_due(None, now) and is_delivery_due(now, now) and is_delivery_due(now-timedelta(seconds=1), now)
    assert not is_delivery_due(now+timedelta(seconds=1), now)
    with pytest.raises(ValueError): is_delivery_due(datetime(2026,1,1), now)

def test_future_binding_deferred_without_publisher_call():
    p=P(); now=datetime(2026,1,1,tzinfo=UTC)
    binding=DestinationDelivery("x",p,object(),now+timedelta(hours=1))
    report=asyncio.run(DeliveryOrchestrator(bindings=(binding,),confirm_send=True,clock=lambda:now).deliver(object(),DeliveryPlan(SimpleNamespace(x=True))))
    assert p.calls == 0 and report.statuses["x"] == "pending" and report.failure_reasons["x"] == "scheduled_for_future"

def test_due_binding_runs():
    p=P(); now=datetime(2026,1,1,tzinfo=UTC)
    binding=DestinationDelivery("x",p,object(),now)
    report=asyncio.run(DeliveryOrchestrator(bindings=(binding,),confirm_send=True,clock=lambda:now).deliver(object(),DeliveryPlan(SimpleNamespace(x=True))))
    assert p.calls == 1 and report.statuses["x"] == "sent"

def test_clock_is_snapshotted_once():
    class Clock:
        def __init__(self): self.calls=0
        def __call__(self): self.calls += 1; return datetime(2026,1,1,tzinfo=UTC)
    clock=Clock(); p=P(); bindings=tuple(DestinationDelivery(str(i),p,object(),datetime(2025,1,1,tzinfo=UTC)) for i in range(3))
    asyncio.run(DeliveryOrchestrator(bindings=bindings,confirm_send=True,clock=clock).deliver(object(),DeliveryPlan(SimpleNamespace(**{str(i):True for i in range(3)}))))
    assert clock.calls == 1

def test_scheduled_for_is_persisted_and_stable(tmp_path):
    s=SQLitePublishedArticlesStore(SQLiteDatabase(tmp_path/"x.db")); first=datetime(2026,1,1,tzinfo=UTC); second=datetime(2027,1,1,tzinfo=UTC)
    s.prepare_delivery_attempt("a","u","x",scheduled_for=first); s.prepare_delivery_attempt("a","u","x",scheduled_for=second)
    rows=s.delivery_state(article_id="a",destination="x"); assert rows[0]["scheduled_for"].startswith("2026-01-01T00:00:00")
