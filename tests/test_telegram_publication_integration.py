import asyncio
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from agents.ai_scout.publishers.telegram_client import TelegramClient
from agents.ai_scout.publishers.telegram_publisher import TelegramPublisher
from core.publication.types import PublicationCandidate


def make_candidate() -> PublicationCandidate:
    return PublicationCandidate(
        candidate_id=uuid4(), document_id=uuid4(), source="rss",
        title="AI update", url="https://example.com/item", summary="A summary",
        keywords=("AI",), tags=("news",), total_score=72,
        reasons=("fresh", "trusted source"), channels=("telegram",),
        correlation_id=uuid4(), created_at=datetime.now(UTC),
    )


class TelegramPublicationIntegrationTests(unittest.TestCase):
    def test_candidate_reaches_telegram_with_format_and_parse_mode(self):
        calls = []

        async def request(url, payload, timeout):
            calls.append((url, payload, timeout))
            return {"ok": True, "result": {"message_id": 42}}

        client = TelegramClient("token", "chat-7", 3, request, parse_mode="HTML")
        result = asyncio.run(TelegramPublisher(client).publish(make_candidate()))

        self.assertTrue(result.success)
        self.assertEqual(result.external_id, "42")
        self.assertEqual(calls[0][1]["chat_id"], "chat-7")
        self.assertEqual(calls[0][1]["parse_mode"], "HTML")
        self.assertIn("AI update", calls[0][1]["text"])
        self.assertIn("https://example.com/item", calls[0][1]["text"])
        self.assertIn("Score: 72", calls[0][1]["text"])

    def test_client_error_becomes_failed_publish_result(self):
        async def request(*_):
            return {"ok": False, "error_code": 403, "description": "blocked"}

        client = TelegramClient("token", "chat", 3, request)
        result = asyncio.run(TelegramPublisher(client).publish(make_candidate()))

        self.assertFalse(result.success)
        self.assertIsNone(result.external_id)
        self.assertEqual(result.error_message, "blocked")


if __name__ == "__main__":
    unittest.main()
