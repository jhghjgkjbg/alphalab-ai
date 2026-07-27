import asyncio
from types import SimpleNamespace

from core.delivery import DeliveryOrchestrator, DeliveryPlan, DestinationDelivery
from core.editorial.channels import PublicationChannels


class Publisher:
    def __init__(self, result=None, error=False): self.calls = 0; self.result = result or SimpleNamespace(success=True); self.error = error
    async def publish(self, view):
        self.calls += 1
        if self.error: raise RuntimeError("boom")
        return self.result


def test_generic_bindings_report_statuses_and_survive_exceptions():
    first = Publisher(error=True); second = Publisher(SimpleNamespace(success=True, external_id="x"))
    report = asyncio.run(DeliveryOrchestrator(bindings=(DestinationDelivery("custom_a", first, object()), DestinationDelivery("custom_b", second, object())), confirm_send=True).deliver(None, DeliveryPlan(PublicationChannels(False))))
    assert report.statuses["custom_a"] == "failed"
    assert report.statuses["custom_b"] == "sent"
    assert report.details["custom_b"]["external_id"] == "x"


def test_generic_skip_does_not_call_publisher():
    publisher = Publisher()
    report = asyncio.run(DeliveryOrchestrator(bindings=(DestinationDelivery("custom", publisher, object()),), confirm_send=True).deliver(None, DeliveryPlan(PublicationChannels(False)), skip_destinations={"custom"}))
    assert publisher.calls == 0
    assert report.statuses["custom"] == "sent"


def test_enabled_destinations_preserves_legacy_ids():
    assert PublicationChannels(True, True, False).enabled_destinations() == ("website", "telegram_en")
