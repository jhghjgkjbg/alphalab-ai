from datetime import datetime, UTC
from core.ai_response.types import RawAIResponse
from typing import Any

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
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

class OpenAIProvider:
    name="openai"
    def __init__(self,api_key=None,model="gpt-4.1-mini",client=None,max_output_tokens=1200): self.api_key=api_key; self.model=model; self.client=client; self.max_output_tokens=max_output_tokens; self._last_response_id=""; self._last_usage=None; self._last_raw_text=""; self.last_failure_kind=None
    def enrich(self,prompt,tasks=()):
        if not self.api_key or self.client is None: return RawAIResponse(provider="openai",model=self.model,finish_reason="configuration_error",created_at=datetime.now(UTC).isoformat())
        try:
            response=self.client.responses.create(model=self.model,input=[{"role":"system","content":prompt.system_prompt},{"role":"user","content":prompt.user_prompt}],max_output_tokens=self.max_output_tokens,text={"format":{"type":"json_schema","name":"ai_response","strict":True,"schema":_RESPONSE_SCHEMA}})
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None) or 0
            body = getattr(exc, "body", None) or getattr(exc, "response", None)
            if hasattr(body, "json"):
                try: body = body.json()
                except Exception: body = {}
            error = body.get("error", body) if isinstance(body, dict) else {}
            error_type = str(error.get("type", "unknown")) if isinstance(error, dict) else "unknown"
            error_code = str(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
            if error_code == "credit_balance_exhausted" or error_type == "insufficient_quota": kind = "payment_required"
            elif status == 401: kind = "authentication"
            elif status == 403: kind = "authorization"
            elif status == 429: kind = "rate_limited"
            elif status >= 500: kind = "provider_unavailable"
            else: kind = "unknown"
            self.last_failure_kind = kind
            print(f"openai_http_status={status}")
            print(f"openai_error_type={error_type}")
            print(f"openai_error_code={error_code}")
            print(f"ai_provider_failure_kind={kind}")
            return RawAIResponse(provider="openai", model=self.model, finish_reason=f"{type(exc).__name__}: {exc}", created_at=datetime.now(UTC).isoformat())
        text=getattr(response,"output_text","") or ""; usage=getattr(response,"usage",None)
        self.last_failure_kind = None if text.strip() else "empty_result"
        if not text.strip():
            print("openai_http_status=200")
            print("openai_error_type=none")
            print("openai_error_code=none")
            print("ai_provider_failure_kind=empty_result")
        self._last_response_id = str(getattr(response, "id", "") or "")
        self._last_raw_text = text
        self._last_usage = usage
        return RawAIResponse(provider="openai",model=self.model,raw_text=text,finish_reason=str(getattr(response,"status","")),input_tokens=int(getattr(usage,"input_tokens",0) or 0),output_tokens=int(getattr(usage,"output_tokens",0) or 0),response_id=str(getattr(response,"id","")),created_at=datetime.now(UTC).isoformat())
