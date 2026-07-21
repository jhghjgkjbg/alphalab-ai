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
    def __init__(self,api_key=None,model="gpt-4.1-mini",client=None,max_output_tokens=1200): self.api_key=api_key; self.model=model; self.client=client; self.max_output_tokens=max_output_tokens; self._last_response_id=""; self._last_usage=None; self._last_raw_text=""
    def enrich(self,prompt,tasks=()):
        if not self.api_key or self.client is None: return RawAIResponse(provider="openai",model=self.model,finish_reason="configuration_error",created_at=datetime.now(UTC).isoformat())
        try:
            response=self.client.responses.create(model=self.model,input=[{"role":"system","content":prompt.system_prompt},{"role":"user","content":prompt.user_prompt}],max_output_tokens=self.max_output_tokens,text={"format":{"type":"json_schema","name":"ai_response","strict":True,"schema":_RESPONSE_SCHEMA}})
        except Exception as exc:
            # Preserve the provider-agnostic response chain and never leak secrets.
            return RawAIResponse(provider="openai", model=self.model, finish_reason=f"{type(exc).__name__}: {exc}", created_at=datetime.now(UTC).isoformat())
        text=getattr(response,"output_text","") or ""; usage=getattr(response,"usage",None)
        self._last_response_id = str(getattr(response, "id", "") or "")
        self._last_raw_text = text
        self._last_usage = usage
        return RawAIResponse(provider="openai",model=self.model,raw_text=text,finish_reason=str(getattr(response,"status","")),input_tokens=int(getattr(usage,"input_tokens",0) or 0),output_tokens=int(getattr(usage,"output_tokens",0) or 0),response_id=str(getattr(response,"id","")),created_at=datetime.now(UTC).isoformat())
