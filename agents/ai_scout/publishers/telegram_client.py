from __future__ import annotations

import json
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

    async def send_message(self, text: str) -> TelegramSendResult:
        if not text:
            return self._failure(None, "message text must not be empty")
        if len(text) > self.MAX_MESSAGE_LENGTH:
            return self._failure(None, "message text exceeds Telegram limit")

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload: dict[str, str] = {"chat_id": self._chat_id, "text": text}
        if self._parse_mode is not None:
            payload["parse_mode"] = self._parse_mode
        try:
            response = await self._request(url, payload, self._timeout_seconds)
            if isinstance(response, tuple) and response:
                status = response[0]
            elif httpx is not None and isinstance(response, httpx.Response):
                status = response.status_code
            else:
                status = getattr(response, "status", None)
            data = self._decode(response)
        except HTTPError as exc:
            body = exc.read()
            try:
                decoded = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)
                data = json.loads(decoded)
                message = data.get("description") if isinstance(data, dict) else "Telegram HTTP request failed"
                code = data.get("error_code") if isinstance(data, dict) and isinstance(data.get("error_code"), int) else exc.code
                return self._failure(code, self._safe_message(message, self._bot_token))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                return self._failure(exc.code, "Telegram HTTP request failed")
        except Exception as exc:
            return self._failure(None, self._safe_error(exc, self._bot_token))

        if not isinstance(data, dict):
            return self._failure(None, "invalid Telegram response")
        if not data.get("ok", False):
            error_code = data.get("error_code")
            return self._failure(error_code if isinstance(error_code, int) else None,
                                 self._safe_message(data.get("description"), self._bot_token))
        result = data.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not isinstance(message_id, int):
            return self._failure(None, "Telegram response has no message_id")
        return TelegramSendResult(True, message_id, self._chat_id, None, None)

    def _failure(self, code: int | None, message: str) -> TelegramSendResult:
        return TelegramSendResult(False, None, self._chat_id, code, message)

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
