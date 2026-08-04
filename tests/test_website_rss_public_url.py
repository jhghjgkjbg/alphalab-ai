from fastapi.testclient import TestClient

from agents.ai_scout.web.app import create_app
from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore
from core.publication.builder import PublicationBuilder
from core.collector.types import SourceItem
from datetime import datetime, UTC
from pathlib import Path
import tempfile


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


def test_article_adds_image_metadata_only_for_valid_image_url():
    store = _Store()
    store.latest = lambda limit=50: [{
        "id": "image-article", "title": "Image article", "summary": "Summary",
        "url": "https://source.example/article", "image_url": "https://cdn.example/image.jpg",
        "published_at": "2026-07-27T10:00:00+00:00",
    }]
    client = TestClient(create_app(store))
    response = client.get("/article/image-article")
    assert response.status_code == 200
    assert "property='og:image'" in response.text
    assert "name='twitter:image'" in response.text
    assert "https://cdn.example/image.jpg" in response.text
    assert "article-hero-image" in response.text
    assert "article-kicker" in response.text


def test_image_url_persists_and_old_schema_migrates():
    with tempfile.TemporaryDirectory() as directory:
        store = SQLitePublishedArticlesStore(SQLiteDatabase(Path(directory) / "articles.db"))
        item = SourceItem("rss", "persisted-image", datetime.now(UTC), {
            "title": "Image", "summary": "Summary", "url": "https://source.example/image",
            "image_url": "https://cdn.example/image.jpg",
        })
        store.append(PublicationBuilder().build(item))
        assert store.latest(1)[0]["image_url"] == "https://cdn.example/image.jpg"
