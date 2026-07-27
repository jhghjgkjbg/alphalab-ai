from dataclasses import dataclass
from html import escape
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_public_article_url, build_tracked_public_url

@dataclass(frozen=True, slots=True)
class MediumArticleView:
    title: str
    content_html: str
    canonical_url: str
    tags: tuple[str, ...]
    publish_status: str

class MediumRenderer:
    def __init__(self, public_base_url=DEFAULT_PUBLIC_BASE_URL, publish_status="draft"):
        self.public_base_url, self.publish_status = public_base_url, publish_status
    def render(self, publication: Publication) -> MediumArticleView:
        title = str(publication.title or "").strip() or "AlphaLab AI"
        summary = str(publication.summary or "").strip()
        variant = publication.variants.get("en") if publication.variants else None
        body = str(getattr(variant, "body", "") or "").strip()
        tracked = build_tracked_public_url(self.public_base_url, publication.article_id, "article", source="medium")
        content = f"<h1>{escape(title)}</h1>"
        if body and body != summary: content += f"\n<p>{escape(body)}</p>"
        content += f"\n<p>{escape(summary)}</p>\n<p><a href=\"{escape(tracked, quote=True)}\">Read the full article on AlphaLab AI</a></p>"
        raw_tags = publication.metadata.get("tags", publication.metadata.get("topics", ())) if isinstance(publication.metadata, dict) else ()
        tags=[]; seen=set()
        for tag in raw_tags or ():
            value=str(tag).strip()
            if value and value.casefold() not in seen: seen.add(value.casefold()); tags.append(value)
        return MediumArticleView(title, content, build_public_article_url(self.public_base_url, publication.article_id), tuple(tags[:5]), self.publish_status)
