import json
from pathlib import Path
from .schemas import PublishedArticle

class PublishedArticlesStore:
    def __init__(self, path=None, max_records=10000): self.path=Path(path) if path else Path(__file__).resolve().parents[2] / "runtime" / "published_articles.json"; self.max_records=max_records; self._items=self._load()
    def _load(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError): return []
    def append(self, article):
        row=article.to_dict() if hasattr(article,"to_dict") else dict(article); key=row.get("id") or row.get("url"); self._items=self._load();
        if any((x.get("id") or x.get("url")) == key for x in self._items): return None
        self._items.append(row); self._items.sort(key=lambda x:x.get("published_at", ""), reverse=True); self._items=self._items[:self.max_records]; self._save(); return row
    def contains(self, article_id=None, url=None):
        self._items=self._load()
        return any((article_id and x.get("id")==article_id) or (url and x.get("url")==url) for x in self._items)
    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self._items, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(self.path)
    def latest(self, limit=20): self._items=self._load(); return self._items[:limit]
    def by_category(self, category): self._items=self._load(); return [x for x in self._items if x.get("category", "").casefold()==category.casefold()]
    def by_source(self, source): self._items=self._load(); return [x for x in self._items if x.get("source", "").casefold()==source.casefold()]
    def search(self, query):
        self._items=self._load(); q=query.casefold(); return [x for x in self._items if q in " ".join(str(x.get(k,"")) for k in ("title","summary","source","category")).casefold()]
