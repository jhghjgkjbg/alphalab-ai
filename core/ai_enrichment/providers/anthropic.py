from datetime import UTC, datetime
from core.ai_response.types import RawAIResponse

class AnthropicProvider:
    name = "anthropic"
    def __init__(self, api_key="", model="claude-3-5-haiku-latest", request=None, timeout=30): self.api_key, self.model, self.request, self.timeout = api_key, model, request, timeout; self.last_failure_kind = None
    def enrich(self, prompt, tasks=()):
        if not self.api_key or self.request is None: self.last_failure_kind = "configuration_missing"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="configuration_error", created_at=datetime.now(UTC).isoformat())
        try:
            response = self.request(self.model, prompt.user_prompt, self.api_key, self.timeout)
            data = response.json() if hasattr(response, "json") else response
            status = getattr(response, "status_code", 200)
            if status in (401, 403): self.last_failure_kind = "authentication" if status == 401 else "authorization"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="provider_error", created_at=datetime.now(UTC).isoformat())
            if status == 429: self.last_failure_kind = "rate_limited"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="provider_error", created_at=datetime.now(UTC).isoformat())
            if status >= 500: self.last_failure_kind = "provider_unavailable"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="provider_error", created_at=datetime.now(UTC).isoformat())
            if isinstance(data, dict) and data.get("error"):
                error_text = str(data.get("error", "")).lower()
                self.last_failure_kind = "payment_required" if "credit" in error_text or "balance" in error_text else "unknown"
                return RawAIResponse(provider=self.name, model=self.model, finish_reason="provider_error", created_at=datetime.now(UTC).isoformat())
            blocks = data.get("content") or [] if isinstance(data, dict) else []
            text = "".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict) and b.get("type") == "text")
            self.last_failure_kind = None if text else "empty_result"
            return RawAIResponse(provider=self.name, model=self.model, raw_text=text, finish_reason="completed", created_at=datetime.now(UTC).isoformat())
        except TimeoutError: self.last_failure_kind = "timeout"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="timeout", created_at=datetime.now(UTC).isoformat())
        except Exception: self.last_failure_kind = "unknown"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="error", created_at=datetime.now(UTC).isoformat())
