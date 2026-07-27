from types import SimpleNamespace
from scripts import check_distribution_config as cli

def settings(**kw):
    base = dict(telegram_en_enabled=False, telegram_ru_enabled=False, x_enabled=False, linkedin_enabled=False, medium_enabled=False, devto_enabled=False, hashnode_enabled=False, substack_enabled=False, reddit_enabled=False, publish_at=None, telegram_bot_token=None, telegram_en_chat_id=None, telegram_ru_chat_id=None, x_bearer_token="", linkedin_access_token="", linkedin_author_urn="", medium_integration_token="", medium_author_id="", devto_api_key="", hashnode_personal_access_token="", hashnode_publication_id="")
    base.update(kw); return SimpleNamespace(**base)

def test_ready_disabled_and_draft_export(tmp_path):
    checks = cli.check(settings(substack_enabled=True, reddit_enabled=True), tmp_path, tmp_path / "lock")
    assert checks["substack"]["ready"] and checks["substack"]["mode"] == "draft_export"
    assert checks["reddit"]["ready"] and checks["telegram_en"]["enabled"] is False

def test_missing_enabled_fields_and_lock_path(tmp_path):
    checks = cli.check(settings(telegram_en_enabled=True), tmp_path, tmp_path / "x" / "lock")
    assert checks["telegram_en"]["ready"] is False
    assert "ALPHALAB_TELEGRAM_BOT_TOKEN" in checks["telegram_en"]["missing_fields"]
    assert checks["lock"]["ready"] is False

def test_json_stable_and_exit_codes(monkeypatch, capsys, tmp_path):
    result = {"checks": cli.check(settings(), tmp_path, tmp_path / "lock")}
    assert list(result["checks"]) == ["runtime", "lock", "telegram_en", "telegram_ru", "x", "linkedin", "medium", "devto", "hashnode", "substack", "reddit", "schedule"]
