import asyncio
from types import SimpleNamespace
from core.editorial.channels import PublicationChannels
from core.publication.builder import PublicationBuilder
from core.renderers.devto import DevToRenderer
from core.publishers.devto import DevToPublisher

def pub(): return PublicationBuilder().build(SimpleNamespace(external_id="d1", source="src", payload={"title":"Title","summary":"Summary","url":"https://source.example/a","tags":[" AI ","ai","Bad Tag!"]}))

def test_devto_opt_in_and_renderer():
    assert "devto" not in PublicationChannels().enabled_destinations()
    assert "devto" in PublicationChannels(devto=True).enabled_destinations()
    view=DevToRenderer("https://alphalabai.online/",published=False).render(pub())
    assert "source.example" not in view.body_markdown and "utm_source=devto" in view.body_markdown
    assert view.canonical_url.endswith("/article/d1") and view.tags == ("ai",)

def test_devto_publisher_request_and_id():
    calls=[]
    async def request(url,payload,timeout,headers):
        calls.append((url,payload,headers)); return SimpleNamespace(status_code=201,json=lambda:{"id":123})
    result=asyncio.run(DevToPublisher("key",request).publish(DevToRenderer().render(pub())))
    assert result.success and result.external_id == "123"
    assert calls[0][0].endswith("/api/articles") and calls[0][1]["article"]["published"] is False
