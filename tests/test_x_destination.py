import asyncio
from types import SimpleNamespace

from core.editorial.channels import PublicationChannels
from core.publication.builder import PublicationBuilder
from core.renderers.x import XRenderer
from core.publishers.x import XPublisher


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
