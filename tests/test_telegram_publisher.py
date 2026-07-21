import asyncio
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from agents.ai_scout.publishers.telegram_publisher import TelegramPublisher
from agents.ai_scout.publishers.telegram_client import TelegramSendResult
from core.publication.types import PublicationCandidate


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.text = None

    async def send_message(self, text):
        self.text = text
        return self.result


def candidate():
    return PublicationCandidate(
        uuid4(), uuid4(), "rss", "Title", "https://example.com", "Summary",
        ("AI",), (), 80, ("fresh",), ("telegram",), uuid4(), datetime.now(UTC)
    )


class TelegramPublisherTests(unittest.TestCase):
    def test_publishes_formatted_candidate(self):
        client = FakeClient(TelegramSendResult(True, 12, "chat", None, None))
        result = asyncio.run(TelegramPublisher(client, parse_mode="HTML").publish(candidate()))
        self.assertTrue(result.success)
        self.assertEqual(result.external_id, "12")
        self.assertIn("Title", client.text)
        self.assertIn("https://example.com", client.text)
        self.assertIn("Score: 80", client.text)

    def test_maps_client_failure(self):
        client = FakeClient(TelegramSendResult(False, None, "chat", 400, "bad request"))
        result = asyncio.run(TelegramPublisher(client).publish(candidate()))
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "bad request")


if __name__ == "__main__":
    unittest.main()
