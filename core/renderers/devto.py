from dataclasses import dataclass
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_public_article_url, build_tracked_public_url

@dataclass(frozen=True, slots=True)
class DevToArticleView:
    title: str; body_markdown: str; canonical_url: str; tags: tuple[str, ...]; published: bool; organization_id: int | None

class DevToRenderer:
    def __init__(self, public_base_url=DEFAULT_PUBLIC_BASE_URL, published=False, organization_id=None): self.public_base_url,self.published,self.organization_id=public_base_url,published,organization_id
    def render(self, publication: Publication) -> DevToArticleView:
        title=str(publication.title or "").strip() or "AlphaLab AI"; summary=str(publication.summary or "").strip(); variant=publication.variants.get("en") if publication.variants else None; body=str(getattr(variant,"body","") or "").strip() or summary
        tracked=build_tracked_public_url(self.public_base_url, publication.article_id, "article", source="devto"); markdown=f"# {title.replace('#','')}\n\n{summary}\n\n{body}\n\n---\n\n[Read the full article on AlphaLab AI]({tracked})"
        raw=publication.metadata.get("tags", publication.metadata.get("topics", ())) if isinstance(publication.metadata,dict) else (); tags=[]; seen=set()
        for tag in raw or ():
            value=str(tag).strip().lower().replace(" ","")
            if value and len(value)<=30 and value.replace("-","").replace("_","").isalnum() and value not in seen: seen.add(value); tags.append(value)
        return DevToArticleView(title,markdown,build_public_article_url(self.public_base_url,publication.article_id),tuple(tags[:4]),self.published,self.organization_id)
