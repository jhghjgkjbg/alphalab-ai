from dataclasses import replace
from core.publication.models import LanguageVariant
class TelegramPolicy:
    def __init__(self, max_preview=600, max_paragraphs=3, site_url=""): self.max_preview=max_preview; self.max_paragraphs=max_paragraphs; self.site_url=site_url
    def apply(self, variant: LanguageVariant) -> LanguageVariant:
        paragraphs=[p.strip() for p in variant.summary.split("\n") if p.strip()][:self.max_paragraphs]; text="\n\n".join(paragraphs)[:self.max_preview]
        return replace(variant,summary=text)
