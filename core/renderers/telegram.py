from dataclasses import dataclass
from types import MappingProxyType
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_tracked_public_url
@dataclass(frozen=True, slots=True)
class TelegramView:
    title: str; text: str; buttons: tuple; metadata: object; language: str
class TelegramRenderer:
    def __init__(self, language=None, public_base_url=DEFAULT_PUBLIC_BASE_URL): self.language=language; self.public_base_url=public_base_url
    def render(self, publication: Publication) -> TelegramView:
        v=publication.variants.get(self.language) if self.language else None; title=v.title if v else publication.title; summary=v.summary if v else publication.summary
        language = self.language or publication.language
        public_url = build_tracked_public_url(self.public_base_url, publication.article_id, language)
        text=f"{title}\n\n{summary}\n\n{public_url}".strip()
        return TelegramView(title,text,(public_url,),MappingProxyType(dict(publication.metadata)),language)
