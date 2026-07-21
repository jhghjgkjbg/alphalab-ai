from typing import Protocol, TypeVar
from core.publication.models import Publication
T=TypeVar("T")
class PublicationRenderer(Protocol[T]):
    def render(self, publication: Publication) -> T: ...
