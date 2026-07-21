from core.publication.models import LanguageVariant
class LanguageVariantEngine:
    def __init__(self,languages=("en","ru")): self.languages=tuple(languages)
    def generate(self,publication):
        context = getattr(publication, "ai_context", None)
        title = (context.headline_suggestions[0] if context and context.headline_suggestions else publication.title)
        summary = (context.short_summary or publication.summary) if context else publication.summary
        translation = (getattr(context, "translation", "") if context else "") or summary
        return tuple(LanguageVariant(language, title if language == "en" else title, summary if language == "en" else translation, summary if language == "en" else translation, summary if language == "en" else translation, tuple(context.seo_keywords) if context else (), publication.canonical_url, publication.publication_id, dict(publication.metadata)) for language in self.languages)
