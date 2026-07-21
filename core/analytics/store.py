import json
from pathlib import Path

class AnalyticsStore:
    def __init__(self, path="runtime/analytics.json"):
        self.path=Path(path); self.data=self._load()
    def _load(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError): return {"counters":{},"sources":{},"categories":{},"daily":{}}
    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(self.path)
