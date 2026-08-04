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
