import asyncio
from types import SimpleNamespace
from core.editorial.channels import PublicationChannels
from core.publication.builder import PublicationBuilder
from core.renderers.medium import MediumRenderer
from core.publishers.medium import MediumPublisher

def pub():
    return PublicationBuilder().build(SimpleNamespace(external_id="m1", source="src", payload={"title":"<Title>", "summary":"<Summary>", "url":"https://source.example/a", "tags":[" AI ","ai","News"]}))

def test_medium_opt_in_renderer_escape_canonical_and_tags():
    assert "medium" not in PublicationChannels().enabled_destinations()
    assert "medium" in PublicationChannels(medium=True).enabled_destinations()
    view=MediumRenderer("https://alphalabai.online/").render(pub())
    assert "&lt;Title&gt;" in view.content_html and "&lt;Summary&gt;" in view.content_html
    assert "utm_source=medium" in view.content_html and "source.example" not in view.content_html
    assert view.canonical_url == "https://alphalabai.online/article/m1"
    assert view.tags == ("AI", "News")

def test_medium_publisher_payload_and_external_id():
    calls=[]
    async def request(url,payload,timeout,headers):
        calls.append((url,payload,headers)); return SimpleNamespace(status_code=201, json=lambda:{"data":{"id":"medium-1"}})
    view=MediumRenderer().render(pub())
    result=asyncio.run(MediumPublisher("token","author",request).publish(view))
    assert result.success and result.external_id == "medium-1"
    assert calls[0][0].endswith("/v1/users/author/posts") and calls[0][1]["contentFormat"] == "html"
