from dataclasses import dataclass, field
@dataclass(frozen=True, slots=True)
class AIContext:
    keywords: tuple[str,...]=()
    entities: tuple[str,...]=()
    topics: tuple[str,...]=()
    summary_version: str=""
    translation_status: str=""
    en_title: str=""; en_body: str=""; ru_title: str=""; ru_body: str=""
    editor_notes: str=""
    confidence: float=0.0
    headline_suggestions: tuple[str,...]=()
    seo_keywords: tuple[str,...]=()
    hashtags: tuple[str,...]=()
    category_guess: str=""
    short_summary: str=""
    long_summary: str=""
    translation: str=""
