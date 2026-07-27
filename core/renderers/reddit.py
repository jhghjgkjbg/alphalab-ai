from dataclasses import dataclass
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from core.publication.models import build_public_article_url, build_tracked_public_url

@dataclass(frozen=True)
class RedditDraftView:
    article_id: str; subreddit: str; post_kind: str; title: str; body_markdown: str
    url: str | None; canonical_url: str; tracked_url: str | None; metadata: dict

def normalize_subreddit(value):
    raw = str(value or "").strip()
    if raw.startswith("/r/"): raw = raw[3:]
    elif raw.startswith("r/"): raw = raw[2:]
    if not raw or len(raw) > 21 or not re.fullmatch(r"[A-Za-z0-9_]+", raw): raise ValueError("reddit_invalid_subreddit")
    return raw

class RedditRenderer:
    def __init__(self, public_base_url, subreddit, post_kind="self", include_tracking=False, require_manual_rule_review=True):
        self.base, self.subreddit = public_base_url, normalize_subreddit(subreddit)
        if post_kind not in {"self", "link"}: raise ValueError("reddit_invalid_post_kind")
        self.kind, self.tracking, self.manual = post_kind, include_tracking, require_manual_rule_review
    def render(self, publication):
        title = re.sub(r"\s+", " ", str(getattr(publication, "title", "") or "").replace("\n", " ")).strip()[:300]
        if not title: raise ValueError("reddit_empty_title")
        article_id = str(getattr(publication, "article_id", "")); clean = build_public_article_url(self.base, article_id)
        tracked = clean
        if self.tracking:
            tracked = build_tracked_public_url(self.base, article_id, self.subreddit.lower(), source="reddit")
            p=urlsplit(tracked); q=dict(parse_qsl(p.query)); q["utm_medium"]="community"; q["utm_content"]=self.subreddit.lower(); tracked=urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),p.fragment))
        if self.kind == "link": body = ""; url = tracked
        else:
            summary = str(getattr(publication, "summary", "") or "").strip(); meta=getattr(publication,"metadata",{}) or {}; body_text=str(meta.get("body","") or meta.get("content","")).strip(); body_text=re.sub(r"<[^>]+>","",body_text)[:40000]
            body = "\n\n".join(x for x in (summary, body_text, "---", f"Read the full article on AlphaLab AI: {tracked}") if x)
            if not body: raise ValueError("reddit_empty_body")
            url = None
        return RedditDraftView(article_id,self.subreddit,self.kind,title,body,url,clean,tracked,{"manual_rule_review_required":self.manual,"remote_publication_performed":False})
