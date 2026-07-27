import asyncio
from types import SimpleNamespace
from core.editorial.channels import PublicationChannels
from core.publishers.hashnode import HashnodePublisher
from core.renderers.hashnode import HashnodeRenderer

def article(**kw):
    base = dict(article_id="a1", title="A *title*", summary="Summary", url="https://source.example/a", metadata={})
    base.update(kw)
    return SimpleNamespace(**base)

def test_opt_in_and_renderer_contract():
    assert "hashnode" not in PublicationChannels().enabled_destinations()
    assert "hashnode" in PublicationChannels(hashnode=True).enabled_destinations()
    view = HashnodeRenderer().render(article(metadata={"body": "<p>Body</p> ![x](image.png)"}))
    assert view.title and view.content_markdown
    assert "source.example" not in view.content_markdown
    assert "<p>" not in view.content_markdown and "![" not in view.content_markdown
    assert "utm_source=hashnode" in view.content_markdown
    assert "utm_medium=referral" in view.content_markdown

def test_draft_request_and_external_id():
    calls = []
    class Response:
        status_code = 200
        def json(self): return {"data": {"createDraft": {"draft": {"id": 42}}}}
    async def request(*args): calls.append(args); return Response()
    result = asyncio.run(HashnodePublisher("PAT", "pub", request, publish=False).publish(HashnodeRenderer().render(article())))
    assert result.success and result.external_id == "42"
    assert len(calls) == 1
    payload = calls[0][1]
    assert "createDraft" in payload["query"] and "publishPost" not in payload["query"]
    assert payload["variables"]["input"]["title"] == "A title"
    assert "PAT" not in repr(payload)

def test_publish_request_and_graphql_errors_fail():
    calls = []
    class Response:
        status_code = 200
        def json(self): return {"errors": [{"message": "forbidden"}]}
    async def request(*args): calls.append(args); return Response()
    result = asyncio.run(HashnodePublisher("PAT", "pub", request, publish=True).publish(HashnodeRenderer().render(article())))
    assert not result.success and result.external_id is None
    assert len(calls) == 1 and "publishPost" in calls[0][1]["query"]

def test_missing_configuration_skips_http():
    called = False
    async def request(*args):
        nonlocal called; called = True
    result = asyncio.run(HashnodePublisher("", "", request).publish(HashnodeRenderer().render(article())))
    assert not result.success and not called and "PAT" not in repr(result)
