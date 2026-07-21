from core.publication.models import LanguageVariant
class WebsitePolicy:
    def apply(self, variant: LanguageVariant) -> LanguageVariant: return variant
