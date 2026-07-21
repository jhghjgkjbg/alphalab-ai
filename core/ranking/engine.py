import json
import re
from .prompts import ranking_prompt
from .types import RankedItem, RankingResult, RankingStats

class RankingEngine:
    def __init__(self, gateway, weights=None, batch_size=16, max_items=100, min_score=0.0):
        self._gateway = gateway; self._weights = weights or {"relevance": .25, "novelty": .25, "technical": .25, "business": .25}; self._batch_size=batch_size; self._max_items=max_items; self._min_score=min_score

    async def rank(self, items) -> RankingResult: return await self._run(items)
    async def rank_batch(self, items) -> RankingResult: return await self._run(items)
    async def rerank(self, items) -> RankingResult: return await self._run(items)

    async def _run(self, items):
        source=list(items or ())[:self._max_items]; unique=[]; seen=set()
        for item in source:
            text=self._text(item)
            if text and text not in seen: seen.add(text); unique.append((item,text))
        ranked=[]; failed=0; cached=0; failures=[]
        for start in range(0,len(unique),self._batch_size):
            for item,text in unique[start:start+self._batch_size]:
                try:
                    response=await self._gateway.rank(ranking_prompt(text))
                except Exception as exc:
                    failed+=1; failures.append((self._record(item), type(exc).__name__, str(exc))); continue
                if not response.success:
                    failed+=1; err=response.error; failures.append((self._record(item), type(err).__name__ if err else "AIError", getattr(err,"message","provider failure"))); continue
                cached += int(bool(response.usage and response.usage.cached))
                scores=self._parse(response.output)
                if scores is None: failed+=1; failures.append((self._record(item), "ValueError", f"malformed ranking response: {response.output!r}")); continue
                final=sum(scores[k]*self._weights.get(k,0) for k in scores)
                if final>=self._min_score: ranked.append(RankedItem(item,*[scores[k] for k in ("relevance","novelty","technical","business")],final))
        ranked.sort(key=lambda x:(-x.final_score, str(self._text(x.item))))
        return RankingResult(tuple(ranked), RankingStats(len(source),len(ranked),failed,cached,tuple(failures)))

    @staticmethod
    def _text(item):
        if isinstance(item,str): return item.strip()
        payload=getattr(item,"payload",{}) or {}; return str(payload.get("title") or payload.get("summary") or "").strip()
    @staticmethod
    def _record(item):
        return str(getattr(item, "external_id", None) or getattr(item, "url", None) or "<unknown>")
    @staticmethod
    def _parse(output):
        required = ("relevance_score", "novelty_score", "technical_depth", "business_value")
        candidates = [output] if not isinstance(output, str) else [output.strip()]
        if isinstance(output, str):
            text = output
            for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE):
                candidates.append(block.strip())
            candidates.extend(RankingEngine._objects(text))
        for candidate in candidates:
            try:
                data = json.loads(candidate) if isinstance(candidate, str) else candidate
                if not isinstance(data, dict) or any(key not in data for key in required):
                    continue
                values = {"relevance": float(data[required[0]]), "novelty": float(data[required[1]]), "technical": float(data[required[2]]), "business": float(data[required[3]])}
                if any(not 0 <= value <= 1 for value in values.values()):
                    continue
                return values
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return None

    @staticmethod
    def _objects(text):
        for start, char in enumerate(text):
            if char != "{":
                continue
            depth = 0; quoted = False; escaped = False
            for index in range(start, len(text)):
                current = text[index]
                if quoted:
                    if escaped: escaped = False
                    elif current == "\\": escaped = True
                    elif current == '"': quoted = False
                    continue
                if current == '"': quoted = True
                elif current == "{": depth += 1
                elif current == "}":
                    depth -= 1
                    if depth == 0:
                        yield text[start:index + 1]
                        break
