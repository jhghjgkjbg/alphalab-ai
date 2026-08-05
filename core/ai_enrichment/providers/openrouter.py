from datetime import UTC, datetime
from typing import Any

from core.ai_response.types import RawAIResponse

_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "en_title": {"type": "string", "description": "English news headline only."},
        "en_body": {"type": "string", "description": "English summary only."},
        "ru_title": {"type": "string", "description": "Idiomatic Russian news headline in Cyrillic; never copy or transliterate en_title."},
        "ru_body": {"type": "string", "description": "Russian summary in Cyrillic only."},
        "headline_suggestions": {"type": "array", "items": {"type": "string"}},
        "short_summary": {"type": "string"}, "long_summary": {"type": "string"},
        "seo_keywords": {"type": "array", "items": {"type": "string"}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "entities": {"type": "array", "items": {"type": "string"}},
        "topics": {"type": "array", "items": {"type": "string"}},
        "category_guess": {"type": "string"}, "language": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "editor_notes": {"type": "string"}, "translation": {"type": "string"},
        "translation_status": {"type": "string"},
    },
    "required": ["headline_suggestions", "short_summary", "long_summary", "seo_keywords", "hashtags", "entities", "topics", "category_guess", "language", "confidence", "editor_notes", "translation", "translation_status"],
}


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key=None, model="", client=None, max_output_tokens=1200):
        self.api_key, self.model, self.client = api_key, model, client
        self.max_output_tokens = max_output_tokens
        self._last_response_id = ""
        self._last_raw_text = ""
        self._last_usage = None
        self.last_failure_kind = None

    def enrich(self, prompt, tasks=()):
        if not self.api_key or self.client is None:
            return RawAIResponse(provider=self.name, model=self.model, finish_reason="configuration_error", created_at=datetime.now(UTC).isoformat())
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt.system_prompt}, {"role": "user", "content": prompt.user_prompt}],
                max_tokens=self.max_output_tokens,
                response_format={"type": "json_schema", "json_schema": {"name": "ai_response", "strict": True, "schema": _SCHEMA}},
            )
            choices = getattr(response, "choices", ()) or ()
            message = getattr(choices[0], "message", None) if choices else None
            content = getattr(message, "content", "") if message else ""
            self._last_raw_text = str(content or "")
            self.last_failure_kind = None
            usage = getattr(response, "usage", None)
            self._last_response_id = str(getattr(response, "id", "") or "")
            self._last_usage = usage
            return RawAIResponse(provider=self.name, model=self.model, raw_text=str(content or ""), response_id=self._last_response_id, finish_reason="completed", input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0), output_tokens=int(getattr(usage, "completion_tokens", 0) or 0), created_at=datetime.now(UTC).isoformat())
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
            self.last_failure_kind = {401: "authentication", 403: "authorization", 402: "payment_required", 429: "rate_limited"}.get(status, "provider_unavailable" if status and int(status) >= 500 else "unknown")
            return RawAIResponse(provider=self.name, model=self.model, finish_reason=f"{type(exc).__name__}: {exc}", created_at=datetime.now(UTC).isoformat())
