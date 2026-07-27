from dataclasses import dataclass
from html import escape
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_public_article_url, build_tracked_public_url

@dataclass(frozen=True, slots=True)
class SubstackDraftView:
    article_id: str; title: str; subtitle: str; body_html: str; canonical_url: str; tracked_url: str; audience: str; metadata: dict

class SubstackRenderer:
    def __init__(self, public_base_url=DEFAULT_PUBLIC_BASE_URL, audience="everyone", publication_url=""):
        self.public_base_url, self.audience, self.publication_url = public_base_url, audience, publication_url
    def render(self, publication: Publication) -> SubstackDraftView:
        title = str(publication.title or "").strip() or "AlphaLab AI"
        summary = str(publication.summary or "").strip()
        variant = publication.variants.get("en") if publication.variants else None
        body = str(getattr(variant, "body", "") or "").strip() or summary
        tracked = build_tracked_public_url(self.public_base_url, publication.article_id, "article", source="substack")
        html = f"<h1>{escape(title)}</h1>\n<p><strong>{escape(summary)}</strong></p>\n<p>{escape(body)}</p>\n<hr>\n<p><a href=\"{escape(tracked, quote=True)}\">Read the original AlphaLab AI article</a></p>"
        canonical = build_public_article_url(self.public_base_url, publication.article_id)
        return SubstackDraftView(str(publication.article_id), title, summary, html, canonical, tracked, self.audience, {"publication_url": self.publication_url})
