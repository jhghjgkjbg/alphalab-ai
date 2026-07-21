import hashlib, json
from typing import Protocol
from .types import Prompt
from .rules import PromptParts, IdentityRule, LanguageRule, EditorialRule, QualityRule, RankingRule, MetricsRule, ContextRule
class PromptBuilder(Protocol):
    def build(self, publication, facts=None, angle=None, headline=None, audience=None) -> Prompt: ...
class DefaultPromptBuilder:
    def __init__(self,version="v1",rules=None,memory=None): self.version=version; self.memory=memory; self.rules=tuple(sorted(rules or (IdentityRule(),LanguageRule(),EditorialRule(),QualityRule(),RankingRule(),MetricsRule(),ContextRule()),key=lambda r:r.priority))
    def build(self,publication, facts=None, angle=None, headline=None, audience=None):
        parts=PromptParts()
        for rule in self.rules: parts=rule.apply(publication,parts)
        raw="\n".join(parts.user_parts); 
        raw += "\n\nEditorial structure guidance: write a natural article with a 1–2 sentence lead, main development, why it matters, technical context, and outlook. Do not expose section headers; integrate the structure into fluent prose."
        if self.memory: raw += "\n\n" + self.memory.instructions()
        if facts: raw += "\n\nVerified editorial facts:\n" + "\n".join(str(x) for x in facts.verified_facts)
        selected_angle = angle or getattr(publication, "editorial_plan", None)
        if selected_angle:
            name = getattr(selected_angle, "name", getattr(selected_angle, "angle", selected_angle))
            guidance = getattr(selected_angle, "guidance", "Adapt emphasis to this angle.")
            raw += f"\n\nStory angle: {name}. {guidance}."
        if headline:
            raw += f"\n\nSelected editorial headline: {headline}. Use it as the primary headline."
        if audience:
            raw += f"\n\nAudience: {getattr(audience, 'audience', audience)}; adjust vocabulary, technical detail, and explanation depth to the reader."
        digest=hashlib.sha256(raw.encode()).hexdigest()
        return Prompt("\n".join(parts.system_parts),raw,{"source":publication.source},publication.language,self.version,digest)
