import asyncio
from types import SimpleNamespace

from core.editorial.channels import PublicationChannels
from core.publication.builder import PublicationBuilder
from core.renderers.x import XRenderer
from core.publishers.x import XPublisher, XOAuthTokenProvider
from core.credentials.x_token_store import XTokenState, XTokenStore


def pub(title="Title", summary="Summary"):
    return PublicationBuilder().build(SimpleNamespace(external_id="x1", source="source", payload={"title": title, "summary": summary, "url": "https://source.example/a"}))


def test_x_channel_is_opt_in():
    assert "x" not in PublicationChannels().enabled_destinations()
    assert "x" in PublicationChannels(x=True).enabled_destinations()


def test_x_renderer_preserves_url_and_limit():
    view = XRenderer("https://alphalabai.online/").render(pub("T" * 200, "S" * 300))
    assert len(view.text) <= 280
    assert "https://alphalabai.online/article/x1" in view.text
    assert "utm_content=post" in view.text


def test_x_publisher_maps_success_and_errors_without_network():
    calls = []
    async def request(url, payload, timeout, headers):
        calls.append((url, payload, headers)); return SimpleNamespace(status_code=201, json=lambda: {"data": {"id": "tweet-1"}})
    result = asyncio.run(XPublisher("secret", request).publish(SimpleNamespace(text="hello")))
    assert result.success and result.external_id == "tweet-1"
    assert calls[0][0].endswith("/2/tweets") and calls[0][1] == {"text": "hello"}

def test_x_oauth_refresh_rotates_tokens_without_logging_secrets():
    calls = []
    async def request(url, payload, timeout, headers):
        calls.append((url, payload, headers))
        return SimpleNamespace(status_code=200, json=lambda: {"access_token": "new-access", "refresh_token": "new-refresh"})
    saved = []
    provider = XOAuthTokenProvider("old", "refresh", "client", request=request, persist=lambda a, r: saved.append((a, r)))
    result = asyncio.run(provider.refresh_access_token())
    assert result.success and provider.access_token == "new-access" and provider.refresh_token == "new-refresh"
    assert saved == [("new-access", "new-refresh")] and "old" not in repr(calls)

def test_x_publisher_refreshes_once_after_401():
    calls = []
    async def request(url, payload, timeout, headers):
        calls.append(headers["Authorization"])
        if len(calls) == 1:
            return SimpleNamespace(status_code=401, json=lambda: {})
        return SimpleNamespace(status_code=201, json=lambda: {"data": {"id": "tweet-2"}})
    async def refresh():
        provider.access_token = "new"
        return SimpleNamespace(success=True)
    provider = XOAuthTokenProvider("old", "refresh", "client", request=lambda *a: None)
    provider.refresh_access_token = refresh
    result = asyncio.run(XPublisher("", request, token_provider=provider).publish(SimpleNamespace(text="hello")))
    assert result.success and calls == ["Bearer old", "Bearer new"]

def test_x_token_store_atomic_round_trip(tmp_path):
    path = tmp_path / "secrets" / "x.json"
    store = XTokenStore(path)
    store.save(XTokenState("access", "refresh"))
    loaded = store.load()
    assert loaded.access_token == "access" and loaded.refresh_token == "refresh"
    if __import__("os").name != "nt":
        assert (path.stat().st_mode & 0o077) == 0

def test_x_token_store_rejects_invalid_state(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")
    try:
        XTokenStore(path).load()
    except RuntimeError as exc:
        assert str(exc) == "x_token_state_invalid"
    else:
        raise AssertionError("invalid state accepted")
