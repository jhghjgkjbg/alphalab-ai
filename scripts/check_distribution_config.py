"""Offline configuration preflight for content distribution."""
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path

SUCCESS, MISSING, STARTUP_ERROR = 0, 1, 2

def _field(value, name): return name if value in (None, "") else None

def check(settings, runtime_dir=None, lock_path=None):
    runtime = Path(runtime_dir or Path(__file__).resolve().parents[1] / "runtime")
    checks = {"runtime": {"enabled": True, "ready": runtime.is_dir() and os.access(runtime, os.R_OK), "mode": "local", "missing_fields": [] if runtime.is_dir() else ["RUNTIME_DIRECTORY"], "warnings": []}}
    lock = Path(lock_path or os.environ.get("ALPHALAB_SCHEDULED_RUN_LOCK") or runtime / "scheduled_distribution.lock")
    checks["lock"] = {"enabled": True, "ready": lock.parent.is_dir() and os.access(lock.parent, os.R_OK | os.W_OK), "mode": "local", "missing_fields": [] if lock.parent.is_dir() else ["ALPHALAB_SCHEDULED_RUN_LOCK"], "warnings": []}
    def add(name, enabled, required, mode="remote_publish"):
        missing = [env for env, value in required if value in (None, "")]
        checks[name] = {"enabled": bool(enabled), "ready": not enabled or not missing, "mode": mode, "missing_fields": missing, "warnings": []}
    add("telegram_en", getattr(settings, "telegram_en_enabled", True), [("ALPHALAB_TELEGRAM_BOT_TOKEN", getattr(settings, "telegram_bot_token", None)), ("ALPHALAB_TELEGRAM_EN_CHAT_ID", getattr(settings, "telegram_en_chat_id", None))])
    add("telegram_ru", getattr(settings, "telegram_ru_enabled", False), [("ALPHALAB_TELEGRAM_BOT_TOKEN", getattr(settings, "telegram_bot_token", None)), ("ALPHALAB_TELEGRAM_RU_CHAT_ID", getattr(settings, "telegram_ru_chat_id", None))])
    x_enabled = getattr(settings, "x_enabled", False)
    x_access = getattr(settings, "x_access_token", "") or ""
    x_refresh = getattr(settings, "x_refresh_token", "") or ""
    x_client = getattr(settings, "x_client_id", "") or ""
    x_missing = []
    if x_enabled:
        if not (x_access or x_refresh): x_missing.append("ALPHALAB_X_ACCESS_TOKEN")
        if not x_refresh: x_missing.append("ALPHALAB_X_REFRESH_TOKEN")
        if not x_client: x_missing.append("ALPHALAB_X_CLIENT_ID")
    checks["x"] = {"enabled": bool(x_enabled), "ready": not x_enabled or not x_missing, "mode": "remote_publish", "missing_fields": x_missing, "warnings": (["ALPHALAB_X_BEARER_TOKEN_DEPRECATED"] if x_enabled and getattr(settings, "x_bearer_token", "") else [])}
    if x_enabled:
        state_path = Path(getattr(settings, "x_token_state_path", os.environ.get("ALPHALAB_X_TOKEN_STATE_PATH", "runtime/secrets/x_oauth_tokens.json")))
        if state_path.exists():
            if not state_path.is_file(): checks["x"]["ready"] = False; checks["x"]["warnings"].append("ALPHALAB_X_TOKEN_STATE_PATH_NOT_FILE")
            elif os.name != "nt" and (state_path.stat().st_mode & 0o077): checks["x"]["ready"] = False; checks["x"]["warnings"].append("ALPHALAB_X_TOKEN_STATE_PATH_INSECURE")
        elif not state_path.parent.exists() and not os.access(state_path.parent.parent if state_path.parent.parent.exists() else Path("."), os.W_OK):
            checks["x"]["ready"] = False; checks["x"]["warnings"].append("ALPHALAB_X_TOKEN_STATE_PATH_UNAVAILABLE")
    add("linkedin", getattr(settings, "linkedin_enabled", False), [("ALPHALAB_LINKEDIN_ACCESS_TOKEN", getattr(settings, "linkedin_access_token", "")), ("ALPHALAB_LINKEDIN_AUTHOR_URN", getattr(settings, "linkedin_author_urn", ""))])
    add("medium", getattr(settings, "medium_enabled", False), [("ALPHALAB_MEDIUM_INTEGRATION_TOKEN", getattr(settings, "medium_integration_token", "")), ("ALPHALAB_MEDIUM_AUTHOR_ID", getattr(settings, "medium_author_id", ""))])
    add("devto", getattr(settings, "devto_enabled", False), [("ALPHALAB_DEVTO_API_KEY", getattr(settings, "devto_api_key", ""))])
    add("hashnode", getattr(settings, "hashnode_enabled", False), [("ALPHALAB_HASHNODE_PERSONAL_ACCESS_TOKEN", getattr(settings, "hashnode_personal_access_token", "")), ("ALPHALAB_HASHNODE_PUBLICATION_ID", getattr(settings, "hashnode_publication_id", ""))])
    add("substack", getattr(settings, "substack_enabled", False), [], "draft_export")
    add("reddit", getattr(settings, "reddit_enabled", False), [], "draft_export")
    publish_at = getattr(settings, "publish_at", None)
    if publish_at is not None and (publish_at.tzinfo is None or publish_at.utcoffset() is None):
        checks["schedule"] = {"enabled": True, "ready": False, "mode": "local", "missing_fields": ["ALPHALAB_PUBLISH_AT"], "warnings": ["must_be_timezone_aware"]}
    else:
        checks["schedule"] = {"enabled": publish_at is not None, "ready": True, "mode": "local", "missing_fields": [], "warnings": []}
    return checks

def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("--json", action="store_true", dest="as_json"); args = parser.parse_args(argv)
    try:
        from backend.app.core.config import Settings
        checks = check(Settings())
        result = {"checks": checks, "ready": all(item["ready"] for item in checks.values())}
        print(json.dumps(result, sort_keys=True, separators=(",", ":")) if args.as_json else _human(result))
        return SUCCESS if result["ready"] else MISSING
    except Exception as exc:
        print(f"preflight failed: {type(exc).__name__}", file=sys.stderr); return STARTUP_ERROR

def _human(result):
    lines = ["Distribution configuration preflight", "===================================="]
    for name, item in result["checks"].items():
        lines.append(f"{name}: enabled={item['enabled']} ready={item['ready']} mode={item['mode']} missing_fields={','.join(item['missing_fields']) or '-'} warnings={','.join(item['warnings']) or '-'}")
    return "\n".join(lines)

if __name__ == "__main__": raise SystemExit(main())
