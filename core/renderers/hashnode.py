from dataclasses import dataclass
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from core.publication.models import build_public_article_url
from core.publication.models import build_tracked_public_url

@dataclass(frozen=True)
class HashnodeArticleView:
    title: str
    content_markdown: str
    canonical_url: str
    tags: tuple[str, ...] = ()
    publish: bool = False
    publication_id: str = ""

class HashnodeRenderer:
    def __init__(self, public_base_url="https://alphalabai.online"):
        self.public_base_url = public_base_url
    def render(self, publication, *, publish=False, publication_id=""):
        title = re.sub(r"[`*_#<>]", "", str(getattr(publication, "title", "") or "")).strip() or "Untitled"
        summary = str(getattr(publication, "summary", "") or "").strip()
        body = str(getattr(publication, "body", "") or "").strip()
        if not body:
            metadata = getattr(publication, "metadata", {}) or {}
            body = str(metadata.get("body", "") or metadata.get("content", "") or "").strip()
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"!\[[^]]*\]\([^)]*\)", "", body)
        content = f"# {title}\n\n{summary}"
        if body and body != summary: content += f"\n\n{body}"
        url = build_public_article_url(self.public_base_url, getattr(publication, "article_id", ""))
        tracked = build_tracked_public_url(self.public_base_url, getattr(publication, "article_id", ""), "article", source="hashnode")
        parts = urlsplit(tracked); query = dict(parse_qsl(parts.query)); query["utm_medium"] = "referral"
        tracked = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        content += f"\n\n---\n\n[Read the full article on AlphaLab AI]({tracked})"
        return HashnodeArticleView(title, content, url, (), bool(publish), str(publication_id or ""))
