from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SEOProfile:
    seo_title: str
    meta_description: str
    focus_keywords: tuple[str, ...]
    canonical_slug: str
    og_title: str
    og_description: str
    twitter_title: str
    twitter_description: str


class SEOEditor:
    def edit(self, publication, facts=None, angle=None, audience=None) -> SEOProfile:
        title = " ".join(str(getattr(publication, "title", "") or "").split()) or "AI Scout article"
        summary = " ".join(str(getattr(publication, "summary", "") or "").split()) or title
        seo_title = title[:60]
        description = summary[:160]
        words = re.findall(r"[A-Za-zА-Яа-я0-9]{3,}", title.casefold())
        keywords = tuple(dict.fromkeys(words))[:8]
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold().encode("ascii", "ignore").decode()).strip("-") or "ai-scout-article"
        return SEOProfile(seo_title, description, keywords, slug, seo_title, description, seo_title, description)
