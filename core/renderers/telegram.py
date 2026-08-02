from dataclasses import dataclass
from types import MappingProxyType
import re
from urllib.parse import urlsplit
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_tracked_public_url
@dataclass(frozen=True, slots=True)
class TelegramView:
    title: str; text: str; buttons: tuple; metadata: object; language: str
class TelegramRenderer:
    def __init__(self, language=None, public_base_url=DEFAULT_PUBLIC_BASE_URL): self.language=language; self.public_base_url=public_base_url
    def render(self, publication: Publication) -> TelegramView:
        v=publication.variants.get(self.language) if self.language else None; title=(v.title if v else publication.title).strip(); summary=v.summary if v else publication.summary
        language = self.language or publication.language
        public_url = build_tracked_public_url(self.public_base_url, publication.article_id, language)
        label_read = "🔗 Read on AlphaLab" if language == "en" else "🔗 Читать на AlphaLab"
        label_source = "🌍 Original source" if language == "en" else "🌍 Оригинальный источник"
        source = str(getattr(publication, "url", "") or "").strip()
        source_valid = urlsplit(source).scheme in {"http", "https"} and bool(urlsplit(source).netloc)
        suffix = f"\n\n{label_read}\n{public_url}" + (f"\n\n{label_source}\n{source}" if source_valid else "")
        summary = self._summary(summary, 4096 - len(title) - len(suffix) - 4)
        blocks = [title, summary, suffix.strip()]
        text="\n\n".join(block for block in blocks if block).strip()
        return TelegramView(title,text,(public_url,),MappingProxyType(dict(publication.metadata)),language)

    @staticmethod
    def _summary(value, limit):
        text = "\n\n".join(" ".join(part.split()) for part in str(value or "").split("\n\n") if part.strip())
        if not text or limit <= 0:
            return ""
        if len(text) <= limit:
            return text
        candidate = text[:limit].rsplit(" ", 1)[0].rstrip()
        sentence = re.search(r"^(.+[.!?])(?:\s|$)", candidate)
        if sentence:
            candidate = sentence.group(1).rstrip()
        return candidate
