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
    def __init__(self, provider=None, registry=None, prompt_builder=None, task_engine=None, parser=None): self.provider=provider or (registry.default_provider() if registry else NoOpAIProvider()); self.prompt_builder=prompt_builder or DefaultPromptBuilder(); self.task_engine=task_engine or AITaskEngine(); self.parser=parser or DefaultResponseParser()
    def enrich(self, publication):
        prompt=self.prompt_builder.build(publication); tasks=self.task_engine.select(publication); raw=self.provider.enrich(prompt,tasks); parsed=self.parser.parse(raw)
        ctx=AIContext(keywords=parsed.seo_keywords,entities=parsed.entities,topics=parsed.topics,translation_status=parsed.translation_status,editor_notes=parsed.editor_notes,confidence=parsed.confidence,headline_suggestions=parsed.headline_suggestions,seo_keywords=parsed.seo_keywords,hashtags=parsed.hashtags,category_guess=parsed.category_guess,short_summary=parsed.short_summary,long_summary=parsed.long_summary,translation=parsed.translation,en_title=parsed.en_title,en_body=parsed.en_body,ru_title=parsed.ru_title,ru_body=parsed.ru_body)
        return replace(publication,ai_context=ctx)
