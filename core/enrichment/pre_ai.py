from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

@dataclass(frozen=True, slots=True)
class PreAIDecision:
    accepted: bool
    score: float
    reason: str

class EditorialCache:
    def __init__(self, ttl_hours: float = 168):
        self._ttl = timedelta(hours=ttl_hours); self._data = {}
    def key(self, item):
        payload = getattr(item, "payload", {}) or {}; url = str(payload.get("url") or "").strip()
        if url:
            parts = urlsplit(url); url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
        title = " ".join(str(payload.get("title") or "").lower().split())
        content = str(payload.get("summary") or payload.get("content") or "")
        return hashlib.sha256(f"v1|{url}|{title}|{hashlib.sha256(content.encode()).hexdigest()}".encode()).hexdigest()
    def get(self, item):
        entry = self._data.get(self.key(item));
        if not entry or entry[0] <= datetime.now(UTC): self._data.pop(self.key(item), None); return None
        return entry[1]
    def set(self, item, value): self._data[self.key(item)] = (datetime.now(UTC) + self._ttl, value)

def pre_ai_filter(items, *, max_candidates=5, enabled=True, exploration_slots=1):
    if not enabled: return tuple(items), tuple()
    accepted=[]; rejected=[]
    for index, item in enumerate(items):
        payload = getattr(item, "payload", {}) or {}; title = str(payload.get("title") or "").strip(); text = str(payload.get("summary") or payload.get("content") or payload.get("description") or "").strip(); url = str(payload.get("url") or "").strip()
        if (not title and not text) or (title and title.lower() in {"untitled", "test", "n/a"}) or (url and not url.startswith(("http://", "https://"))):
            rejected.append((item, "hard_validation")); continue
        score = min(len(text) / 500, 1.0) * .5 + (0.3 if title else 0) + (0.2 if url else 0)
        accepted.append((score, index, item))
    accepted.sort(key=lambda value: (-value[0], value[1]))
    if max_candidates > 0 and len(accepted) > max_candidates:
        keep = accepted[:max_candidates]
        extra = accepted[max_candidates:max_candidates + max(0, exploration_slots)]
        keep.extend(extra); accepted = keep
    return tuple(item for _, _, item in accepted), tuple(rejected)
