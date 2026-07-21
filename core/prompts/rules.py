from dataclasses import dataclass, field
from typing import Mapping, Any, Protocol
@dataclass(frozen=True, slots=True)
class PromptParts:
    system_parts: tuple[str,...]=(); user_parts: tuple[str,...]=(); metadata: Mapping[str,Any]=field(default_factory=dict)
class PromptRule(Protocol):
    priority: int
    def apply(self, publication, prompt_parts: PromptParts) -> PromptParts: ...
class _Rule:
    priority=10
    def __init__(self,priority=10): self.priority=priority
class IdentityRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts+("You are an editorial assistant. Produce bilingual content in the existing JSON fields. en_title and en_body MUST be written in English. ru_title and ru_body MUST be written in Russian using Cyrillic characters; ru_title MUST be an idiomatic Russian news headline for Russian readers. Translate and adapt it naturally, never transliterate, never copy the English title, and never leave Russian fields in English. Keep both language variants complete and faithful to the source.",),x.user_parts,x.metadata)
class LanguageRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts,x.user_parts+(f"Language: {p.language}.",),x.metadata)
class EditorialRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts,x.user_parts+("Preserve meaning and factual tone.",),x.metadata)
class QualityRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts,x.user_parts+(f"Quality score: {p.final_quality_score}.",),x.metadata)
class RankingRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts,x.user_parts+(f"Ranking score: {p.ranking_score}.",),x.metadata)
class MetricsRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts,x.user_parts+(f"Source: {p.source}; category: {p.category}.",),x.metadata)
class ContextRule(_Rule):
    def apply(self,p,x): return PromptParts(x.system_parts,x.user_parts+(f"Title: {p.title}\nSummary: {p.summary}",),x.metadata)
