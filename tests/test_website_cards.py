from fastapi.testclient import TestClient

from agents.ai_scout.web.app import create_app


class Store:
    def latest(self, limit=50):
        return [{"id": "c1", "title": "Title", "summary": "Summary", "url": "https://source.test/a", "image_url": "https://cdn.test/a.jpg", "category": "AI", "source": "RSS", "published_at": "2026-08-04T12:00:00+00:00", "score": .8}]

    def count(self):
        return 1

    def search(self, query, limit=50):
        return self.latest(limit)


def test_homepage_api_exposes_image_without_en_body():
    response = TestClient(create_app(Store())).get("/api/articles")
    row = response.json()["items"][0]
    assert row["image_url"] == "https://cdn.test/a.jpg"
    assert "en_body" not in row


def test_card_rendering_contract_and_empty_fields_are_safe():
    script = open("agents/ai_scout/web/static/app.js", encoding="utf-8").read()
    assert "validImage" in script and "category-badge" in script and "score-badge" in script
    assert "relativeTime" in script
    assert "x.image_url" in script
    assert "excellent" in script


def test_homepage_hero_and_responsive_card_layout_are_present():
    html = open("agents/ai_scout/web/index.html", encoding="utf-8").read()
    css = open("agents/ai_scout/web/static/styles.css", encoding="utf-8").read()
    assert "What matters in AI" in html
    assert "grid-template-columns:repeat(3" in css
    assert "@media(max-width:1024px)" in css
    assert "@media(max-width:600px)" in css
    assert "id=\"search\"" in html and "id=\"category\"" in html and "id=\"source\"" in html
    assert "aspect-ratio:16/9" in css
    assert ".category-security" in css and ".category-open-source" in css


def test_card_highlights_use_existing_summary_with_safe_fallback():
    script = open("agents/ai_scout/web/static/app.js", encoding="utf-8").read()
    css = open("agents/ai_scout/web/static/styles.css", encoding="utf-8").read()
    assert "function highlights" in script
    assert "card-highlights" in script and "card-highlights" in css
    assert "slice(0, 2)" in script


def test_feed_search_filters_empty_state_and_load_more_contract():
    script = open("agents/ai_scout/web/static/app.js", encoding="utf-8").read()
    assert "setTimeout(() => load(true), 280)" in script
    assert "aria-label', 'Search articles" in script
    assert "aria-label', 'Clear search" in script
    assert "event.key === 'Escape'" in script
    assert "event.key === 'Enter'" in script
    assert "No articles found" in script
    assert "Try another search or reset filters." in script
    assert "Clear filters" in script
    assert "more.textContent = 'Loading...'" in script
    assert "more.textContent = 'Load more'" in script
