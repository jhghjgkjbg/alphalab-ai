import asyncio
from types import SimpleNamespace
from core.editorial.channels import PublicationChannels
from core.publication.builder import PublicationBuilder
from core.renderers.linkedin import LinkedInRenderer
from core.publishers.linkedin import LinkedInPublisher

def pub():
    return PublicationBuilder().build(SimpleNamespace(external_id="li1", source="src", payload={"title":"Title", "summary":"Summary", "url":"https://source.example/a"}))

def test_linkedin_opt_in_and_rendering():
    assert "linkedin" not in PublicationChannels().enabled_destinations()
    assert "linkedin" in PublicationChannels(linkedin=True).enabled_destinations()
    view = LinkedInRenderer("https://alphalabai.online/").render(pub())
    assert "Read more: https://alphalabai.online/article/li1" in view.text
    assert "utm_source=linkedin" in view.text and "source.example" not in view.text
    assert len(view.text) <= 3000

def test_linkedin_publisher_headers_payload_and_id():
    calls=[]
    async def request(url, payload, timeout, headers):
        calls.append((url,payload,headers)); return SimpleNamespace(status_code=201, headers={"x-restli-id":"post-1"})
    result = asyncio.run(LinkedInPublisher("token", "urn:li:person:1", request).publish(SimpleNamespace(text="hello")))
    assert result.success and result.external_id == "post-1"
    assert calls[0][0].endswith("/rest/posts") and calls[0][1]["visibility"] == "PUBLIC"
    assert calls[0][2]["LinkedIn-Version"] == "202601"
