from pathlib import Path

from fastapi.testclient import TestClient

from agents.ai_scout.web.app import create_app
from core.storage.database import SQLiteDatabase
from core.storage.stores import SQLitePublishedArticlesStore


def client(tmp_path):
    store = SQLitePublishedArticlesStore(SQLiteDatabase(tmp_path / "subscribers.db"))
    return TestClient(create_app(store)), store


def test_subscribe_form_and_normalized_idempotent_storage(tmp_path):
    api, store = client(tmp_path)
    page = api.get("/subscribe")
    assert page.status_code == 200
    assert "id='subscribe-form'" in page.text
    first = api.post("/api/subscribe", json={"email": " User@Example.com ", "consent": True})
    second = api.post("/api/subscribe", json={"email": "user@example.com", "consent": True})
    assert first.status_code == 200 and first.json()["already_subscribed"] is False
    assert second.status_code == 200 and second.json()["already_subscribed"] is True
    with store.database.connect() as connection:
        rows = connection.execute("SELECT email,status FROM subscribers").fetchall()
    assert [(row[0], row[1]) for row in rows] == [("user@example.com", "subscribed")]


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
