from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from core.scheduler.adaptive import AdaptivePublicationScheduler

def test_below_threshold_uses_scheduled_fallback():
    s=AdaptivePublicationScheduler(90,30); assert s.select_immediate([SimpleNamespace(final_score=89)]) is None
def test_immediate_and_cooldown_select_highest():
    now=[datetime(2026,1,1,tzinfo=UTC)]; s=AdaptivePublicationScheduler(90,30,lambda:now[0])
    assert s.select_immediate([SimpleNamespace(final_score=91),SimpleNamespace(final_score=99)]).final_score==99
    s.record_immediate_success()
    assert s.select_immediate([SimpleNamespace(final_score=100)]) is None
    now[0]+=timedelta(minutes=31)
    assert s.select_immediate([SimpleNamespace(final_score=95)]).final_score==95
