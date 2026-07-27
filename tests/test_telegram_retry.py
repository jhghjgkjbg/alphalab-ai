import asyncio

from agents.ai_scout.publishers.telegram_client import TelegramClient


def run_client(responses, **kwargs):
    calls, sleeps = [], []
    async def request(*args):
        calls.append(args)
        value = responses.pop(0)
        if isinstance(value, BaseException): raise value
        return value
    async def sleep(delay): sleeps.append(delay)
    client = TelegramClient("token", "chat", 1, request, sleep=sleep, jitter=lambda _: 0, **kwargs)
    return asyncio.run(client.send_message("hello")), calls, sleeps


def test_success_first_attempt_has_no_sleep():
    result, calls, sleeps = run_client([{"ok": True, "result": {"message_id": 1}}])
    assert result.success and len(calls) == 1 and sleeps == []


def test_http_500_retries_then_succeeds():
    result, calls, sleeps = run_client([{"ok": False, "error_code": 500}, {"ok": True, "result": {"message_id": 2}}])
    assert result.success and len(calls) == 2 and sleeps == [1.0]


def test_429_retry_after_is_capped():
    result, calls, sleeps = run_client([{"ok": False, "error_code": 429, "parameters": {"retry_after": 99}}, {"ok": True, "result": {"message_id": 3}}], retry_max_seconds=4)
    assert result.success and sleeps == [4.0]


def test_timeout_and_bad_request_are_not_retried():
    for response in (TimeoutError("timeout"), {"ok": False, "error_code": 400}, {"ok": False, "error_code": 401}, {"ok": False, "error_code": 403}, "not-json"):
        result, calls, sleeps = run_client([response])
        assert not result.success and len(calls) == 1 and sleeps == []


def test_connect_error_retries():
    try:
        import httpx
    except ImportError:
        return
    result, calls, sleeps = run_client([httpx.ConnectError("connect"), {"ok": True, "result": {"message_id": 4}}])
    assert result.success and len(calls) == 2 and sleeps == [1.0]
