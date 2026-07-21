from dataclasses import dataclass
import time

@dataclass(frozen=True)
class CycleResult:
    status: str
    provider: str
    duration_ms: int

class ProductionCycle:
    def __init__(self, collect, process, provider="noop"):
        self.collect=collect; self.process=process; self.provider=provider
    async def run(self):
        started=time.perf_counter(); print("cycle_started")
        items=await self.collect()
        if not items: raise RuntimeError("no candidates")
        result=await self.process(items)
        duration=int((time.perf_counter()-started)*1000); print(f"provider={self.provider}\ncycle_finished\nduration_ms={duration}")
        return CycleResult(str(result or "published"), self.provider, duration)
