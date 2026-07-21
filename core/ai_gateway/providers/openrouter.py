from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from ..types import AIError, AIRequest, AIResponse, AIUsage

HttpRequest = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Awaitable[Any]]


class OpenRouterProvider:
    name = "openrouter"
    priority = 90
    quality = 0.85
    estimated_cost = 0.0002
    estimated_speed = 0.85
    supported_operations = frozenset({"classify", "summarize", "rank"})
    enabled = True

    def __init__(self, api_key: str, model: str = "deepseek/deepseek-chat-v3", timeout_seconds: float = 30.0, request: HttpRequest | None = None) -> None:
        if not api_key or not model or timeout_seconds <= 0 or request is None:
            raise ValueError("valid OpenRouter configuration is required")
        self._key, self._model, self._timeout, self._request = api_key, model, timeout_seconds, request

    async def execute(self, request: AIRequest) -> AIResponse:
        payload = {"model": self._model, "messages": [{"role": "user", "content": f"Task: {request.operation}\n{request.input}"}]}
        try:
            response = await self._request("https://openrouter.ai/api/v1/chat/completions", {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}, payload, self._timeout)
            status, data = self._unpack(response)
            if status in (401, 403): return self._error("unauthorized", "OpenRouter authorization failed")
            if status == 429: return self._error("rate_limit", "OpenRouter rate limit exceeded")
            if status == 402: return self._error("quota_exceeded", "OpenRouter quota exceeded")
            if status is not None and not 200 <= status < 300: return self._error("provider_error", "OpenRouter request failed")
            choices = data.get("choices") if isinstance(data, dict) else None
            text = choices[0].get("message", {}).get("content") if choices else None
            if not isinstance(text, str) or not text.strip(): return self._error("empty_response", "OpenRouter returned an empty response")
            usage = data.get("usage", {})
            return AIResponse(True, text, AIUsage(self.name, self._model, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)), self.estimated_cost))
        except TimeoutError: return self._error("timeout", "OpenRouter request timed out")
        except Exception: return self._error("malformed_response", "Malformed OpenRouter response")

    @staticmethod
    def _unpack(response: Any) -> tuple[int | None, Any]:
        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], int): return response[0], response[1]
        return None, response

    @staticmethod
    def _error(code: str, message: str) -> AIResponse:
        return AIResponse(False, None, error=AIError(code, message))
