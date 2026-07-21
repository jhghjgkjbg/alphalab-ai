from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PublicationChannels:
    website: bool = True
    telegram_en: bool = False
    telegram_ru: bool = False


class ChannelSelector:
    def explain(self, priority, window=None, audience=None, angle=None, language="en", category="", ai_succeeded=False, has_ru_variant=False):
        level = getattr(priority, "level", "normal")
        english = str(language or "en").casefold() in ("en", "english")
        ai_news = str(category or "").casefold() in ("ai", "llm", "research", "machine learning")
        ru_ok = english and has_ru_variant and (ai_news or ai_succeeded)
        if ru_ok:
            ru_reason = "ai_enriched_variant_eligible"
        elif not english:
            ru_reason = "language_ineligible"
        elif not has_ru_variant:
            ru_reason = "missing_ru_variant"
        elif not ai_succeeded:
            ru_reason = "ai_enrichment_required"
        else:
            ru_reason = "policy_excluded"
        return {"language": language, "audience": getattr(audience, "audience", ""), "priority": level, "window": getattr(window, "selected", ""), "website_reason": "website_default", "telegram_en_reason": "english_eligible" if english else "language_ineligible", "telegram_ru_reason": ru_reason}

    def select(self, priority, window=None, audience=None, angle=None, language="en", category="", ai_succeeded=False, has_ru_variant=False) -> PublicationChannels:
        level = getattr(priority, "level", "normal")
        english = str(language or "en").casefold() in ("en", "english")
        ai_news = str(category or "").casefold() in ("ai", "llm", "research", "machine learning")
        ru_eligible = english and has_ru_variant and (ai_news or ai_succeeded)
        if level == "breaking":
            return PublicationChannels(True, english, ru_eligible)
        if level == "high":
            return PublicationChannels(True, english, ru_eligible)
        return PublicationChannels(True, english, ru_eligible)

    def apply(self, publication, priority, **kwargs):
        return replace(publication, channels=self.select(priority, **kwargs))
