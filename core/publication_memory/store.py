import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from .memory import PublicationMemory

class PublicationMemoryStore:
    def __init__(self, path: str | Path = "runtime/publication_memory.json", ttl_days: int = 7, limit: int = 5000, threshold: float = .90):
        self.path, self.ttl, self.limit, self.threshold = Path(path), timedelta(days=ttl_days), limit, threshold
        self._items: list[PublicationMemory] = []; self.expired_removed = 0; self._load()
    def _load(self):
        try:
            for x in json.loads(self.path.read_text(encoding="utf-8")):
                self._items.append(PublicationMemory(x["title"], x["url"], x["source"], datetime.fromisoformat(x["published_at"]), tuple(x.get("embedding", ())), x.get("category", "")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError): self._items = []
        self._purge()
    def _purge(self):
        cutoff = datetime.now(UTC) - self.ttl; old = len(self._items); self._items = [x for x in self._items if x.published_at >= cutoff]; self.expired_removed += old-len(self._items)
    def contains(self, vector: tuple[float, ...]) -> bool:
        self._purge(); return any(x.similar(vector, self.threshold) for x in self._items)
    def add(self, item: PublicationMemory):
        self._purge(); self._items.append(item); self._items = sorted(self._items, key=lambda x:x.published_at)[-self.limit:]; self.path.parent.mkdir(parents=True, exist_ok=True); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps([{"title":x.title,"url":x.url,"source":x.source,"published_at":x.published_at.isoformat(),"embedding":list(x.embedding),"category":x.category} for x in self._items]), encoding="utf-8"); tmp.replace(self.path)
    def __len__(self): return len(self._items)
