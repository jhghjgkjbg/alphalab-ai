import asyncio
import unittest
from core.ai_gateway.router import AIRouter, ProviderMetadata
from core.ai_gateway.gateway import AIGateway
from core.ai_gateway.types import AIRequest, AIResponse

class P:
    def __init__(self, name, fail=False): self.name=name; self.fail=fail; self.calls=0
    async def execute(self, request):
        self.calls += 1
        if self.fail: raise RuntimeError("x")
        return AIResponse(True, self.name)

def meta(name, cost=1, quality=1, ops=("classify",)): return ProviderMetadata(name, True, 1, cost, 1, quality, frozenset(ops))

class RouterTests(unittest.TestCase):
    def test_selection_disabled_and_fallback(self):
        async def run():
            cheap, quality = P("cheap"), P("quality"); r=AIRouter(); r.register(quality, meta("quality", quality=5)); r.register(cheap, meta("cheap", cost=.1)); self.assertEqual((await r.execute(AIRequest("classify","x"))).output,"cheap")
            failed=P("bad",True); r=AIRouter(); r.register(failed, meta("bad")); self.assertTrue((await r.execute(AIRequest("classify","x"))).success)
            self.assertTrue((await AIGateway(router=AIRouter()).classify("x")).success)
        asyncio.run(run())

if __name__ == "__main__": unittest.main()
