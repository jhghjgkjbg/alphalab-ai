from __future__ import annotations

from core.dedup.engine import DedupEngine
from core.ranking.engine import RankingEngine
from core.scoring.engine import ScoringEngine
from core.enrichment.pre_ai import pre_ai_filter, EditorialCache
from .types import PipelineResult, PipelineStats, StageStats, StageFailure
import traceback
import json
import re

class AIPipeline:
    def __init__(self, *, collector, dedup=None, embedding_engine=None, similarity_engine=None, gateway=None, ranking_engine=None, scoring_engine=None, publication_engine=None, pre_ai_enabled=True, pre_ai_max_candidates=5, max_editorial_ai_calls=5, editorial_cache=None):
        self._collector=collector; self._dedup=dedup or DedupEngine(); self._embedding=embedding_engine; self._similarity=similarity_engine; self._gateway=gateway; self._ranking=ranking_engine or (RankingEngine(gateway) if gateway else None); self._scoring=scoring_engine or ScoringEngine(); self._publication=publication_engine; self._pre_ai_enabled=pre_ai_enabled; self._pre_ai_max=pre_ai_max_candidates; self._editorial_limit=max_editorial_ai_calls; self._editorial_cache=editorial_cache or EditorialCache()

    async def run(self) -> PipelineResult:
        if callable(self._collector):
            raw = self._collector()
            if hasattr(raw, "__await__"): raw = await raw
        else: raw = await self._collector.run_enabled()
        if isinstance(raw, tuple) and raw and hasattr(raw[0], "items"): raw = tuple(item for result in raw for item in result.items)
        raw = tuple(raw or ()); stages=[StageStats("collect",0,len(raw))]
        if not raw: return PipelineResult((), PipelineStats(tuple(stages)))
        unique, groups, dedup_stats = self._dedup.deduplicate(raw)
        dedup_failures = tuple(StageFailure(_record_key(item), "DuplicateItem", "duplicate item removed", "" ) for group in groups for item in group.items[1:])
        stages.append(StageStats("dedup",len(raw),len(unique),dedup_stats.duplicate_items, dedup_failures))
        if not unique: return PipelineResult((), PipelineStats(tuple(stages)))
        unique, _ = pre_ai_filter(unique, enabled=self._pre_ai_enabled, max_candidates=self._pre_ai_max)
        stages.append(StageStats("pre_ai_filter", len(raw), len(unique), max(0, len(raw) - len(unique))))
        enriched = 0; enrichment_failures = []
        editorial_calls = 0
        if self._gateway:
            for item in unique:
                payload = getattr(item, "payload", None)
                if not isinstance(payload, dict):
                    enrichment_failures.append(_failure(item, TypeError("record payload is not a mapping")))
                    continue
                text = str(payload.get("summary") or payload.get("title") or "").strip()
                if not text:
                    enrichment_failures.append(_failure(item, ValueError("record has no text to enrich")))
                    continue
                try:
                    cached = self._editorial_cache.get(item)
                    if cached is not None:
                        payload["enrichment"] = cached; enriched += 1; continue
                    if self._editorial_limit > 0 and editorial_calls >= self._editorial_limit:
                        continue
                    editorial_calls += 1
                    prompt = ("Return only JSON with keys summary, why_this_matters, target_audience, "
                              "category, importance, verdict. Use concise English editorial text.\n" + text)
                    response = await self._gateway.summarize(prompt)
                    if not getattr(response, "success", False):
                        err = getattr(response, "error", None)
                        raise RuntimeError(f"editorial enrichment failed: {getattr(err, 'message', 'unknown provider error')}")
                    editorial = _parse_editorial(getattr(response, "output", None))
                    if editorial is None:
                        raise ValueError("malformed editorial response")
                    payload["enrichment"] = {
                        **editorial,
                        "tags": tuple(payload.get("tags", ())),
                    }
                    self._editorial_cache.set(item, payload["enrichment"])
                    enriched += 1
                except Exception as exc:
                    enrichment_failures.append(_failure(item, exc))
                    payload["enrichment"] = {"summary": text, "category": None, "tags": tuple(payload.get("tags", ())), "novelty_score": None, "relevance_explanation": None}
            stages.append(StageStats("enrichment", len(unique), enriched, len(unique) - enriched, tuple(enrichment_failures)))
        if self._embedding:
            embedded=[]; embedding_failures=[]
            for item in unique:
                text=getattr(item,"payload",{}).get("title", "")
                result=await self._embedding.embed(text)
                if result.vector: embedded.append((item,result.vector))
                else:
                    err = getattr(result, "error", None)
                    embedding_failures.append(_failure(item, RuntimeError(getattr(err, "message", "embedding returned no vector"))))
            stages.append(StageStats("embeddings",len(unique),len(embedded),len(unique)-len(embedded), tuple(embedding_failures)))
        else: embedded=[(item,None) for item in unique]
        if not embedded: return PipelineResult((), PipelineStats(tuple(stages)))
        candidates=[item for item,_ in embedded]
        if self._similarity and candidates:
            reference = candidates[0]
            similar = await self._similarity.find_similar(self._text(reference), candidates, 0.0, len(candidates))
            candidates = [match.item for match in similar.matches]
            stages.append(StageStats("similarity",len(embedded),len(candidates),len(embedded)-len(candidates)))
        else: stages.append(StageStats("similarity",len(candidates),len(candidates)))
        ranked=await self._ranking.rank(candidates) if self._ranking else None
        ranked_items=ranked.items if ranked else tuple(candidates)
        ranking_failures = tuple(StageFailure(record, exc_type, message, f"RankingEngine diagnostic: {exc_type}: {message}\n") for record, exc_type, message in (ranked.stats.failures if ranked else ()))
        stages.append(StageStats("ranking",len(candidates),len(ranked_items),len(candidates)-len(ranked_items), ranking_failures))
        scored=self._scoring.score_items([__import__("core.scoring.types",fromlist=["ScoringRequest"]).ScoringRequest(x.item, ranking_score=x.final_score) for x in ranked_items]); stages.append(StageStats("scoring",len(ranked_items),len(scored.items)))
        published=scored.items
        if self._publication:
            publication=await self._publication.publish_scored(scored.items); published=publication.items; stages.append(StageStats("publication",len(scored.items),len(published)))
        return PipelineResult(tuple(published),PipelineStats(tuple(stages)))

    @staticmethod
    def _text(item):
        payload = getattr(item, "payload", {}) or {}
        return str(payload.get("summary") or payload.get("title") or "")

