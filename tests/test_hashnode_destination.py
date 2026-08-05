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
    assert result.mutation_name == "createDraft"
    assert len(calls) == 1
    payload = calls[0][1]
    assert "createDraft" in payload["query"] and "publishPost" not in payload["query"]
    assert payload["variables"]["input"]["title"] == "A title"
    assert "PAT" not in repr(payload)

def test_publish_request_and_graphql_errors_fail(capsys):
    calls = []
    class Response:
        status_code = 200
        def json(self): return {"errors": [{"message": "forbidden", "extensions": {"code": "FORBIDDEN"}, "path": ["publishPost", "post"]}]}
    async def request(*args): calls.append(args); return Response()
    result = asyncio.run(HashnodePublisher("PAT", "pub", request, publish=True).publish(HashnodeRenderer().render(article())))
    assert not result.success and result.external_id is None
    assert result.failure_kind == "graphql"
    assert result.graphql_error_codes == ("FORBIDDEN",)
    output = capsys.readouterr().out
    assert "hashnode_graphql_code=FORBIDDEN" in output
    assert "hashnode_graphql_path=publishPost.post" in output
    assert "hashnode_graphql_category=authorization" in output
    assert "forbidden" not in output and "PAT" not in output
    assert len(calls) == 1 and "publishPost" in calls[0][1]["query"]

def test_missing_configuration_skips_http():
    called = False
    async def request(*args):
        nonlocal called; called = True
    result = asyncio.run(HashnodePublisher("", "", request).publish(HashnodeRenderer().render(article())))
    assert not result.success and result.failure_kind == "hashnode_config_missing" and not called and "PAT" not in repr(result)

def test_missing_mutation_path_and_id_are_safe_failures():
    class Response:
        status_code = 200
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload
    async def request(*args): return Response({"data": {"publishPost": None}})
    result = asyncio.run(HashnodePublisher("PAT", "pub", request, publish=True).publish(HashnodeRenderer().render(article())))
    assert not result.success and result.failure_kind == "missing_response_path"

    async def request_without_id(*args): return Response({"data": {"publishPost": {"post": {"id": ""}}}})
    result = asyncio.run(HashnodePublisher("PAT", "pub", request_without_id, publish=True).publish(HashnodeRenderer().render(article())))
    assert not result.success and result.failure_kind == "missing_response_id"

def test_invalid_endpoint_is_blocked_before_http():
    called = False
    async def request(*args):
        nonlocal called
        called = True
    result = asyncio.run(HashnodePublisher("PAT", "pub", request, api_url="not-a-url").publish(HashnodeRenderer().render(article())))
    assert not result.success and result.failure_kind == "hashnode_config_missing" and not called

def test_graphql_error_categories_are_symbolic_and_safe(capsys):
    class Response:
        status_code = 200
        def __init__(self, message): self.message = message
        def json(self): return {"errors": [{"message": self.message}]}
    messages = {
        "authentication failed": "authentication",
        "publication not found": "publication_not_found",
        "invalid input": "invalid_input",
        "validation failed": "validation",
        "unexpected backend detail": "unknown_graphql",
    }
    for message, category in messages.items():
        async def request(*args, _message=message): return Response(_message)
        result = asyncio.run(HashnodePublisher("secret-token", "private-publication", request).publish(HashnodeRenderer().render(article())))
        assert not result.success and result.failure_kind == "graphql"
        output = capsys.readouterr().out
        assert f"hashnode_graphql_category={category}" in output
        assert message not in output
        assert "secret-token" not in output and "private-publication" not in output
