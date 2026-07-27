from core.publication.models import build_public_article_url, build_tracked_public_url
from core.renderers.telegram import TelegramRenderer
from core.renderers.website import WebsiteRenderer
from core.publication.builder import PublicationBuilder
from types import SimpleNamespace


def publication():
    return PublicationBuilder().build(SimpleNamespace(external_id="a/1", source="src", payload={"title":"T", "summary":"S", "url":"https://source.example/item?x=1"}))


def test_public_url_and_tracking_are_deterministic():
    assert build_public_article_url("https://alphalabai.online/", "a/1") == "https://alphalabai.online/article/a%2F1"
    url = build_tracked_public_url("https://alphalabai.online/", "a", "en")
    assert url.count("utm_content=en") == 1
    assert "utm_source=telegram" in url and "utm_medium=social" in url and "utm_campaign=content_distribution" in url
    tracked = build_tracked_public_url("https://alphalabai.online/feed?x=1#top", "a", "ru")
    assert "x=1" in tracked and tracked.endswith("#top")


def test_telegram_uses_public_url_and_website_keeps_source():
    pub = publication()
    en = TelegramRenderer("en", "https://alphalabai.online/").render(pub)
    ru = TelegramRenderer("ru", "https://alphalabai.online/").render(pub)
    website = WebsiteRenderer("en").render(pub)
    assert "https://alphalabai.online/article/a%2F1" in en.text
    assert "utm_content=en" in en.text
    assert "utm_content=ru" in ru.text
    assert "source.example" not in en.text and "source.example" not in ru.text
    assert website.url == pub.url
    assert pub.canonical_url.startswith("https://source.example")