def _record_key(item):
    return str(getattr(item, "external_id", None) or getattr(item, "url", None) or getattr(getattr(item, "payload", {}), "get", lambda *_: None)("url") or "<unknown>")

def _failure(item, exc):
    rendered = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if not exc.__traceback__:
        rendered += "Traceback (diagnostic capture):\n" + "".join(traceback.format_stack(limit=12))
    return StageFailure(_record_key(item), type(exc).__name__, str(exc), rendered)

def _parse_editorial(output):
    if not isinstance(output, str): return None
    candidates = [output.strip()]
    candidates += [block.strip() for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", output, re.I)]
    for start, char in enumerate(output):
        if char != "{": continue
        depth = 0; quoted = False; escaped = False
        for index in range(start, len(output)):
            current = output[index]
            if quoted:
                if escaped: escaped = False
                elif current == "\\": escaped = True
                elif current == '"': quoted = False
            elif current == '"': quoted = True
            elif current == "{": depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(output[start:index + 1]); break
    allowed_categories = {"AI", "Software Development", "Open Source", "Cybersecurity", "Startups", "Business", "Science", "Climate Tech", "Hardware", "Crypto", "Other"}
    allowed_importance = {"breaking", "important", "insight", "research", "standard"}
    allowed_verdicts = {"Must Read", "Worth Reading", "Interesting", "Research"}
    for candidate in candidates:
        try: data = json.loads(candidate)
        except (TypeError, ValueError, json.JSONDecodeError): continue
        if not isinstance(data, dict) or not isinstance(data.get("summary"), str): continue
        summary = " ".join(data["summary"].split())[:600]
        if not summary: continue
        def values(value):
            if isinstance(value, str): value = value.replace(",", "\n").splitlines()
            if not isinstance(value, (list, tuple)): return []
            result = []
            for entry in value:
                item = " ".join(str(entry).strip(" •-\t").split())
                if item and item.casefold() not in {x.casefold() for x in result}: result.append(item)
            return result[:3]
        category = data.get("category") if data.get("category") in allowed_categories else "Other"
        importance = data.get("importance") if data.get("importance") in allowed_importance else "standard"
        verdict = data.get("verdict") if data.get("verdict") in allowed_verdicts else ""
        return {"summary": summary, "why_this_matters": values(data.get("why_this_matters")), "target_audience": values(data.get("target_audience")), "category": category, "importance": importance, "verdict": verdict}
    return None
