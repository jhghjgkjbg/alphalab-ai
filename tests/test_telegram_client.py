import asyncio
import json
import unittest

from agents.ai_scout.publishers.telegram_client import TelegramClient


class TelegramClientTests(unittest.TestCase):
    def run_async(self, awaitable):
        return asyncio.run(awaitable)

    def client(self, response, **kwargs):
        calls = []
        async def request(url, payload, timeout):
            calls.append((url, payload, timeout))
            return response
        return TelegramClient("SECRET_TOKEN", "chat", 2, request, **kwargs), calls

    def test_success_and_request_payload(self):
        client, calls = self.client({"ok": True, "result": {"message_id": 7}})
        result = self.run_async(client.send_message("hello"))
        self.assertTrue(result.success)
        self.assertEqual(result.message_id, 7)
        self.assertEqual(calls[0][1], {"chat_id": "chat", "text": "hello"})

    def test_validation_and_errors(self):
        for text, expected in [("", "empty"), ("x" * 4097, "exceeds")]:
            client, _ = self.client({})
            result = self.run_async(client.send_message(text))
            self.assertFalse(result.success)
            self.assertIn(expected, result.error_message)

    def test_api_http_timeout_json_and_missing_message(self):
        cases = [
            ({"ok": False, "error_code": 400, "description": "bad"}, 400),
            (b"not-json", None),
            ({"ok": True, "result": {}}, None),
        ]
        for response, code in cases:
            client, _ = self.client(response)
            result = self.run_async(client.send_message("x"))
            self.assertFalse(result.success)
            self.assertEqual(result.error_code, code)

        async def failing(*_):
            raise TimeoutError("SECRET_TOKEN timeout")
        client = TelegramClient("SECRET_TOKEN", 1, 1, failing)
        result = self.run_async(client.send_message("x"))
        self.assertFalse(result.success)
        self.assertNotIn("SECRET_TOKEN", repr(client))
        self.assertNotIn("SECRET_TOKEN", result.error_message)

    def test_no_network_is_used(self):
        client, calls = self.client(json.dumps({"ok": True, "result": {"message_id": 1}}))
        self.run_async(client.send_message("x"))
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
