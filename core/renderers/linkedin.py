from dataclasses import dataclass
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_tracked_public_url

@dataclass(frozen=True, slots=True)
class LinkedInPostView:
    text: str

class LinkedInRenderer:
    def __init__(self, public_base_url=DEFAULT_PUBLIC_BASE_URL): self.public_base_url = public_base_url
    def render(self, publication: Publication) -> LinkedInPostView:
        url = build_tracked_public_url(self.public_base_url, publication.article_id, "post", source="linkedin")
        title = str(publication.title or "").strip() or "AlphaLab AI"
        summary = str(publication.summary or "").strip()
        suffix = f"\n\nRead more: {url}"
        budget = max(1, 3000 - len(suffix))
        body = f"{title}\n\n{summary}" if summary else title
        if len(body) > budget: body = body[:max(1, budget - 1)].rstrip() + "…"
        return LinkedInPostView(body + suffix)
