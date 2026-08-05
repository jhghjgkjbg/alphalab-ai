from types import SimpleNamespace
import asyncio
from core.delivery import DeliveryOrchestrator, DeliveryPlan, DestinationDelivery

class Publisher:
    async def publish(self, view): return SimpleNamespace(success=True, external_id="ok")

def channels(**values):
    defaults={"website":False,"telegram_en":False,"telegram_ru":False,"devto":False,"hashnode":False,"reddit":False,"x":False,"linkedin":False,"medium":False,"substack":False}
    defaults.update(values); return SimpleNamespace(**defaults)

def test_enabled_instantiated_destinations_all_sent():
    p=Publisher(); bindings=[DestinationDelivery("website",p,object()),DestinationDelivery("telegram_en",p,object()),DestinationDelivery("devto",p,object()),DestinationDelivery("hashnode",p,object())]
    r=asyncio.run(DeliveryOrchestrator(bindings=bindings,confirm_send=True).deliver(None,DeliveryPlan(channels(website=True,telegram_en=True,devto=True,hashnode=True))))
    assert r.overall == "sent"

def test_disabled_or_missing_optional_publishers_do_not_fail():
    p=Publisher(); bindings=[DestinationDelivery("website",p,object()),DestinationDelivery("reddit",None,object()),DestinationDelivery("x",None,object())]
    r=asyncio.run(DeliveryOrchestrator(bindings=bindings,confirm_send=True).deliver(None,DeliveryPlan(channels(website=True,reddit=False,x=False))))
    assert r.overall == "sent"
