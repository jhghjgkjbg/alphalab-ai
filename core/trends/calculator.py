from math import sqrt
from typing import Any, Iterable

class TrendBooster:
    def __init__(self, threshold: float = .85, enabled: bool = True): self.threshold=threshold; self.enabled=enabled
    def bonus(self, candidate: Any, materials: Iterable[Any]) -> float:
        if not self.enabled: return 0.0
        vector=tuple((getattr(candidate, "payload", {}) or {}).get("embedding", ()))
        if not vector: return 0.0
        sources=set()
        for item in materials:
            if item is candidate: continue
            other=tuple((getattr(item, "payload", {}) or {}).get("embedding", ()))
            if len(other)!=len(vector) or not other: continue
            dot=sum(a*b for a,b in zip(vector,other)); na=sqrt(sum(x*x for x in vector)); nb=sqrt(sum(x*x for x in other))
            if na and nb and dot/(na*nb)>=self.threshold: sources.add(str(getattr(item,"source","")))
        count=len(sources)
        return min(.10, .03 if count>=2 else 0.0 if count<2 else .06) if count < 3 else min(.10, .06 if count==3 else .10)
