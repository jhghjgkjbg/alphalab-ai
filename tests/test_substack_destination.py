import asyncio, json
from types import SimpleNamespace
from core.editorial.channels import PublicationChannels
from core.publication.builder import PublicationBuilder
from core.renderers.substack import SubstackRenderer
from core.publishers.substack import SubstackDraftPublisher

def pub(): return PublicationBuilder().build(SimpleNamespace(external_id="ss1", source="src", payload={"title":"<Title>","summary":"<Summary>","url":"https://source.example/a"}))

def test_substack_renderer_and_opt_in():
    assert "substack" not in PublicationChannels().enabled_destinations()
    assert "substack" in PublicationChannels(substack=True).enabled_destinations()
    view=SubstackRenderer("https://alphalabai.online/").render(pub())
    assert "&lt;Title&gt;" in view.body_html and "source.example" not in view.body_html
    assert view.canonical_url.endswith("/article/ss1") and "utm_source=substack" in view.tracked_url

def test_substack_atomic_draft_export_and_idempotency(tmp_path):
    view=SubstackRenderer().render(pub()); result=asyncio.run(SubstackDraftPublisher(tmp_path).publish(view))
    assert result.success and (tmp_path/"ss1"/"draft.html").exists() and (tmp_path/"ss1"/"metadata.json").exists()
    meta=json.loads((tmp_path/"ss1"/"metadata.json").read_text())
    assert meta["format_version"] == 1
    again=asyncio.run(SubstackDraftPublisher(tmp_path).publish(view)); assert again.success and again.external_id == result.external_id
