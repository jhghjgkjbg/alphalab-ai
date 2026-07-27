import json, os, tempfile, shutil
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

class RedditDraftPublisher:
    def __init__(self, outbox_directory, subreddit="", post_kind="self", include_tracking=False, require_manual_rule_review=True):
        self.outbox=Path(outbox_directory); self.subreddit=subreddit; self.post_kind=post_kind; self.include_tracking=include_tracking; self.require_manual_rule_review=require_manual_rule_review
    async def publish(self, view):
        final=self.outbox/view.article_id/view.subreddit; final.parent.mkdir(parents=True,exist_ok=True)
        metadata={"article_id":view.article_id,"destination":"reddit","subreddit":view.subreddit,"post_kind":view.post_kind,"title":view.title,"canonical_url":view.canonical_url,"submission_url":view.tracked_url or view.url,"tracking_enabled":bool(view.tracked_url and view.tracked_url!=view.canonical_url),"manual_rule_review_required":True,"remote_publication_performed":False,"created_at":datetime.now(timezone.utc).isoformat(),"format_version":1}
        if final.exists():
            if (final/"metadata.json").exists() and (final/"submission.md").exists():
                try:
                    existing=json.loads((final/"metadata.json").read_text(encoding="utf-8"))
                    expected={"article_id":view.article_id,"subreddit":view.subreddit,"post_kind":view.post_kind,"title":view.title,"canonical_url":view.canonical_url}
                    if any(existing.get(k) != v for k,v in expected.items()): return SimpleNamespace(success=False,external_id=None,error="reddit_outbox_conflict")
                    if existing.get("format_version") != 1: return SimpleNamespace(success=False,external_id=None,error="reddit_invalid_existing_draft")
                    return SimpleNamespace(success=True,external_id=str(final),error=None,delivery_mode="draft_export")
                except Exception: return SimpleNamespace(success=False,external_id=None,error="reddit_invalid_existing_draft")
            return SimpleNamespace(success=False,external_id=None,error="reddit_invalid_existing_draft")
        tmp=Path(tempfile.mkdtemp(prefix=".reddit-",dir=str(final.parent)))
        try:
            text=f"# Title\n\n{view.title}\n\n# Subreddit\n\nr/{view.subreddit}\n\n# Post kind\n\n{view.post_kind}\n\n"
            text += ("# Body\n\n"+view.body_markdown if view.post_kind=="self" else "# URL\n\n"+str(view.url))
            (tmp/"submission.md").write_text(text,encoding="utf-8"); (tmp/"metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8"); os.replace(tmp,final)
            return SimpleNamespace(success=True,external_id=str(final),error=None,delivery_mode="draft_export")
        except Exception:
            shutil.rmtree(tmp,ignore_errors=True); return SimpleNamespace(success=False,external_id=None,error="reddit_outbox_write_failed")
