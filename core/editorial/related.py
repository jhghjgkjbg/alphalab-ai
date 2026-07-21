from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RelatedStory:
    publication_id: str
    title: str
    url: str
    source: str
    score: float


class RelatedStoryFinder:
    def __init__(self, store, limit=5):
        self.store, self.limit = store, max(3, min(5, int(limit)))

    def find(self, publication):
        current_url = str(getattr(publication, "canonical_url", "") or getattr(publication, "url", ""))
        current = set(re.findall(r"[a-z0-9]{3,}", (str(getattr(publication, "title", "")) + " " + str(getattr(publication, "summary", ""))).casefold()))
        rows = self.store.latest(limit=100)
        ranked = []
        for row in rows:
            url = str(row.get("canonical_url") or row.get("url") or "")
            if url == current_url: continue
            words = set(re.findall(r"[a-z0-9]{3,}", (str(row.get("title", "")) + " " + str(row.get("summary", ""))).casefold()))
            overlap = len(current & words)
            if overlap:
                ranked.append((overlap, RelatedStory(str(row.get("id") or row.get("publication_id") or url), str(row.get("title", "")), url, str(row.get("source", "")), float(row.get("score", 0) or 0))))
        ranked.sort(key=lambda x: (-x[0], -x[1].score, x[1].title))
        return tuple(x[1] for x in ranked[: self.limit])
