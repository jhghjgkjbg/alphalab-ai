import io
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.publishers.telegram_client import TelegramClient


class TelegramCompositionTests(unittest.TestCase):
    def test_injected_client_registers_telegram_publisher(self):
        async def request(*_):
            return {"ok": True, "result": {"message_id": 1}}

        scout = AIScout(
            output=io.StringIO(),
            telegram_client=TelegramClient("secret", "chat", 1, request),
            rss_enabled=False,
        )
        self.assertEqual(scout._publisher_registry.channels(), ("console", "telegram"))

    def test_configuration_builds_client_without_network(self):
        calls = []
        async def request(*args):
            calls.append(args)
            return {"ok": True, "result": {"message_id": 1}}

        scout = AIScout(
            output=io.StringIO(), telegram_bot_token="secret",
            telegram_chat_id="chat", telegram_parse_mode="HTML",
            telegram_request=request, rss_enabled=False,
        )
        self.assertIn("telegram", scout._publisher_registry.channels())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
