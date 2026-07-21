from dataclasses import dataclass
from types import MappingProxyType
from core.publication.models import Publication
@dataclass(frozen=True, slots=True)
class TelegramView:
    title: str; text: str; buttons: tuple; metadata: object; language: str
class TelegramRenderer:
    def __init__(self, language=None): self.language=language
    def render(self, publication: Publication) -> TelegramView:
        v=publication.variants.get(self.language) if self.language else None; title=v.title if v else publication.title; summary=v.summary if v else publication.summary
        text=f"{title}\n\n{summary}\n\n{publication.url}".strip()
        return TelegramView(title,text,(publication.url,),MappingProxyType(dict(publication.metadata)),self.language or publication.language)
