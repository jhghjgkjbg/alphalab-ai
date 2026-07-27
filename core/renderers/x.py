from dataclasses import dataclass
from core.publication.models import Publication, DEFAULT_PUBLIC_BASE_URL, build_tracked_public_url

@dataclass(frozen=True, slots=True)
class XPostView:
    text: str

class XRenderer:
    def __init__(self, public_base_url=DEFAULT_PUBLIC_BASE_URL):
        self.public_base_url = public_base_url

    def render(self, publication: Publication) -> XPostView:
        url = build_tracked_public_url(self.public_base_url, publication.article_id, "post")
        title = str(publication.title or "").strip() or "AlphaLab AI"
        summary = str(publication.summary or "").strip()
        suffix = f"\n\n{url}"
        available = max(0, 280 - len(suffix))
        if len(title) + len(summary) + 2 <= available:
            body = f"{title}\n\n{summary}" if summary else title
        else:
            title = title[:available].rstrip() + "…"
            body = title
            if summary:
                title_budget = max(1, available - len(summary) - 2)
                title = title[:title_budget].rstrip() + "…"
                body = f"{title}\n\n{summary[:max(0, available-len(title)-2)].rstrip()}…"
        text = f"{body}{suffix}"
        if len(text) > 280:
            budget = max(1, 280 - len(suffix))
            text = f"{body[:budget-1].rstrip()}…{suffix}"
        return XPostView(text)
