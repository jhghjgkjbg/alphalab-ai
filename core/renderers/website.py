from dataclasses import dataclass
from core.publication.models import Publication
@dataclass(frozen=True, slots=True)
class WebsiteView:
    title: str; summary: str; source: str; category: str; language: str; published_at: str; score: float; url: str; why_this_matters: str = ""; target_audience: str = ""; body: str = ""
class WebsiteRenderer:
    def __init__(self, language=None): self.language=language
    def render(self, publication: Publication) -> WebsiteView:
        v=publication.variants.get(self.language) if self.language else None
        return WebsiteView(v.title if v else publication.title,v.summary if v else publication.summary,publication.source,publication.category,self.language or publication.language,publication.published_at,publication.score,publication.url,publication.why_this_matters,publication.target_audience,body=(v.body if v else "") or (v.summary if v else publication.summary))
