from dataclasses import dataclass

@dataclass(frozen=True)
class EditorialAIRanking:
    best_candidate_id: str | None
    confidence: float
    short_reason: str

class EditorialAIRanker:
    """Optional one-call editorial selector with deterministic fallback."""
    def __init__(self, provider=None): self.provider = provider
    def rank(self, candidates, deterministic_key=None):
        items=list(candidates)
        fallback = min(items, key=deterministic_key or (lambda x: str(getattr(x, "article_id", getattr(x, "id", ""))))) if items else None
        if not items or self.provider is None: return EditorialAIRanking(self._id(fallback), 0.0, "deterministic_fallback")
        try:
            result=self.provider(items)
            if isinstance(result, dict) and result.get("best_candidate_id"):
                return EditorialAIRanking(str(result["best_candidate_id"]), float(result.get("confidence",0)), str(result.get("short_reason", "")))
        except Exception:
            pass
        return EditorialAIRanking(self._id(fallback), 0.0, "deterministic_fallback")
    @staticmethod
    def _id(item): return str(getattr(item, "article_id", getattr(item, "id", ""))) if item is not None else None
