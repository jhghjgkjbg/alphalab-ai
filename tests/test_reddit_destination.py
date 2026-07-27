import asyncio
import json
import pytest
from types import SimpleNamespace
from core.editorial.channels import PublicationChannels
from core.renderers.reddit import RedditRenderer, normalize_subreddit
from core.publishers.reddit import RedditDraftPublisher

def article(**kw):
    data=dict(article_id="r1", title="Title\nHere", summary="Summary", metadata={"body":"<p>Body</p>"}); data.update(kw); return SimpleNamespace(**data)
def test_opt_in_and_normalization():
    assert "reddit" not in PublicationChannels().enabled_destinations()
    assert "reddit" in PublicationChannels(reddit=True).enabled_destinations()
    assert normalize_subreddit("/r/MachineLearning") == "MachineLearning"
    for value in ("", "   ", "https://reddit.com/r/x", "reddit.com/r/x", "r/", "/r/", "bad name", "bad/name", "bad-name", "тест", "a"*22):
        with pytest.raises(ValueError, match="reddit_invalid_subreddit"):
            normalize_subreddit(value)
def test_renderer_self_and_link():
    view=RedditRenderer("https://alphalabai.online","r/MachineLearning").render(article())
    assert view.subreddit == "MachineLearning" and "source URL" not in view.body_markdown
    link=RedditRenderer("https://alphalabai.online","MachineLearning","link").render(article())
    assert link.body_markdown == "" and link.url.startswith("https://alphalabai.online/article/")
    tracked=RedditRenderer("https://alphalabai.online","MachineLearning",include_tracking=True).render(article())
    assert "utm_source=reddit" in tracked.tracked_url and "utm_medium=community" in tracked.tracked_url and "utm_content=machinelearning" in tracked.tracked_url
    assert "utm_" not in view.tracked_url
    with pytest.raises(ValueError, match="reddit_invalid_post_kind"):
        RedditRenderer("https://alphalabai.online","MachineLearning","bad")
    with pytest.raises(ValueError, match="reddit_empty_title"):
        RedditRenderer("https://alphalabai.online","MachineLearning").render(article(title=""))
def test_outbox_export_idempotent(tmp_path):
    pub=RedditDraftPublisher(tmp_path)
    view=RedditRenderer("https://alphalabai.online","MachineLearning").render(article())
    first=asyncio.run(pub.publish(view)); second=asyncio.run(pub.publish(view))
    assert first.success and second.success and (tmp_path/"r1"/"MachineLearning"/"metadata.json").exists()
    meta=json.loads((tmp_path/"r1"/"MachineLearning"/"metadata.json").read_text())
    assert meta["format_version"] == 1 and meta["remote_publication_performed"] is False and "source.example" not in json.dumps(meta)

def test_corrupt_and_conflicting_drafts_are_rejected(tmp_path):
    pub=RedditDraftPublisher(tmp_path); view=RedditRenderer("https://alphalabai.online","MachineLearning").render(article())
    final=tmp_path/"r1"/"MachineLearning"; final.mkdir(parents=True); (final/"metadata.json").write_text("bad")
    result=asyncio.run(pub.publish(view)); assert not result.success and result.error == "reddit_invalid_existing_draft"
    (final/"metadata.json").write_text(json.dumps({"format_version":1,"article_id":"other","subreddit":"MachineLearning","post_kind":"self","title":"Other","canonical_url":"x"})); (final/"submission.md").write_text("x")
    result=asyncio.run(pub.publish(view)); assert not result.success and result.error == "reddit_outbox_conflict"
