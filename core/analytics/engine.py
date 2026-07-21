from datetime import date
from .store import AnalyticsStore

class AnalyticsEngine:
    def __init__(self, store=None, enabled=True): self.store=store or AnalyticsStore(); self.enabled=enabled
    def increment(self, metric, value=1):
        if not self.enabled: return
        self.store.data.setdefault("counters", {})[metric] = self.store.data.setdefault("counters", {}).get(metric, 0) + value; self._daily(metric, value); self.store.save()
    def observe_source(self, source, received=0, published=0):
        if not self.enabled: return
        row=self.store.data.setdefault("sources", {}).setdefault(source, {"received":0,"published":0}); row["received"]+=received; row["published"]+=published; self.store.save()
    def observe_category(self, category, value=1):
        if self.enabled: self.store.data.setdefault("categories", {})[category]=self.store.data.setdefault("categories", {}).get(category,0)+value; self.store.save()
    def _daily(self, metric, value):
        row=self.store.data.setdefault("daily", {}).setdefault(date.today().isoformat(), {})
        row[metric]=row.get(metric,0)+value
    def summary(self): return self.store.data
