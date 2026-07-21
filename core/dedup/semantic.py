from dataclasses import dataclass
from .normalize import normalize_title, normalize_url

@dataclass(frozen=True)
class DeduplicationDecision:
    duplicate: bool
    confidence: float
    matched_publication_id: str | None = None
    reasons: tuple[str, ...] = ()

class DeduplicationEngine:
    def __init__(self, store=None): self.store = store
    def evaluate(self, item):
        payload=getattr(item,"payload",{}) if not isinstance(item,dict) else item; payload=payload if isinstance(payload,dict) else {}
        url=normalize_url(str(payload.get("url", ""))); title=normalize_title(str(payload.get("title", "")))
        rows=self.store.latest(10000) if self.store and hasattr(self.store,"latest") else ()
        for row in rows:
            if url and normalize_url(str(row.get("canonical_url") or row.get("url") or "")) == url:
                return DeduplicationDecision(True,1.0,str(row.get("id") or row.get("publication_id")),("canonical_url",))
            if title and normalize_title(str(row.get("title") or row.get("original_title") or "")) == title:
                return DeduplicationDecision(True,.95,str(row.get("id") or row.get("publication_id")),("normalized_title",))
        return DeduplicationDecision(False,0.0,reasons=("new_publication",))
