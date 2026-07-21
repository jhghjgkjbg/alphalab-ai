"""Safety and delivery policy for the manual Telegram smoke test."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SmokePreflight:
    ok: bool
    reason: str = ""


def validate_preflight(*, confirm_send: bool, provider: str, token: str, en_target: str, ru_target: str, en_text: str, ru_text: str, ru_title: str | None = None, ru_body: str | None = None, max_length: int = 4096) -> SmokePreflight:
    if not confirm_send: return SmokePreflight(False, "confirm_send_required")
    if provider == "noop": return SmokePreflight(False, "real_ai_provider_required")
    if not token: return SmokePreflight(False, "missing_telegram_token")
    if not en_target: return SmokePreflight(False, "missing_en_target")
    if not ru_target: return SmokePreflight(False, "missing_ru_target")
    if en_target == ru_target: return SmokePreflight(False, "targets_must_differ")
    if not en_text.strip(): return SmokePreflight(False, "empty_en_view")
    if not ru_text.strip(): return SmokePreflight(False, "empty_ru_view")
    ru_title = ru_title if ru_title is not None else ru_text
    ru_body = ru_body if ru_body is not None else ru_text
    if not any("\u0400" <= char <= "\u04ff" for char in ru_title): return SmokePreflight(False, "ru_title_not_cyrillic")
    if not any("\u0400" <= char <= "\u04ff" for char in ru_body): return SmokePreflight(False, "ru_body_not_cyrillic")
    if len(en_text) > max_length or len(ru_text) > max_length: return SmokePreflight(False, "telegram_length_limit")
    return SmokePreflight(True)


def mask_target(value: str) -> str:
    return value[:2] + "***" + value[-2:] if len(value) > 4 else "***"


def selected_model(settings) -> str:
    return str(getattr(settings, "openrouter_model", "") or "")


def smoke_model_line(settings) -> str:
    """Safe diagnostic line used by the manual smoke test."""
    return f"model={selected_model(settings)}"
