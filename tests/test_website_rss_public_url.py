from fastapi.testclient import TestClient

from agents.ai_scout.web.app import create_app


class _Store:
    def latest(self, limit=50):
        return [{
            "id": "rss-public-url",
            "title": "RSS article",
            "summary": "Summary",
            "url": "https://source.example/article",
            "published_at": "2026-07-27T10:00:00+00:00",
        }]

    def count(self):
        return 1


def test_rss_uses_public_base_url_for_local_request(monkeypatch):
    monkeypatch.delenv("ALPHALAB_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    client = TestClient(create_app(_Store()), base_url="http://127.0.0.1:8080")

    response = client.get("/rss")

    assert response.status_code == 200
    assert "https://alphalabai.online/article/rss-public-url" in response.text
    assert "127.0.0.1:8080/article/" not in response.text
