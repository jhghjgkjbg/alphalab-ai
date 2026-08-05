from datetime import UTC, datetime
from core.ai_response.types import RawAIResponse

class GeminiProvider:
    name = "gemini"
    def __init__(self, api_key="", model="gemini-2.0-flash", request=None, timeout=30): self.api_key, self.model, self.request, self.timeout = api_key, model, request, timeout; self.last_failure_kind = None
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
                message = str((data.get("error") or {}).get("message", "")).lower()
                self.last_failure_kind = "region_unsupported" if "location" in message or "region" in message or "failed_precondition" in message else "provider_unavailable"
                return RawAIResponse(provider=self.name, model=self.model, finish_reason="provider_error", created_at=datetime.now(UTC).isoformat())
            parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
            if not text: self.last_failure_kind = "safety_blocked" if data.get("promptFeedback") else "empty_result"
            else: self.last_failure_kind = None
            return RawAIResponse(provider=self.name, model=self.model, raw_text=text, finish_reason="completed", created_at=datetime.now(UTC).isoformat())
        except TimeoutError: self.last_failure_kind = "timeout"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="timeout", created_at=datetime.now(UTC).isoformat())
        except Exception: self.last_failure_kind = "unknown"; return RawAIResponse(provider=self.name, model=self.model, finish_reason="error", created_at=datetime.now(UTC).isoformat())
