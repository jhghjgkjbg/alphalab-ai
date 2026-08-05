from dataclasses import replace
from typing import Protocol
from .types import AIContext
from core.ai_response.types import RawAIResponse
from core.ai_response import DefaultResponseParser
from core.ai_tasks import AITaskEngine
from core.prompts import DefaultPromptBuilder
from dataclasses import replace
from core.publication.models import Publication
class AIProvider(Protocol):
    def enrich(self, prompt) -> AIContext: ...
class NoOpAIProvider:
    def enrich(self, prompt, tasks=()): return RawAIResponse(provider="noop")
class AIEnrichmentEngine:
    def __init__(self, provider=None, registry=None, prompt_builder=None, task_engine=None, parser=None): self.registry=registry; self.provider=provider or (registry.default_provider() if registry else NoOpAIProvider()); self.prompt_builder=prompt_builder or DefaultPromptBuilder(); self.task_engine=task_engine or AITaskEngine(); self.parser=parser or DefaultResponseParser()
    @staticmethod
    def _source_fallback(publication):
        import re
        metadata = getattr(publication, "metadata", {}) or {}
        text = " ".join(str(getattr(publication, "summary", "") or "").split())
        if not text:
            text = " ".join(str(metadata.get("body") or metadata.get("content") or "").split())
        title = " ".join(str(getattr(publication, "title", "") or "").split())
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        structured = bool(metadata.get("body") or metadata.get("content"))
        return bool(text and text != title and len(text) >= 160 and (len(sentences) >= 2 or structured))

    def enrich(self, publication):
        prompt=self.prompt_builder.build(publication); tasks=self.task_engine.select(publication)
        providers = self.registry.ordered() if self.registry is not None and hasattr(self.registry, "ordered") else ((getattr(self.provider, "name", "provider"), self.provider),)
        for name, provider in providers:
            if provider is None or provider.__class__.__name__ == "NoOpAIProvider":
                print(f"ai_provider_attempt={name}\nai_provider_result=skipped\nai_provider_failure_kind=configuration_missing")
                continue
            print(f"ai_provider_attempt={name}")
            try:
                raw=provider.enrich(prompt,tasks); parsed=self.parser.parse(raw)
                usable = bool(parsed.long_summary.strip() or parsed.short_summary.strip() or parsed.en_body.strip())
                if usable:
                    ctx=AIContext(keywords=parsed.seo_keywords,entities=parsed.entities,topics=parsed.topics,translation_status=parsed.translation_status,editor_notes=parsed.editor_notes,confidence=parsed.confidence,headline_suggestions=parsed.headline_suggestions,seo_keywords=parsed.seo_keywords,hashtags=parsed.hashtags,category_guess=parsed.category_guess,short_summary=parsed.short_summary,long_summary=parsed.long_summary,translation=parsed.translation,en_title=parsed.en_title,en_body=parsed.en_body,ru_title=parsed.ru_title,ru_body=parsed.ru_body)
                    print(f"ai_provider_result=success\nai_provider_selected={name}")
                    return replace(publication,ai_context=ctx)
                kind = getattr(provider, "last_failure_kind", None) or "empty_result"
            except Exception:
                kind = "unknown"
            print(f"ai_provider_result=failed\nai_provider_failure_kind={kind}")
        if self._source_fallback(publication):
            metadata = dict(getattr(publication, "metadata", {}) or {})
            metadata.update(enrichment_mode="source_fallback", ai_provider_selected="none")
            print("ai_provider_selected=none")
            return replace(publication, metadata=metadata, ai_context=AIContext())
        return replace(publication, ai_context=AIContext())
