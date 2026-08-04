from pathlib import Path

from fastapi.testclient import TestClient

from agents.ai_scout.web.app import create_app
from core.storage.database import SQLiteDatabase
from core.storage.stores import SQLitePublishedArticlesStore


def client(tmp_path):
    store = SQLitePublishedArticlesStore(SQLiteDatabase(tmp_path / "subscribers.db"))
    sent = []
    return TestClient(create_app(store, email_sender=lambda *args: sent.append(args))), store


def test_subscribe_form_and_normalized_idempotent_storage(tmp_path):
    api, store = client(tmp_path)
    page = api.get("/subscribe")
    assert page.status_code == 200
    assert "id='subscribe-form'" in page.text
    assert "https://t.me/alphalabai_en" in page.text
    assert "Join Telegram" in page.text
    assert "http://127.0.0.1:8080/rss" not in page.text
    assert "your@email.com" in page.text
    assert "theme-toggle" in page.text
    first = api.post("/api/subscribe", json={"email": " User@Example.com ", "consent": True})
    second = api.post("/api/subscribe", json={"email": "user@example.com", "consent": True})
    assert first.status_code == 200 and first.json()["pending"] is True
    assert second.status_code == 200 and second.json()["pending"] is True
    with store.database.connect() as connection:
        rows = connection.execute("SELECT email,status FROM subscribers").fetchall()
    assert [(row[0], row[1]) for row in rows] == [("user@example.com", "pending")]


def test_subscribe_rejects_invalid_email_and_missing_consent(tmp_path):
    api, _ = client(tmp_path)
    assert api.post("/api/subscribe", json={"email": "bad", "consent": True}).status_code == 422
    assert api.post("/api/subscribe", json={"email": "a@example.com", "consent": False}).status_code == 422


def test_subscribers_migration_is_idempotent(tmp_path):
    path = tmp_path / "existing.db"
    first = SQLiteDatabase(path)
    first.migrate()
    second = SQLiteDatabase(path)
    with second.connect() as connection:
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='subscribers'").fetchone()


def test_theme_css_supports_manual_preference_and_system_dark_mode():
    css = Path("agents/ai_scout/web/static/styles.css").read_text(encoding="utf-8")
    js = Path("agents/ai_scout/web/static/app.js").read_text(encoding="utf-8")
    assert "prefers-color-scheme:dark" in css
    assert "data-theme=\"dark\"" in css
    assert "alphalab-theme" in js
    assert "localStorage" in js
