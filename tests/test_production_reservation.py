from pathlib import Path

from core.storage import SQLiteDatabase, SQLitePublishedArticlesStore


def make_store(tmp_path):
    return SQLitePublishedArticlesStore(SQLiteDatabase(Path(tmp_path) / "reservations.db"))


def test_first_reservation_wins_and_second_article_id_is_rejected(tmp_path):
    store = make_store(tmp_path)
    assert store.reserve("a1", "https://example.test/a")
    assert not store.reserve("a1", "https://example.test/other")


def test_canonical_url_is_unique_across_article_ids(tmp_path):
    store = make_store(tmp_path)
    assert store.reserve("a1", "https://example.test/a")
    assert not store.reserve("a2", "https://example.test/a")


def test_separate_connections_cannot_both_reserve(tmp_path):
    path = Path(tmp_path) / "reservations.db"
    first = SQLitePublishedArticlesStore(SQLiteDatabase(path))
    second = SQLitePublishedArticlesStore(SQLiteDatabase(path))
    assert first.reserve("a1", "https://example.test/a")
    assert not second.reserve("a1", "https://example.test/a")


def test_failed_reservation_can_be_released_and_retried(tmp_path):
    store = make_store(tmp_path)
    assert store.reserve("a1", "https://example.test/a")
    assert store.release_reservation("a1", "https://example.test/a")
    assert store.reserve("a1", "https://example.test/a")


def test_successful_finalization_blocks_future_reservation(tmp_path):
    store = make_store(tmp_path)
    assert store.reserve("a1", "https://example.test/a")
    assert store.finalize_reservation("a1", "https://example.test/a")
    assert not store.reserve("a1", "https://example.test/a")

