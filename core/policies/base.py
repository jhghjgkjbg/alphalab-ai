from typing import Protocol
from core.publication.models import LanguageVariant
class ChannelPolicy(Protocol):
    def apply(self, variant: LanguageVariant) -> LanguageVariant: ...
