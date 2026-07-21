from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

class TranslationCache:
    def __init__(self, path="runtime/translation_cache.json", ttl_hours=720): self.path=Path(path); self.ttl_hours=ttl_hours; self._data=self._load()
    def _load(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError): return {}
    def key(self, payload: dict[str, Any]) -> str: return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    def get(self, key): return self._data.get(key)
    def set(self, key, value):
        self._data[key]=value; self.path.parent.mkdir(parents=True, exist_ok=True); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding='utf-8'); tmp.replace(self.path)

class RussianTranslator:
    def __init__(self, gateway, cache: TranslationCache | None = None): self.gateway=gateway; self.cache=cache or TranslationCache()
    async def translate(self, editorial: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
        source={k:editorial.get(k) for k in ("title","summary","why_this_matters","target_audience","verdict")}; key=self.cache.key({"source":source,"lang":"ru","version":1})
        cached=self.cache.get(key)
        if isinstance(cached, dict): return cached, True
        prompt="Translate the following editorial JSON to natural Russian. Return only JSON with the same keys, no markdown. Preserve facts and technical names: " + json.dumps(source, ensure_ascii=False)
        response=await self.gateway.summarize(prompt)
        if not getattr(response, "success", False): return None, False
        try:
            data=json.loads(response.content if hasattr(response,"content") else response.text)
            if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not isinstance(data.get("summary"), str): return None, False
        except (ValueError, TypeError, AttributeError): return None, False
        self.cache.set(key, data); return data, False
