from __future__ import annotations
from collections.abc import Mapping

class SourceReputationCalculator:
    DEFAULTS = {"openai":1.0,"anthropic":.98,"deepmind":.98,"google":.96,"microsoft":.95,"github":.93,"arxiv":.92,"producthunt":.80,"devto":.70,"hacker_news":.65,"lobsters":.60,"reddit":.50}
    def __init__(self, default: float = .60, overrides: Mapping[str, float] | None = None, enabled: bool = True):
        self.enabled = enabled; self.default = max(0.0, min(1.0, float(default))); self.overrides = {k.casefold(): max(0.0, min(1.0, float(v))) for k,v in (overrides or self.DEFAULTS).items()}
    def calculate(self, source: str | None) -> float:
        if not self.enabled: return self.default
        return self.overrides.get(str(source or "").casefold(), self.default)
    def stats(self, sources):
        values = tuple(self.calculate(x) for x in sources)
        return {"checked": len(values), "average": sum(values)/len(values) if values else 0.0, "highest": max(values) if values else 0.0, "lowest": min(values) if values else 0.0}
