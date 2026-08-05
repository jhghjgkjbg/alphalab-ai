import builtins
from backend.app.core.config import Settings
from core.publication.composition import PublicationCompositionRoot

def _missing_reddit_import(monkeypatch):
    original = builtins.__import__
    def hooked(name, *args, **kwargs):
        if name == "core.publishers.reddit_remote":
            raise ModuleNotFoundError("missing", name="core.publishers.reddit_remote")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", hooked)

def _safe_settings(**kwargs):
    kwargs.update(devto_enabled=False, hashnode_enabled=False, x_enabled=False, linkedin_enabled=False, medium_enabled=False, substack_enabled=False)
    return Settings(**kwargs)

def test_reddit_module_is_not_needed_when_disabled(monkeypatch):
    _missing_reddit_import(monkeypatch)
    import core.analytics, core.storage
    class Store: pass
    monkeypatch.setattr(core.analytics, "DistributionEventStore", lambda: Store())
    monkeypatch.setattr(core.storage, "SQLitePublishedArticlesStore", lambda: Store())
    root = PublicationCompositionRoot.from_settings(_safe_settings(reddit_enabled=False))
    assert root.reddit_enabled is False

def test_missing_reddit_module_is_non_fatal_when_enabled(monkeypatch):
    _missing_reddit_import(monkeypatch)
    import core.analytics, core.storage
    class Store: pass
    monkeypatch.setattr(core.analytics, "DistributionEventStore", lambda: Store())
    monkeypatch.setattr(core.storage, "SQLitePublishedArticlesStore", lambda: Store())
    settings = _safe_settings(reddit_enabled=True, reddit_mode="remote_publish", reddit_subreddit="ml")
    root = PublicationCompositionRoot.from_settings(settings)
    assert root.reddit_enabled is False
    assert root.website_publisher is not None
    assert root.telegram_publisher_en is not None

def test_missing_hashnode_config_is_non_fatal(monkeypatch):
    import core.analytics, core.storage
    class Store: pass
    monkeypatch.setattr(core.analytics, "DistributionEventStore", lambda: Store())
    monkeypatch.setattr(core.storage, "SQLitePublishedArticlesStore", lambda: Store())
    settings = _safe_settings(hashnode_enabled=True, hashnode_personal_access_token="", hashnode_publication_id="")
    root = PublicationCompositionRoot.from_settings(settings)
    assert root.hashnode_enabled is False
    assert root.website_publisher is not None
    assert root.telegram_publisher_en is not None
