from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from ..types import AIError, AIRequest, AIResponse, AIUsage


HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Awaitable[Any]]


class GeminiProvider:
    name = "gemini"
    enabled = True
    priority = 100
    estimated_cost = 0.0001
    estimated_speed = 0.9
    quality = 0.85
    supported_operations = frozenset({"classify", "summarize", "rank"})

    def __init__(self, api_key: str, model: str, timeout_seconds: float, request: HttpRequest) -> None:
        if not api_key or not model or timeout_seconds <= 0:
            raise ValueError("valid Gemini configuration is required")
        self._api_key, self._model, self._timeout, self._request = api_key, model, timeout_seconds, request

    async def execute(self, request: AIRequest) -> AIResponse:
        prompt = f"Task: {request.operation}\nInput:\n{request.input}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = await self._request(url, {"Content-Type": "application/json"}, payload, self._timeout)
            status, data = self._unpack(response)
            if status in (401, 403):
                return self._error("invalid_api_key", "Gemini API key is invalid")
            if status == 429:
                return self._error("rate_limit", "Gemini rate limit exceeded")
            if status ==  quota_status():
                return self._error("quota_exceeded", "Gemini quota exceeded")
            if status is not None and not 200 <= status < 300:
                return self._error("provider_error", "Gemini request failed")
            candidates = data.get("candidates") if isinstance(data, dict) else None
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text") if candidates else None
            if not isinstance(text, str) or not text.strip():
                return self._error("empty_response", "Gemini returned an empty response")
            usage = data.get("usageMetadata", {})
            return AIResponse(True, text, AIUsage(self.name, self._model, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)), self.estimated_cost))
        except TimeoutError:
            return self._error("timeout", "Gemini request timed out")
        except Exception:
            return self._error("malformed_response", "Malformed Gemini response")

    def _error(self, code: str, message: str) -> AIResponse:
        return AIResponse(False, None, error=AIError(code, message))

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int): return response[0], response[1]
        return None, response


def quota_status() -> int:
    return 402
