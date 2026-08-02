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
    assert "source.example" in en.text and "source.example" in ru.text
    assert "🔗 Read on AlphaLab" in en.text
    assert "🌍 Original source" in en.text
    assert "🔗 Читать на AlphaLab" in ru.text
    assert "🌍 Оригинальный источник" in ru.text
    assert website.url == pub.url
    assert pub.canonical_url.startswith("https://source.example")


def test_telegram_summary_format_and_safe_limit():
    pub = PublicationBuilder().build(SimpleNamespace(external_id="long", source="src", payload={"title": "Headline", "summary": "First paragraph.\n\nSecond paragraph with enough detail.\n\nThird paragraph.", "url": ""}))
    text = TelegramRenderer("en", "https://alphalabai.online").render(pub).text
    assert "First paragraph.\n\nSecond paragraph" in text
    assert "Original source" not in text
    assert len(text) <= 4096


def test_telegram_long_summary_does_not_cut_sentence():
    summary = ("A complete sentence. " * 400).strip()
    pub = PublicationBuilder().build(SimpleNamespace(external_id="long", source="src", payload={"title": "Headline", "summary": summary, "url": "https://source.example/item"}))
    text = TelegramRenderer("en").render(pub).text
    assert len(text) <= 4096
    assert "A complete sentence." in text
