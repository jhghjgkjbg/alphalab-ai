from __future__ import annotations

import json
import asyncio
import random
try:
    import httpx
except ImportError:  # optional outside the production transport environment
    httpx = None
from urllib.error import HTTPError
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any


TelegramRequest = Callable[[str, Mapping[str, str], float], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class TelegramSendResult:
    success: bool
    message_id: int | None
    chat_id: str
    error_code: int | None
    error_message: str | None
    attempts: int = 1


class TelegramClient:
    MAX_MESSAGE_LENGTH = 4096

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        timeout_seconds: float,
        request: TelegramRequest,
        *,
        parse_mode: str | None = None,
        max_attempts: int = 3,
        retry_base_seconds: float = 1.0,
        retry_max_seconds: float = 15.0,
        sleep: Callable[[float], Awaitable[Any]] | None = None,
        jitter: Callable[[float], float] | None = None,
    ) -> None:
        if not bot_token:
            raise ValueError("bot_token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._bot_token = bot_token
        self._chat_id = str(chat_id)
        self._timeout_seconds = timeout_seconds
        self._request = request
        self._parse_mode = parse_mode
        self._max_attempts = max(1, int(max_attempts))
        self._retry_base = max(0.0, float(retry_base_seconds))
        self._retry_max = max(0.0, float(retry_max_seconds))
        self._sleep = sleep or asyncio.sleep
        self._jitter = jitter or (lambda _delay: random.uniform(0.0, 0.1))

    async def send_message(self, text: str) -> TelegramSendResult:
        if not text:
            return self._failure(None, "message text must not be empty")
        if len(text) > self.MAX_MESSAGE_LENGTH:
            return self._failure(None, "message text exceeds Telegram limit")

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload: dict[str, str] = {"chat_id": self._chat_id, "text": text}
        if self._parse_mode is not None:
            payload["parse_mode"] = self._parse_mode
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._request(url, payload, self._timeout_seconds)
            except (TimeoutError, ConnectionError) as exc:
                if isinstance(exc, TimeoutError):
                    return self._failure(None, self._safe_error(exc, self._bot_token), attempt)
                if attempt < self._max_attempts:
                    await self._wait(attempt, None)
                    continue
                return self._failure(None, self._safe_error(exc, self._bot_token), attempt)
            except Exception as exc:
                if httpx is not None and isinstance(exc, httpx.ConnectError) and attempt < self._max_attempts:
                    await self._wait(attempt, None)
                    continue
                return self._failure(None, self._safe_error(exc, self._bot_token), attempt)
            if isinstance(response, tuple) and response:
                status = response[0]
            elif httpx is not None and isinstance(response, httpx.Response):
                status = response.status_code
            else:
                status = getattr(response, "status", None)
            try:
                data = self._decode(response)
            except Exception:
                return self._failure(None, "invalid Telegram response", attempt)
            if status in {429, 500, 502, 503, 504}:
                if attempt < self._max_attempts:
                    retry_after = data.get("parameters", {}).get("retry_after") if isinstance(data, dict) else None
                    await self._wait(attempt, retry_after)
                    continue
                return self._failure(status, f"retry_exhausted_http_{status}", attempt)
            if isinstance(data, dict) and not data.get("ok", False):
                code = data.get("error_code")
                if code in {429, 500, 502, 503, 504} and attempt < self._max_attempts:
                    await self._wait(attempt, data.get("parameters", {}).get("retry_after"))
                    continue
                return self._failure(code if isinstance(code, int) else None, self._safe_message(data.get("description"), self._bot_token), attempt)
            break

        if not isinstance(data, dict):
            return self._failure(None, "invalid Telegram response", attempt)
        result = data.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not isinstance(message_id, int):
            return self._failure(None, "Telegram response has no message_id", attempt)
        return TelegramSendResult(True, message_id, self._chat_id, None, None)

    async def _wait(self, attempt: int, retry_after: Any):
        try: delay = min(self._retry_max, max(0.0, float(retry_after))) if retry_after is not None else min(self._retry_max, self._retry_base * (2 ** (attempt - 1)))
        except (TypeError, ValueError): delay = min(self._retry_max, self._retry_base * (2 ** (attempt - 1)))
        await self._sleep(delay + (0.0 if retry_after is not None else self._jitter(delay)))

    def _failure(self, code: int | None, message: str, attempts: int = 1) -> TelegramSendResult:
        return TelegramSendResult(False, None, self._chat_id, code, message, attempts)

    @staticmethod
    def _decode(response: Any) -> Any:
        if isinstance(response, tuple) and len(response) == 2:
            return TelegramClient._decode(response[1])
        if isinstance(response, (bytes, bytearray)):
            response = response.decode("utf-8")
        if isinstance(response, str):
            return json.loads(response)
        if httpx is not None and isinstance(response, httpx.Response):
            return response.json()
        return response

    @staticmethod
    def _safe_error(exc: Exception, secret: str) -> str:
        message = str(exc) or type(exc).__name__
        return message.replace(secret, "[redacted]")

    @staticmethod
    def _safe_message(value: Any, secret: str) -> str:
        if not isinstance(value, str) or not value:
            return "Telegram API request failed"
        return value.replace(secret, "[redacted]")
